// 动态获取地图对象（folium生成的地图变量名每次不同）
function getMap() {
    for (let key in window) {
        if (key.startsWith('map_') && window[key] instanceof L.Map) {
            return window[key];
        }
    }
    return null;
}

// 坐标转换参数
const A = 6378245.0;
const EE = 0.00669342162296594323;

function transformLat(x, y) {
    let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    ret += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin(y / 3.0 * Math.PI)) * 2.0 / 3.0;
    ret += (160.0 * Math.sin(y / 12.0 * Math.PI) + 320 * Math.sin(y * Math.PI / 30.0)) * 2.0 / 3.0;
    return ret;
}

function transformLon(x, y) {
    let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    ret += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin(x / 3.0 * Math.PI)) * 2.0 / 3.0;
    ret += (150.0 * Math.sin(x / 12.0 * Math.PI) + 300.0 * Math.sin(x / 30.0 * Math.PI)) * 2.0 / 3.0;
    return ret;
}

function gcj02ToWgs84(gcjLat, gcjLon) {
    let dLat = transformLat(gcjLon - 105.0, gcjLat - 35.0);
    let dLon = transformLon(gcjLon - 105.0, gcjLat - 35.0);
    let radLat = gcjLat / 180.0 * Math.PI;
    let magic = Math.sin(radLat);
    magic = 1 - EE * magic * magic;
    let sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180.0) / ((A * (1 - EE)) / (magic * sqrtMagic) * Math.PI);
    dLon = (dLon * 180.0) / (A / sqrtMagic * Math.cos(radLat) * Math.PI);
    return [gcjLat - dLat, gcjLon - dLon];
}

function bd09ToWgs84(bdLat, bdLon) {
    let x = bdLon - 0.0065;
    let y = bdLat - 0.006;
    let z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * Math.PI * 3000.0 / 180.0);
    let theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * Math.PI * 3000.0 / 180.0);
    let gcjLat = z * Math.sin(theta);
    let gcjLon = z * Math.cos(theta);
    return gcj02ToWgs84(gcjLat, gcjLon);
}

function convertToWgs84(lat, lon, source) {
    return gcj02ToWgs84(lat, lon);
}

function haversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// 两点测距状态
let distanceState = {
    start: null,
    end: null,
    line: null,
    markers: {}
};

// 多点路径状态
let routeState = {
    origin: null,
    points: [],
    line: null,
    markers: {},
    isSettingOrigin: false
};

let currentMode = 'two-point';

// ========== 辅助函数 ==========

function ensureRouteState() {
    if (!routeState.points) routeState.points = [];
    if (!routeState.markers) routeState.markers = {};
}

// ========== 保存与加载功能 ==========

function saveRouteData() {
    ensureRouteState();
    const data = {
        origin: routeState.origin,
        points: routeState.points,
        savedAt: new Date().toISOString()
    };
    try {
        localStorage.setItem('yaelocus_route_data', JSON.stringify(data));
        alert('路线已保存！记录点数: ' + routeState.points.length);
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
}

function loadRouteData() {
    ensureRouteState();
    var map = getMap();
    if (!map) {
        alert('地图未加载，请稍后再试');
        return;
    }
    var saved = localStorage.getItem('yaelocus_route_data');
    if (!saved) {
        alert('没有保存的路线数据');
        return;
    }
    try {
        var data = JSON.parse(saved);
        if (!Array.isArray(data.points)) {
            alert('数据格式错误');
            return;
        }
        // 先清除当前状态
        clearAllRouteMarkers();
        // 加载新数据
        routeState.origin = data.origin || null;
        routeState.points = data.points;
        // 重新绘制
        redrawAllRoute();
        alert('路线已加载！保存时间: ' + (data.savedAt || '未知') + '，记录点数: ' + data.points.length);
    } catch (e) {
        alert('加载失败: ' + e.message);
    }
}

function clearSavedRoute() {
    localStorage.removeItem('yaelocus_route_data');
}

// ========== 标记管理函数 ==========

// 清除所有路线相关标记（不含连线）
function clearAllRouteMarkers() {
    var map = getMap();
    // 先重置 markers 对象，即使 map 为 null 也执行
    var markersToClear = routeState.markers || {};
    routeState.markers = {};
    // 如果 map 存在，逐个清除标记
    if (map) {
        Object.keys(markersToClear).forEach(function(key) {
            var marker = markersToClear[key];
            if (marker) {
                try { map.removeLayer(marker); } catch(e) {}
            }
        });
    }
}

// 重新绘制所有路线元素
function redrawAllRoute() {
    ensureRouteState();
    var map = getMap();
    if (!map) return;

    // 先清除所有现有标记
    clearAllRouteMarkers();

    // 绘制总起点标记
    if (routeState.origin) {
        routeState.markers['origin_circle'] = L.circleMarker([routeState.origin.lat, routeState.origin.lon], {
            radius: 15, color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.9, weight: 3
        }).addTo(map);
        routeState.markers['origin_label'] = L.marker([routeState.origin.lat, routeState.origin.lon], {
            icon: L.divIcon({
                className: 'origin-label',
                html: '<div style="background:#fff;color:#e74c3c;font-weight:bold;font-size:14px;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;border:2px solid #e74c3c;box-shadow:0 2px 4px rgba(0,0,0,0.3);">起</div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            })
        }).addTo(map);
    }

    // 绘制记录点标记
    routeState.points.forEach(function(p, i) {
        routeState.markers['point_' + i + '_circle'] = L.circleMarker([p.lat, p.lon], {
            radius: 15, color: '#4a90d9', fillColor: '#4a90d9', fillOpacity: 0.9, weight: 3
        }).addTo(map);
        routeState.markers['point_' + i + '_label'] = L.marker([p.lat, p.lon], {
            icon: L.divIcon({
                className: 'point-label',
                html: '<div style="background:#fff;color:#4a90d9;font-weight:bold;font-size:14px;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;border:2px solid #4a90d9;box-shadow:0 2px 4px rgba(0,0,0,0.3);">' + (i + 1) + '</div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            })
        }).addTo(map);
    });

    // 绘制连线
    drawRouteLine();
    // 更新UI
    updateRoutePanelUI();
}

// 绘制连线
function drawRouteLine() {
    ensureRouteState();
    var map = getMap();
    if (!map) return;

    // 清除旧连线
    if (routeState.line) {
        try { map.removeLayer(routeState.line); } catch(e) {}
        routeState.line = null;
    }

    // 构建坐标数组
    var coords = [];
    if (routeState.origin) {
        coords.push([routeState.origin.lat, routeState.origin.lon]);
    }
    routeState.points.forEach(function(p) {
        coords.push([p.lat, p.lon]);
    });

    // 绘制新连线
    if (coords.length >= 2) {
        routeState.line = L.polyline(coords, { color: '#4a90d9', weight: 4, opacity: 0.8 }).addTo(map);
    }

    // 更新距离显示
    updateDistanceDisplay();
}

// ========== 总起点功能 ==========

function startSetOrigin() {
    routeState.isSettingOrigin = true;
    var btn = document.getElementById('origin-btn');
    if (btn) {
        btn.textContent = '点击地图';
        btn.style.background = '#e74c3c';
        btn.style.color = 'white';
        btn.style.border = 'none';
    }
    var map = getMap();
    if (map) map.getContainer().style.cursor = 'crosshair';
}

function setOriginPoint(lat, lon) {
    ensureRouteState();
    var wgs = gcj02ToWgs84(lat, lon);
    routeState.origin = { lat: lat, lon: lon, address: '自定义起点', wgsLat: wgs[0], wgsLon: wgs[1] };
    routeState.isSettingOrigin = false;

    var btn = document.getElementById('origin-btn');
    if (btn) {
        btn.textContent = '设置起点';
        btn.style.background = '#f8f9fa';
        btn.style.color = '#333';
        btn.style.border = '1px solid #dee2e6';
    }
    var map = getMap();
    if (map) map.getContainer().style.cursor = '';

    redrawAllRoute();
}

function clearOrigin() {
    routeState.origin = null;
    routeState.isSettingOrigin = false;

    var btn = document.getElementById('origin-btn');
    if (btn) {
        btn.textContent = '设置起点';
        btn.style.background = '#f8f9fa';
        btn.style.color = '#333';
        btn.style.border = '1px solid #dee2e6';
    }
    var map = getMap();
    if (map) map.getContainer().style.cursor = '';

    // 清除总起点标记
    if (routeState.markers['origin_circle']) {
        try { getMap().removeLayer(routeState.markers['origin_circle']); } catch(e) {}
        delete routeState.markers['origin_circle'];
    }
    if (routeState.markers['origin_label']) {
        try { getMap().removeLayer(routeState.markers['origin_label']); } catch(e) {}
        delete routeState.markers['origin_label'];
    }

    drawRouteLine();
    updateRoutePanelUI();
}

// ========== 记录点功能 ==========

function addRecordPoint(lat, lon, address, source) {
    ensureRouteState();
    var wgs = convertToWgs84(lat, lon, source);
    routeState.points.push({
        lat: lat,
        lon: lon,
        address: address,
        wgsLat: wgs[0],
        wgsLon: wgs[1],
        source: source
    });
    redrawAllRoute();
}

function removeRecordPoint(index) {
    ensureRouteState();
    if (index >= 0 && index < routeState.points.length) {
        routeState.points.splice(index, 1);
        redrawAllRoute();
    }
}

// ========== UI更新函数 ==========

function updateRoutePanelUI() {
    ensureRouteState();

    // 更新总起点信息
    var originInfo = document.getElementById('origin-info');
    if (originInfo) {
        if (routeState.origin) {
            originInfo.innerHTML = '<div style="margin:2px 0;padding:4px;background:#ffe6e6;border-radius:3px;font-size:11px;"><span style="color:#e74c3c;">●</span> 起点: (' + routeState.origin.lat.toFixed(4) + ', ' + routeState.origin.lon.toFixed(4) + ') <button onclick="clearOrigin()" style="font-size:10px;padding:2px 6px;background:#fff;border:1px solid #dee2e6;border-radius:2px;cursor:pointer;">清除</button></div>';
        } else {
            originInfo.innerHTML = '';
        }
    }

    // 更新记录点列表
    var recordList = document.getElementById('record-list');
    if (recordList) {
        var html = '';
        routeState.points.forEach(function(p, i) {
            html += '<div style="margin:2px 0;display:flex;justify-content:space-between;align-items:center;">' +
                    '<span style="color:#4a90d9;">' + (i+1) + '.</span> <span style="flex:1;margin-left:4px;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(p.address.substring(0, 15)) + '</span>' +
                    '<button onclick="removeRecordPoint(' + i + ')" style="font-size:10px;padding:2px 6px;background:#fff;border:1px solid #dee2e6;border-radius:2px;cursor:pointer;">删除</button>' +
                    '</div>';
        });
        recordList.innerHTML = html;
    }

    // 更新距离显示
    updateDistanceDisplay();
}

function updateDistanceDisplay() {
    ensureRouteState();

    var segmentsEl = document.getElementById('route-segments');
    var resultEl = document.getElementById('route-result');
    if (!segmentsEl || !resultEl) return;

    var totalDist = 0;
    var segments = [];

    // 计算起点到第一个记录点
    if (routeState.origin && routeState.points.length > 0) {
        var d = haversineDistance(
            routeState.origin.wgsLat, routeState.origin.wgsLon,
            routeState.points[0].wgsLat, routeState.points[0].wgsLon
        );
        segments.push('起点→点1: ' + d.toFixed(2) + ' km');
        totalDist += d;
    }

    // 计算记录点之间
    for (var i = 0; i < routeState.points.length - 1; i++) {
        var d = haversineDistance(
            routeState.points[i].wgsLat, routeState.points[i].wgsLon,
            routeState.points[i+1].wgsLat, routeState.points[i+1].wgsLon
        );
        segments.push('点' + (i+1) + '→点' + (i+2) + ': ' + d.toFixed(2) + ' km');
        totalDist += d;
    }

    segmentsEl.innerHTML = segments.map(function(s) {
        return '<div style="margin:1px 0;">' + s + '</div>';
    }).join('');

    var resultHtml = '<b>总距离:</b> ' + totalDist.toFixed(2) + ' km (' + Math.round(totalDist * 1000) + ' 米)';
    if (routeState.origin) {
        resultHtml += '<br><span style="color:#e74c3c;font-size:11px;">含自定义起点</span>';
    }
    resultEl.innerHTML = resultHtml;
}

// ========== 清除功能 ==========

function clearRoute() {
    var map = getMap();
    if (map) {
        // 清除连线
        if (routeState.line) {
            try { map.removeLayer(routeState.line); } catch(e) {}
        }
        // 清除所有标记
        clearAllRouteMarkers();
        // 重置光标
        map.getContainer().style.cursor = '';
    }
    // 重置状态
    routeState = { origin: null, points: [], line: null, markers: {}, isSettingOrigin: false };

    // 重置UI
    var btn = document.getElementById('origin-btn');
    if (btn) {
        btn.textContent = '设置起点';
        btn.style.background = '#f8f9fa';
        btn.style.color = '#333';
        btn.style.border = '1px solid #dee2e6';
    }
    var originInfo = document.getElementById('origin-info');
    if (originInfo) originInfo.innerHTML = '';
    var recordList = document.getElementById('record-list');
    if (recordList) recordList.innerHTML = '';
    var segmentsEl = document.getElementById('route-segments');
    if (segmentsEl) segmentsEl.innerHTML = '';
    var resultEl = document.getElementById('route-result');
    if (resultEl) resultEl.innerHTML = '';
}

// 监听弹窗打开事件，动态更新按钮显示
function setupPopupListener() {
    var map = getMap();
    if (!map) return;
    map.on('popupopen', function(e) {
        updatePopupButtons();
    });
    // 监听地图点击事件（用于设置总起点）
    map.on('click', function(e) {
        if (routeState.isSettingOrigin) {
            setOriginPoint(e.latlng.lat, e.latlng.lng);
        }
    });
}

function updatePopupButtons() {
    var twoPointBtns = document.querySelectorAll('.two-point-btn');
    var routeBtns = document.querySelectorAll('.route-btn');
    twoPointBtns.forEach(btn => btn.style.display = currentMode === 'two-point' ? 'inline-block' : 'none');
    routeBtns.forEach(btn => btn.style.display = currentMode === 'route' ? 'inline-block' : 'none');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function setDistancePoint(type, lat, lon, address, source) {
    var map = getMap();
    if (!map) return;
    var wgs = convertToWgs84(lat, lon, source);
    distanceState[type] = { lat: lat, lon: lon, address: address, wgsLat: wgs[0], wgsLon: wgs[1], source: source };

    // 清除旧标记
    var markerKey = type + '_marker';
    var labelKey = type + '_label';
    if (distanceState.markers[markerKey]) {
        try { map.removeLayer(distanceState.markers[markerKey]); } catch(e) {}
    }
    if (distanceState.markers[labelKey]) {
        try { map.removeLayer(distanceState.markers[labelKey]); } catch(e) {}
    }

    // 创建明显的标记
    var color = type === 'start' ? '#2ecc71' : '#e74c3c';
    var label = type === 'start' ? '起' : '终';
    // 大圆形背景
    distanceState.markers[markerKey] = L.circleMarker([lat, lon], {
        radius: 15, color: color, fillColor: color, fillOpacity: 0.9, weight: 3
    }).addTo(map);
    // 白色数字标签
    distanceState.markers[labelKey] = L.marker([lat, lon], {
        icon: L.divIcon({
            className: 'distance-label',
            html: '<div style="background:#fff;color:' + color + ';font-weight:bold;font-size:14px;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;border:2px solid ' + color + ';box-shadow:0 2px 4px rgba(0,0,0,0.3);">' + label + '</div>',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        })
    }).addTo(map);

    updateDistanceUI();

    if (distanceState.start && distanceState.end) {
        drawDistanceLine();
        showDistanceResult();
    }
}

function drawDistanceLine() {
    var map = getMap();
    if (!map) return;
    if (distanceState.line) {
        try { map.removeLayer(distanceState.line); } catch(e) {}
    }
    distanceState.line = L.polyline([
        [distanceState.start.lat, distanceState.start.lon],
        [distanceState.end.lat, distanceState.end.lon]
    ], { color: '#FF6600', weight: 4, opacity: 0.8 }).addTo(map);
}

function showDistanceResult() {
    var dist = haversineDistance(
        distanceState.start.wgsLat, distanceState.start.wgsLon,
        distanceState.end.wgsLat, distanceState.end.wgsLon
    );
    var resultEl = document.getElementById('distance-result');
    if (resultEl) {
        resultEl.innerHTML = '<b>距离:</b> ' + dist.toFixed(2) + ' km (' + Math.round(dist * 1000) + ' 米)';
    }
}

function updateDistanceUI() {
    var startEl = document.getElementById('start-point');
    var endEl = document.getElementById('end-point');
    if (startEl) {
        startEl.textContent = distanceState.start ? escapeHtml(distanceState.start.address.substring(0, 20)) : '未选择';
    }
    if (endEl) {
        endEl.textContent = distanceState.end ? escapeHtml(distanceState.end.address.substring(0, 20)) : '未选择';
    }
}

// ========== 清除两点测距 ==========

function clearDistance() {
    var map = getMap();
    if (map) {
        if (distanceState.line) {
            try { map.removeLayer(distanceState.line); } catch(e) {}
        }
        Object.keys(distanceState.markers).forEach(function(key) {
            if (distanceState.markers[key]) {
                try { map.removeLayer(distanceState.markers[key]); } catch(e) {}
            }
        });
    }
    distanceState = { start: null, end: null, line: null, markers: {} };
    var startEl = document.getElementById('start-point');
    var endEl = document.getElementById('end-point');
    var resultEl = document.getElementById('distance-result');
    if (startEl) startEl.textContent = '未选择';
    if (endEl) endEl.textContent = '未选择';
    if (resultEl) resultEl.innerHTML = '';
}

// ========== 模式切换 ==========

function switchMode(mode) {
    currentMode = mode;
    var twoPanel = document.getElementById('two-point-panel');
    var routePanel = document.getElementById('route-panel');
    if (twoPanel) twoPanel.style.display = mode === 'two-point' ? 'block' : 'none';
    if (routePanel) routePanel.style.display = mode === 'route' ? 'block' : 'none';
    // 更新按钮样式 - 统一风格
    var twoBtn = document.getElementById('mode-two-point');
    var routeBtn = document.getElementById('mode-route');
    if (mode === 'two-point') {
        if (twoBtn) {
            twoBtn.style.background = '#4a90d9';
            twoBtn.style.color = 'white';
            twoBtn.style.border = 'none';
        }
        if (routeBtn) {
            routeBtn.style.background = '#f8f9fa';
            routeBtn.style.color = '#333';
            routeBtn.style.border = '1px solid #dee2e6';
        }
    } else {
        if (routeBtn) {
            routeBtn.style.background = '#4a90d9';
            routeBtn.style.color = 'white';
            routeBtn.style.border = 'none';
        }
        if (twoBtn) {
            twoBtn.style.background = '#f8f9fa';
            twoBtn.style.color = '#333';
            twoBtn.style.border = '1px solid #dee2e6';
        }
    }
    updatePopupButtons();
    clearDistance();
    clearRoute();
}

// ========== 多点路径辅助函数 ==========

function updateRouteMarkers() {
    ensureRouteState();
    var map = getMap();
    if (!map) return;
    // 清除现有标记（不含origin）
    clearAllRouteMarkers();
    // 绘制记录点标记 - 使用统一的标记名
    routeState.points.forEach(function(p, i) {
        routeState.markers['point_' + i + '_circle'] = L.circleMarker([p.lat, p.lon], {
            radius: 15, color: '#4a90d9', fillColor: '#4a90d9',
            fillOpacity: 0.9, weight: 3
        }).addTo(map);
        // 序号标签
        routeState.markers['point_' + i + '_label'] = L.marker([p.lat, p.lon], {
            icon: L.divIcon({
                className: 'point-label',
                html: '<div style="background:#fff;color:#4a90d9;font-weight:bold;font-size:14px;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;border:2px solid #4a90d9;box-shadow:0 2px 4px rgba(0,0,0,0.3);">' + (i + 1) + '</div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            })
        }).addTo(map);
    });
    // 绘制origin标记（如果存在）
    if (routeState.origin) {
        routeState.markers['origin_circle'] = L.circleMarker([routeState.origin.lat, routeState.origin.lon], {
            radius: 18, color: '#e74c3c', fillColor: '#e74c3c',
            fillOpacity: 0.9, weight: 4
        }).addTo(map);
        routeState.markers['origin_label'] = L.marker([routeState.origin.lat, routeState.origin.lon], {
            icon: L.divIcon({
                className: 'origin-label',
                html: '<div style="background:#fff;color:#e74c3c;font-weight:bold;font-size:12px;width:30px;height:30px;line-height:30px;text-align:center;border-radius:50%;border:3px solid #e74c3c;box-shadow:0 2px 4px rgba(0,0,0,0.3);">起</div>',
                iconSize: [30, 30],
                iconAnchor: [15, 15]
            })
        }).addTo(map);
    }
}

function updateRouteUI() {
    ensureRouteState();
    updateRoutePanelUI();
    updateDistanceDisplay();
}

function drawRecordLine() {
    ensureRouteState();
    drawRouteLine();
}

// ========== 页面初始化 ==========

// 页面加载完成后初始化
window.addEventListener('load', function() {
    setTimeout(function() {
        setupPopupListener();
        // 自动加载保存的路线数据
        var saved = localStorage.getItem('yaelocus_route_data');
        if (saved) {
            try {
                var data = JSON.parse(saved);
                if (data.points && Array.isArray(data.points)) {
                    routeState.origin = data.origin || null;
                    routeState.points = data.points;
                    if (routeState.origin || routeState.points.length > 0) {
                        redrawAllRoute();
                        console.log('已自动加载保存的路线数据, 记录点数:', routeState.points.length);
                    }
                }
            } catch (e) {
                console.log('自动加载失败:', e);
            }
        }
    }, 800);
});

// 弹窗打开时更新按钮状态
(function(){
    var _pm=null;
    function _pb(){for(var k in window){if(k.startsWith('map_')&&window[k] instanceof L.Map){_pm=window[k];break}}if(!_pm){setTimeout(_pb,500);return}_pm.on('popupopen',function(){if(typeof updatePopupButtons==='function'){setTimeout(updatePopupButtons,50)}})}_pb();
})();

// ========== 面板折叠切换 ==========

function toggleDistancePanel() {
    var body = document.getElementById('distance-panel-body');
    var btn = document.getElementById('distance-toggle-btn');
    if (body && btn) {
        body.style.display = 'block';
        btn.style.display = 'none';
    }
}

function collapseDistancePanel() {
    var body = document.getElementById('distance-panel-body');
    var btn = document.getElementById('distance-toggle-btn');
    if (body && btn) {
        body.style.display = 'none';
        btn.style.display = 'flex';
    }
}