import html
import json
from typing import List, Dict, Optional, Tuple

import folium
from folium.plugins import MarkerCluster, HeatMap
from pathlib import Path

from .config import OutputPaths
from .coords import wgs84_to_gcj02
from .routing.models import TravelMode


# JavaScript 坐标转换和测距代码模板
DISTANCE_JS = """
<script>
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
    var denseBtns = document.querySelectorAll('.dense-btn');
    twoPointBtns.forEach(btn => btn.style.display = currentMode === 'two-point' ? 'inline-block' : 'none');
    routeBtns.forEach(btn => btn.style.display = currentMode === 'route' ? 'inline-block' : 'none');
    denseBtns.forEach(btn => btn.style.display = denseState.enabled ? 'inline-block' : 'none');
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

// ========== 密集搜索模式 ==========

// 全局标记数据（由 Python 注入）
var _denseMarkerData = [];

var denseState = {
    enabled: false,
    center: null,
    previousCenter: null,
    radius: 5,
    recommendations: [],
    highlightMarkers: [],
    routes: [],
    visitHistory: [],
    searchCircle: null
};

function toggleDenseMode() {
    denseState.enabled = !denseState.enabled;
    var btn = document.getElementById('dense-toggle-btn');
    var body = document.getElementById('dense-panel-body');
    if (denseState.enabled) {
        if (btn) btn.classList.add('active');
        if (body) body.style.display = 'block';
        updatePopupButtons();
        // 首次开启时收集标记引用
        if (!window._markersCollected) { _collectAllMarkers(); }
    } else {
        clearDenseMode();
        if (btn) btn.classList.remove('active');
        if (body) body.style.display = 'none';
        updatePopupButtons();
        // 恢复所有标记为完全可见
        _restoreAllMarkers();
    }
}

function selectDenseCenter(idx) {
    if (idx < 0 || idx >= _denseMarkerData.length) return;
    var data = _denseMarkerData[idx];
    // 保存当前圆心为 previousCenter（用于排除）
    if (denseState.center) {
        denseState.previousCenter = {
            idx: denseState.center.idx,
            address: denseState.center.address
        };
    }
    denseState.center = {
        idx: idx,
        gcjLat: data.gcjLat,
        gcjLon: data.gcjLon,
        wgsLat: data.wgsLat,
        wgsLon: data.wgsLon,
        address: data.address
    };
    // 加入访问历史
    denseState.visitHistory.push({
        idx: idx,
        address: data.address,
        gcjLat: data.gcjLat,
        gcjLon: data.gcjLon
    });
    searchNearby();
}

function searchNearby() {
    if (!denseState.center) return;
    var cLat = denseState.center.wgsLat;
    var cLon = denseState.center.wgsLon;
    var radius = denseState.radius;
    var map = getMap();

    // 更新/绘制搜索半径圆（虚线半透明，不阻挡交互）
    if (map) {
        if (denseState.searchCircle) {
            try { map.removeLayer(denseState.searchCircle); } catch(e) {}
        }
        denseState.searchCircle = L.circle([denseState.center.gcjLat, denseState.center.gcjLon], {
            radius: radius * 1000,
            color: '#4a90d9', fillColor: '#4a90d9',
            fillOpacity: 0.05, weight: 1.5, dashArray: '6 4',
            interactive: false
        }).addTo(map);
    }

    // 标记过滤：圆外标记淡化
    _filterMarkersByRadius(denseState.center.wgsLat, denseState.center.wgsLon, radius);

    // 按地址分组统计：{ address: { count, minDist, bestIdx, gcjLat, gcjLon, wgsLat, wgsLon } }
    var groups = {};
    for (var i = 0; i < _denseMarkerData.length; i++) {
        var m = _denseMarkerData[i];
        var dist = haversineDistance(cLat, cLon, m.wgsLat, m.wgsLon);
        if (dist > radius) continue;
        // 排除当前圆心自身
        if (m.idx === denseState.center.idx) continue;
        // 排除上一个圆心
        if (denseState.previousCenter && m.idx === denseState.previousCenter.idx) continue;

        var addr = m.address;
        if (!groups[addr]) {
            groups[addr] = { address: addr, count: 0, minDist: Infinity, bestIdx: i,
                             gcjLat: m.gcjLat, gcjLon: m.gcjLon, wgsLat: m.wgsLat, wgsLon: m.wgsLon };
        }
        groups[addr].count++;
        if (dist < groups[addr].minDist) {
            groups[addr].minDist = dist;
            groups[addr].bestIdx = i;
            groups[addr].gcjLat = m.gcjLat;
            groups[addr].gcjLon = m.gcjLon;
            groups[addr].wgsLat = m.wgsLat;
            groups[addr].wgsLon = m.wgsLon;
        }
    }

    // 转为数组并按规则排序：频次降序 → 距离升序
    var sorted = [];
    for (var key in groups) {
        if (groups.hasOwnProperty(key)) sorted.push(groups[key]);
    }
    sorted.sort(function(a, b) {
        if (b.count !== a.count) return b.count - a.count;
        return a.minDist - b.minDist;
    });

    denseState.recommendations = sorted.slice(0, 5);

    // 清除旧的高亮标记
    clearHighlightMarkers();

    // 绘制新的高亮标记
    if (map) {
        // 圆心标记（红色大圆 + 标签）
        if (denseState.center) {
            denseState.highlightMarkers.push(
                L.circleMarker([denseState.center.gcjLat, denseState.center.gcjLon], {
                    radius: 14, color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.85, weight: 3
                }).addTo(map)
            );
            denseState.highlightMarkers.push(
                L.marker([denseState.center.gcjLat, denseState.center.gcjLon], {
                    icon: L.divIcon({
                        className: 'dense-center-label',
                        html: '<div style="background:#fff;color:#e74c3c;font-weight:bold;font-size:12px;width:28px;height:28px;line-height:28px;text-align:center;border-radius:50%;border:3px solid #e74c3c;box-shadow:0 2px 6px rgba(0,0,0,0.3);">&#9679;</div>',
                        iconSize: [28, 28], iconAnchor: [14, 14]
                    })
                }).addTo(map)
            );
        }
        // 推荐标记（橙色脉冲圆 + 序号标签）
        for (var r = 0; r < denseState.recommendations.length; r++) {
            var rec = denseState.recommendations[r];
            (function(rec, rank) {
                denseState.highlightMarkers.push(
                    L.circleMarker([rec.gcjLat, rec.gcjLon], {
                        radius: 12, color: '#ff6600', fillColor: '#ff6600', fillOpacity: 0.75, weight: 3,
                        className: 'dense-rec-pulse'
                    }).addTo(map).bindTooltip((rank+1) + '. ' + rec.address.substring(0, 20) + ' (' + rec.count + '次, ' + rec.minDist.toFixed(1) + 'km)')
                );
                denseState.highlightMarkers.push(
                    L.marker([rec.gcjLat, rec.gcjLon], {
                        icon: L.divIcon({
                            className: 'dense-rec-label',
                            html: '<div style="background:#fff;color:#ff6600;font-weight:bold;font-size:13px;width:26px;height:26px;line-height:26px;text-align:center;border-radius:50%;border:2px solid #ff6600;box-shadow:0 2px 6px rgba(0,0,0,0.3);">' + (rank+1) + '</div>',
                            iconSize: [26, 26], iconAnchor: [13, 13]
                        })
                    }).addTo(map)
                );
            })(rec, r);
        }
        // 自适应视野
        if (denseState.recommendations.length > 0) {
            var bounds = [[denseState.center.gcjLat, denseState.center.gcjLon]];
            for (var r2 = 0; r2 < denseState.recommendations.length; r2++) {
                bounds.push([denseState.recommendations[r2].gcjLat, denseState.recommendations[r2].gcjLon]);
            }
            try { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 }); } catch(e) {}
        }
    }

    // 同步半径输入框的值
    var radiusInput = document.getElementById('dense-radius-input');
    if (radiusInput && parseFloat(radiusInput.value) !== radius) {
        radiusInput.value = radius;
    }

    updateDensePanelUI();
}

function selectRecommendation(recIdx) {
    if (recIdx < 0 || recIdx >= denseState.recommendations.length) return;
    var rec = denseState.recommendations[recIdx];
    // 绘制路线 A → B
    if (denseState.center) {
        drawDenseRoute(
            { gcjLat: denseState.center.gcjLat, gcjLon: denseState.center.gcjLon, address: denseState.center.address },
            { gcjLat: rec.gcjLat, gcjLon: rec.gcjLon, address: rec.address }
        );
    }
    // 将推荐点设为新圆心（通过 idx 查找）
    var newIdx = rec.bestIdx;
    if (newIdx >= 0 && newIdx < _denseMarkerData.length) {
        selectDenseCenter(newIdx);
    }
}

function drawDenseRoute(from, to) {
    var map = getMap();
    if (!map) return;
    var colors = ['#2ecc71', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800', '#00BCD4', '#795548', '#607D8B'];
    var color = colors[denseState.routes.length % colors.length];
    var line = L.polyline([[from.gcjLat, from.gcjLon], [to.gcjLat, to.gcjLon]], {
        color: color, weight: 4, opacity: 0.8, dashArray: null
    }).addTo(map);
    // 绑定点击查看详情
    var dist = haversineDistance(
        _denseMarkerData[denseState.center.idx].wgsLat, _denseMarkerData[denseState.center.idx].wgsLon,
        _denseMarkerData[denseState.recommendations[0] ? denseState.recommendations[0].bestIdx : 0].wgsLat,
        _denseMarkerData[denseState.recommendations[0] ? denseState.recommendations[0].bestIdx : 0].wgsLon
    );
    line.bindTooltip(from.address.substring(0, 10) + ' → ' + to.address.substring(0, 10));
    denseState.routes.push({ line: line, from: from.address, to: to.address, color: color });
}

function clearHighlightMarkers() {
    var map = getMap();
    if (map) {
        for (var i = 0; i < denseState.highlightMarkers.length; i++) {
            try { map.removeLayer(denseState.highlightMarkers[i]); } catch(e) {}
        }
        if (denseState.searchCircle) {
            try { map.removeLayer(denseState.searchCircle); } catch(e) {}
            denseState.searchCircle = null;
        }
    }
    denseState.highlightMarkers = [];
}

function clearDenseRoutes() {
    var map = getMap();
    if (map) {
        for (var i = 0; i < denseState.routes.length; i++) {
            try { map.removeLayer(denseState.routes[i].line); } catch(e) {}
        }
    }
    denseState.routes = [];
}

function clearDenseMode() {
    clearHighlightMarkers();
    clearDenseRoutes();
    _restoreAllMarkers();
    denseState.center = null;
    denseState.previousCenter = null;
    denseState.recommendations = [];
    denseState.visitHistory = [];
    updateDensePanelUI();
}

// ========== 标记收集与过滤 ==========

function _collectAllMarkers() {
    var map = getMap();
    if (!map) return;
    // 递归遍历所有 layer，收集 L.Marker 实例
    function walk(layer) {
        if (layer instanceof L.Marker) {
            var ll = layer.getLatLng();
            // 按 GCJ-02 坐标匹配 _denseMarkerData（允许微小误差）
            for (var i = 0; i < _denseMarkerData.length; i++) {
                var d = _denseMarkerData[i];
                if (Math.abs(ll.lat - d.gcjLat) < 0.00001 && Math.abs(ll.lng - d.gcjLon) < 0.00001) {
                    if (!_denseMarkerData[i]._layer) {
                        _denseMarkerData[i]._layer = layer;
                    }
                    break;
                }
            }
        }
        if (layer.eachLayer) {
            layer.eachLayer(function(child) { walk(child); });
        }
    }
    map.eachLayer(walk);
    window._markersCollected = true;
}

function _filterMarkersByRadius(cLat, cLon, radius) {
    // 如果标记引用尚未收集，先收集
    if (!window._markersCollected) _collectAllMarkers();
    for (var i = 0; i < _denseMarkerData.length; i++) {
        var m = _denseMarkerData[i];
        if (!m._layer) continue;
        var dist = haversineDistance(cLat, cLon, m.wgsLat, m.wgsLon);
        try {
            if (dist <= radius) {
                m._layer.setOpacity(1.0);
            } else {
                m._layer.setOpacity(0.06);
            }
        } catch(e) {}
    }
}

function _restoreAllMarkers() {
    for (var i = 0; i < _denseMarkerData.length; i++) {
        var m = _denseMarkerData[i];
        if (m._layer) {
            try { m._layer.setOpacity(1.0); } catch(e) {}
        }
    }
}

function updateDensePanelUI() {
    // 圆心信息
    var infoEl = document.getElementById('dense-center-info');
    if (infoEl) {
        if (denseState.center) {
            infoEl.innerHTML = '<strong>圆心:</strong> ' + escapeHtml(denseState.center.address.substring(0, 30)) +
                               '<br><span style="font-size:11px;color:#999;">半径 ' + denseState.radius.toFixed(1) + ' km 内搜索</span>';
        } else {
            infoEl.innerHTML = '请点击地图标记点，在弹出窗口中点击<strong>"选为圆心"</strong>';
        }
    }

    // 推荐列表
    var recList = document.getElementById('dense-rec-list');
    if (recList) {
        if (denseState.recommendations.length === 0) {
            recList.innerHTML = denseState.center ? '<span style="color:#999;">该范围内暂无其他地址</span>' : '<span style="color:#999;">等待选择圆心...</span>';
        } else {
            var html = '';
            for (var i = 0; i < denseState.recommendations.length; i++) {
                var r = denseState.recommendations[i];
                html += '<div onclick="selectRecommendation(' + i + ')" style="padding:8px 10px;margin:4px 0;background:#fff;border:1px solid #e8e8e8;border-radius:8px;cursor:pointer;transition:all 0.15s;display:flex;justify-content:space-between;align-items:center;box-shadow:0 1px 2px rgba(0,0,0,0.03);" onmouseover="this.style.background=\\'#fff8f0\\';this.style.borderColor=\\'#ff9800\\';this.style.boxShadow=\\'0 2px 8px rgba(255,152,0,0.12)\\';this.style.transform=\\'translateX(2px)\\'" onmouseout="this.style.background=\\'#fff\\';this.style.borderColor=\\'#e8e8e8\\';this.style.boxShadow=\\'0 1px 2px rgba(0,0,0,0.03)\\';this.style.transform=\\'translateX(0)\\'">' +
                        '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:6px;"><span style="display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;background:#fff3e0;color:#ff6600;font-weight:bold;font-size:11px;border-radius:5px;">' + (i+1) + '</span> ' + escapeHtml(r.address.substring(0, 16)) + '</span>' +
                        '<span style="font-size:10px;color:#999;margin-left:8px;white-space:nowrap;text-align:right;"><span style="font-weight:600;color:#666;">' + r.count + '</span>次<br><span style="font-size:9px;">' + r.minDist.toFixed(1) + 'km</span></span>' +
                        '</div>';
            }
            recList.innerHTML = html;
        }
    }

    // 路径历史
    var histList = document.getElementById('dense-history-list');
    if (histList) {
        if (denseState.visitHistory.length === 0) {
            histList.innerHTML = '<span style="color:#999;">暂无</span>';
        } else {
            var histHtml = '';
            for (var h = 0; h < denseState.visitHistory.length; h++) {
                var v = denseState.visitHistory[h];
                var arrow = h > 0 ? '<span style="color:#4a90d9;margin:0 4px;">→</span>' : '';
                histHtml += arrow + '<span style="color:#333;">' + escapeHtml(v.address.substring(0, 12)) + '</span>';
            }
            // 路线数量
            histHtml += '<br><span style="font-size:10px;color:#999;">共 ' + denseState.routes.length + ' 段路径</span>';
            histList.innerHTML = histHtml;
        }
    }
}

function updateRadiusFromInput(val) {
    var r = parseFloat(val);
    if (isNaN(r) || r < 0.5) r = 0.5;
    if (r > 50) r = 50;
    denseState.radius = r;
    var input = document.getElementById('dense-radius-input');
    if (input && parseFloat(input.value) !== r) input.value = r;
    if (denseState.center) {
        searchNearby();
    }
}

function adjustRadius(delta) {
    var newVal = denseState.radius + delta;
    if (newVal < 0.5) newVal = 0.5;
    if (newVal > 50) newVal = 50;
    newVal = Math.round(newVal * 2) / 2; // 保留 0.5 步长
    denseState.radius = newVal;
    var input = document.getElementById('dense-radius-input');
    if (input) input.value = newVal;
    if (denseState.center) {
        searchNearby();
    }
}

// ========== 地图搜索栏 ==========

var _searchHighlight = null;  // 搜索高亮的临时圆形

function onSearchFocus() {
    var input = document.getElementById('map-search-input');
    if (input && input.value.length >= 1) {
        filterSuggestions(input.value);
    }
}

function onSearchInput() {
    var input = document.getElementById('map-search-input');
    var clearBtn = document.getElementById('map-search-clear');
    var query = input ? input.value.trim() : '';
    // 控制清除按钮
    if (clearBtn) clearBtn.style.display = query.length > 0 ? 'block' : 'none';
    if (query.length >= 1) {
        filterSuggestions(query);
    } else {
        closeSearchDropdown();
    }
}

function onSearchKeydown(e) {
    if (e.key === 'Escape') { closeSearchDropdown(); return; }
    if (e.key === 'Enter') {
        var first = document.querySelector('.search-dropdown-item.active');
        if (first) first.click();
    }
    // 上下箭头导航
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        var items = document.querySelectorAll('.search-dropdown-item');
        if (items.length === 0) return;
        var active = document.querySelector('.search-dropdown-item.active');
        var idx = -1;
        if (active) {
            for (var i = 0; i < items.length; i++) {
                if (items[i] === active) { idx = i; break; }
            }
            active.classList.remove('active');
        }
        if (e.key === 'ArrowDown') idx = (idx + 1) % items.length;
        else idx = (idx - 1 + items.length) % items.length;
        items[idx].classList.add('active');
        items[idx].scrollIntoView({ block: 'nearest' });
    }
}

function filterSuggestions(query) {
    if (!query || query.length < 1) { closeSearchDropdown(); return; }
    var q = query.toLowerCase();
    var results = [];
    var seen = {};  // 去重（相同地址只显示一次）
    for (var i = 0; i < _denseMarkerData.length; i++) {
        var m = _denseMarkerData[i];
        var addr = m.address;
        if (seen[addr]) continue;
        // 模糊匹配：查询词中的每个字都必须出现在地址中
        var matched = true;
        for (var c = 0; c < q.length; c++) {
            if (addr.indexOf(q.charAt(c)) === -1 && addr.toLowerCase().indexOf(q.charAt(c)) === -1) {
                matched = false; break;
            }
        }
        if (matched) {
            seen[addr] = true;
            results.push({ idx: i, address: addr, source: m.source, gcjLat: m.gcjLat, gcjLon: m.gcjLon });
            if (results.length >= 8) break;
        }
    }
    renderSearchDropdown(results);
}

function renderSearchDropdown(results) {
    var dropdown = document.getElementById('map-search-dropdown');
    if (!dropdown) return;
    if (results.length === 0) {
        dropdown.innerHTML = '<div style="padding:12px 16px;font-size:13px;color:#999;">无匹配结果</div>';
        dropdown.style.display = 'block';
        return;
    }
    var sourceNames = { amap: '高德', tianditu: '天地图', baidu: '百度' };
    var sourceColors = { amap: '#2196F3', tianditu: '#4CAF50', baidu: '#f44336' };
    var html = '';
    for (var i = 0; i < results.length; i++) {
        var r = results[i];
        var sc = sourceColors[r.source] || '#999';
        var sn = sourceNames[r.source] || r.source;
        html += '<div class="search-dropdown-item" onclick="selectSearchResult(' + r.idx + ')" data-idx="' + r.idx + '"' +
                ' style="padding:10px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;' +
                'font-size:13px;border-bottom:1px solid #f5f5f5;transition:background 0.1s;"' +
                ' onmouseover="this.style.background=\\'#f8f9fa\\'" onmouseout="this.style.background=\\'#fff\\'">' +
                '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">' +
                escapeHtml(r.address) + '</span>' +
                '<span style="font-size:10px;color:' + sc + ';margin-left:8px;padding:2px 6px;background:' + sc + '15;border-radius:3px;flex-shrink:0;">' + sn + '</span>' +
                '</div>';
    }
    dropdown.innerHTML = html;
    dropdown.style.display = 'block';
}

function selectSearchResult(idx) {
    if (idx < 0 || idx >= _denseMarkerData.length) return;
    var m = _denseMarkerData[idx];
    var map = getMap();
    if (!map) return;
    // 飞到目标位置
    map.setView([m.gcjLat, m.gcjLon], Math.max(map.getZoom(), 14), { animate: true });
    // 清除旧的高亮
    if (_searchHighlight) {
        try { map.removeLayer(_searchHighlight); } catch(e) {}
        _searchHighlight = null;
    }
    // 高亮闪烁标记
    _searchHighlight = L.circleMarker([m.gcjLat, m.gcjLon], {
        radius: 18, color: '#4a90d9', fillColor: '#4a90d9', fillOpacity: 0.3, weight: 3
    }).addTo(map);
    // 3 秒后渐隐
    setTimeout(function() {
        if (_searchHighlight) {
            try { map.removeLayer(_searchHighlight); } catch(e) {}
            _searchHighlight = null;
        }
    }, 3000);
    // 关闭搜索下拉
    closeSearchDropdown();
    // 打开对应标记的 popup
    setTimeout(function() {
        // 遍历 marker 找到对应位置并触发 click
        map.eachLayer(function(layer) {
            if (layer instanceof L.Marker && !(layer instanceof L.CircleMarker)) {
                var ll = layer.getLatLng();
                if (Math.abs(ll.lat - m.gcjLat) < 0.00001 && Math.abs(ll.lng - m.gcjLon) < 0.00001) {
                    try { layer.openPopup(); } catch(e) {}
                }
            }
        });
    }, 600);
}

function closeSearchDropdown() {
    var dropdown = document.getElementById('map-search-dropdown');
    if (dropdown) dropdown.style.display = 'none';
    // 恢复输入框边框
    var wrapper = document.getElementById('map-search-wrapper');
    if (wrapper) wrapper.style.borderColor = '#e0e0e0';
}

function clearSearchInput() {
    var input = document.getElementById('map-search-input');
    var clearBtn = document.getElementById('map-search-clear');
    if (input) input.value = '';
    if (clearBtn) clearBtn.style.display = 'none';
    closeSearchDropdown();
    if (_searchHighlight) {
        try { getMap().removeLayer(_searchHighlight); } catch(e) {}
        _searchHighlight = null;
    }
}

// 全局点击关闭下拉框
document.addEventListener('click', function(e) {
    var bar = document.getElementById('map-search-bar');
    if (bar && !bar.contains(e.target)) {
        closeSearchDropdown();
    }
});
</script>
"""


# 测距面板 HTML 模板 - 右下角折叠式浮动按钮 + 展开面板
DISTANCE_PANEL = """
<style>
.map-float-btn {
    position: fixed; right: 20px; z-index: 9999;
    width: 44px; height: 44px; border-radius: 50%;
    background: white; color: #666; border: 2px solid #e0e0e0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12); cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 19px; transition: all 0.2s; outline: none;
}
.map-float-btn:hover {
    transform: scale(1.08); box-shadow: 0 4px 14px rgba(0,0,0,0.18);
    border-color: #4a90d9; color: #4a90d9;
}
.map-float-btn.active {
    background: #4a90d9; color: white; border-color: #4a90d9;
}
.map-float-btn.active:hover {
    background: #3d7bc8; border-color: #3d7bc8; color: white;
}
.map-panel-close {
    width: 24px; height: 24px; border-radius: 50%; border: 1px solid #dee2e6;
    background: #f8f9fa; color: #666; cursor: pointer; font-size: 15px;
    line-height: 22px; text-align: center; padding: 0; transition: all 0.15s;
}
.map-panel-close:hover { background: #e74c3c; color: white; border-color: #e74c3c; }
#map-search-input:focus { outline: none; }
#map-search-wrapper:focus-within { border-color: #4a90d9 !important; box-shadow: 0 2px 14px rgba(74,144,217,0.15) !important; }
.search-dropdown-item.active { background: #f0f7ff !important; }
.search-dropdown-item:hover { background: #f8f9fa !important; }
.search-dropdown-item.active:hover { background: #e8f0fb !important; }
#map-search-dropdown::-webkit-scrollbar { width: 4px; }
#map-search-dropdown::-webkit-scrollbar-thumb { background: #e0e0e0; border-radius: 2px; }
</style>
<div id="distance-toggle-btn" onclick="toggleDistancePanel()" title="距离测算" class="map-float-btn"
     style="bottom: 20px;">&#128207;</div>

<div id="distance-panel-body" style="position: fixed; bottom: 20px; right: 76px; z-index: 9998; display: none;
            background-color: white; padding: 14px; border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.18); min-width: 230px; max-width: 310px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <p style="margin: 0; font-weight: 600; font-size: 14px; color: #333;">距离测算</p>
        <button onclick="collapseDistancePanel()" title="折叠" class="map-panel-close">&times;</button>
    </div>
    <div style="margin-top: 8px; display: flex; gap: 5px;">
        <button id="mode-two-point" onclick="switchMode('two-point')"
                style="flex: 1; padding: 6px 10px; font-size: 12px; background: #4a90d9; color: white; border: none; border-radius: 5px; cursor: pointer; transition: all 0.2s;">两点测距</button>
        <button id="mode-route" onclick="switchMode('route')"
                style="flex: 1; padding: 6px 10px; font-size: 12px; background: #f8f9fa; color: #333; border: 1px solid #dee2e6; border-radius: 5px; cursor: pointer; transition: all 0.2s;">多点路径</button>
    </div>

    <div id="two-point-panel" style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee;">
        <p style="margin: 0; font-size: 12px; color: #666;">点击标记点选择起点和终点</p>
        <div style="margin-top: 6px; font-size: 13px;">
            <p style="margin: 4px 0; display: flex; align-items: center;">
                <span style="width: 8px; height: 8px; background: #2ecc71; border-radius: 50%; margin-right: 6px;"></span>
                起点: <span id="start-point" style="color: #2ecc71; margin-left: 4px;">未选择</span>
            </p>
            <p style="margin: 4px 0; display: flex; align-items: center;">
                <span style="width: 8px; height: 8px; background: #e74c3c; border-radius: 50%; margin-right: 6px;"></span>
                终点: <span id="end-point" style="color: #e74c3c; margin-left: 4px;">未选择</span>
            </p>
        </div>
        <div id="distance-result" style="margin-top: 6px; padding: 6px 8px; background: #f8f9fa; border-radius: 5px; font-size: 12px; color: #333;"></div>
        <button onclick="clearDistance()" style="margin-top: 8px; width: 100%; padding: 7px 12px; font-size: 12px; background: #f8f9fa; color: #555; border: 1px solid #dee2e6; border-radius: 5px; cursor: pointer; transition: all 0.15s;">清除选择</button>
    </div>

    <div id="route-panel" style="display: none; margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee;">
        <div style="display: flex; gap: 4px; margin-bottom: 6px;">
            <button id="origin-btn" onclick="startSetOrigin()" style="flex: 1; padding: 5px 8px; font-size: 11px; background: #f8f9fa; color: #333; border: 1px solid #dee2e6; border-radius: 5px; cursor: pointer;">设置起点</button>
            <button onclick="saveRouteData()" style="padding: 5px 8px; font-size: 11px; background: #2ecc71; color: white; border: none; border-radius: 5px; cursor: pointer;">保存</button>
            <button onclick="loadRouteData()" style="padding: 5px 8px; font-size: 11px; background: #4a90d9; color: white; border: none; border-radius: 5px; cursor: pointer;">加载</button>
        </div>
        <div id="origin-info" style="font-size: 11px; margin-bottom: 4px; color: #e74c3c;"></div>
        <p style="margin: 0; font-size: 11px; color: #666;">点击标记点的"记录点"按钮添加</p>
        <div id="record-list" style="font-size: 11px; max-height: 100px; overflow-y: auto; margin-top: 5px; padding: 4px; background: #f8f9fa; border-radius: 5px;"></div>
        <p style="margin: 6px 0 0 0; font-size: 11px; color: #666;">分段距离:</p>
        <div id="route-segments" style="font-size: 11px; color: #333; max-height: 80px; overflow-y: auto; padding: 4px; background: #f8f9fa; border-radius: 5px;"></div>
        <div id="route-result" style="margin-top: 6px; padding: 6px 8px; background: #f8f9fa; border-radius: 5px; font-size: 12px; color: #333;"></div>
        <button onclick="clearRoute()" style="margin-top: 8px; width: 100%; padding: 7px 12px; font-size: 12px; background: #f8f9fa; color: #555; border: 1px solid #dee2e6; border-radius: 5px; cursor: pointer; transition: all 0.15s;">清除路径</button>
    </div>

    <p style="margin-top: 10px; font-size: 10px; color: #999; border-top: 1px solid #eee; padding-top: 6px;">基于 WGS-84 坐标系计算</p>
</div>
"""


# 密集搜索面板 HTML 模板 - 右下角浮动按钮 + 展开面板
DENSE_SEARCH_PANEL = """
<div id="dense-toggle-btn" onclick="toggleDenseMode()" title="密集搜索模式" class="map-float-btn"
     style="bottom: 74px; font-size: 18px;">&#128269;</div>

<div id="dense-panel-body" style="position: fixed; bottom: 20px; right: 76px; z-index: 9996; display: none;
            background-color: white; padding: 14px; border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.18); width: 280px; max-height: 70vh; overflow-y: auto;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <p style="margin: 0; font-weight: 600; font-size: 14px; color: #333;">&#128269; 密集搜索</p>
        <button onclick="toggleDenseMode()" title="关闭" class="map-panel-close">&times;</button>
    </div>

    <div id="dense-center-info" style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 6px; border-left: 3px solid #ff9800; font-size: 12px; color: #666;">
        请点击地图标记点，在弹出窗口中点击<strong>"选为圆心"</strong>
    </div>

    <div style="margin-bottom: 10px;">
        <label style="font-size: 12px; color: #555; font-weight: 500; display: block; margin-bottom: 5px;">搜索半径</label>
        <div style="display: flex; align-items: center; gap: 4px;">
            <button onclick="adjustRadius(-0.5)" title="减小"
                    style="width: 28px; height: 28px; border: 1px solid #dee2e6; border-radius: 5px;
                           background: #f8f9fa; color: #555; cursor: pointer; font-size: 16px; line-height: 1;">&minus;</button>
            <input type="number" id="dense-radius-input" min="0.5" max="50" step="0.5" value="5"
                   onchange="updateRadiusFromInput(this.value)" onkeydown="if(event.key==='Enter')updateRadiusFromInput(this.value)"
                   style="width: 80px; padding: 4px 6px; border: 1px solid #dee2e6; border-radius: 5px;
                          font-size: 13px; text-align: center; color: #333; outline: none;
                          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <button onclick="adjustRadius(0.5)" title="增大"
                    style="width: 28px; height: 28px; border: 1px solid #dee2e6; border-radius: 5px;
                           background: #f8f9fa; color: #555; cursor: pointer; font-size: 16px; line-height: 1;">+</button>
            <span style="font-size: 12px; color: #999; margin-left: 2px;">km</span>
        </div>
    </div>

    <div id="dense-recommendations" style="margin-bottom: 10px;">
        <p style="margin: 0 0 6px 0; font-size: 12px; color: #555; font-weight: 500;">推荐地址（前5）:</p>
        <div id="dense-rec-list" style="font-size: 11px; color: #999;">等待选择圆心...</div>
    </div>

    <div id="dense-history" style="margin-bottom: 10px;">
        <p style="margin: 0 0 6px 0; font-size: 12px; color: #555; font-weight: 500;">搜索路径:</p>
        <div id="dense-history-list" style="font-size: 11px; color: #999;">暂无</div>
    </div>

    <button onclick="clearDenseMode()" style="width: 100%; padding: 8px 12px; font-size: 12px;
            background: #f8f9fa; color: #e74c3c; border: 1px solid #e74c3c; border-radius: 6px;
            cursor: pointer; transition: all 0.15s; font-weight: 500;"
            onmouseover="this.style.background='#e74c3c';this.style.color='white'"
            onmouseout="this.style.background='#f8f9fa';this.style.color='#e74c3c'">清除全部路径</button>
</div>
"""
# 地图搜索栏 - 顶部居中，带自动补全下拉
MAP_SEARCH_BAR = """
<div id="map-search-bar" style="position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;">
    <div style="position: relative; display: flex; align-items: center;
                background: white; border-radius: 22px; box-shadow: 0 2px 12px rgba(0,0,0,0.12);
                border: 2px solid #e0e0e0; transition: border-color 0.2s; width: 340px;"
         id="map-search-wrapper">
        <span style="padding-left: 14px; font-size: 15px; color: #999; flex-shrink: 0;">&#128269;</span>
        <input id="map-search-input" type="text" placeholder="搜索地址..." autocomplete="off"
               oninput="onSearchInput()" onfocus="onSearchFocus()" onkeydown="onSearchKeydown(event)"
               style="flex: 1; padding: 10px 12px 10px 8px; border: none; outline: none;
                      font-size: 14px; color: #333; background: transparent;
                      font-family: inherit; min-width: 0;">
        <button id="map-search-clear" onclick="clearSearchInput()" title="清除"
                style="display: none; width: 24px; height: 24px; border-radius: 50%; border: none;
                       background: #e0e0e0; color: #666; cursor: pointer; font-size: 14px;
                       line-height: 22px; text-align: center; padding: 0; margin-right: 8px; flex-shrink: 0;">&times;</button>
    </div>
    <div id="map-search-dropdown" style="display: none; position: absolute; top: 100%; left: 0; right: 0;
                margin-top: 6px; background: white; border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.14); max-height: 320px; overflow-y: auto;
                border: 1px solid #eee;"></div>
</div>
"""


def create_map(
    data: List[Dict],
    output_file: str = str(OutputPaths.MAP / "地图输出.html"),
    title: str = "地址分布地图",
    use_cluster: bool = True,
    use_heatmap: bool = True,
    default_zoom: int = 5,
) -> str:
    if not data:
        raise ValueError("数据为空，无法创建地图")

    valid_points = [
        (item.get("latitude"), item.get("longitude"), item)
        for item in data
        if item.get("latitude") is not None and item.get("longitude") is not None
    ]

    if not valid_points:
        raise ValueError("没有有效的经纬度数据")

    # 批量转换 WGS-84 → GCJ-02，仅一次
    gcj_points = []
    for lat, lon, item in valid_points:
        gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)
        gcj_points.append((gcj_lat, gcj_lon, lat, lon, item))
    center_lat = sum(p[0] for p in gcj_points) / len(gcj_points)
    center_lon = sum(p[1] for p in gcj_points) / len(gcj_points)

    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=default_zoom, tiles=None
    )

    folium.TileLayer(
        tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        attr="高德地图",
        name="高德底图",
        subdomains="1234",
        max_zoom=18,
        min_zoom=1,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星图",
        name="卫星影像",
        subdomains="1234",
        max_zoom=18,
        min_zoom=1,
        show=False,
    ).add_to(m)

    source_colors = {"amap": "blue", "tianditu": "green", "baidu": "red"}

    feature_group_markers = folium.FeatureGroup(name="标记点")

    if use_cluster:
        marker_cluster = MarkerCluster(name="点聚类")

        for i, (gcj_lat, gcj_lon, wgs_lat, wgs_lon, item) in enumerate(gcj_points):
            source = item.get("source", "unknown")
            color = source_colors.get(source, "gray")
            orig_addr = item.get("original_address", "N/A") or "N/A"
            formatted_addr = item.get("formatted_address", "N/A") or "N/A"
            coord_sys = item.get("coordinate_system", "N/A") or "N/A"
            addr_js = html.escape(json.dumps(orig_addr), quote=True)
            source_js = html.escape(json.dumps(source), quote=True)

            popup_html = f"""
            <span class="dense-marker-idx" style="display:none;">{i}</span>
            <b>地址:</b> {html.escape(orig_addr)}<br>
            <b>标准化地址:</b> {html.escape(formatted_addr)}<br>
            <b>经纬度:</b> {wgs_lat:.6f}, {wgs_lon:.6f}<br>
            <b>数据来源:</b> {html.escape(source)}<br>
            <b>坐标系:</b> {html.escape(coord_sys)}
            <hr style="margin: 5px 0; border-color: #eee;">
            <div style="font-size: 11px;">
                <button onclick="setDistancePoint('start', {gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="two-point-btn" style="padding: 4px 10px; margin: 3px 2px; background: #2ecc71; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">设为起点</button>
                <button onclick="setDistancePoint('end', {gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="two-point-btn" style="padding: 4px 10px; margin: 3px 2px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">设为终点</button>
                <button onclick="addRecordPoint({gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="route-btn" style="padding: 4px 10px; margin: 3px 2px; background: #4a90d9; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; display: none;">记录点</button>
                <button onclick="selectDenseCenter({i})"
                        class="dense-btn" style="padding: 4px 10px; margin: 3px 2px; background: white; color: #ff9800; border: 1.5px solid #ff9800; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 500; display: none;">选为圆心</button>
            </div>
            """

            folium.Marker(
                location=[gcj_lat, gcj_lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon="info-sign"),
                tooltip=item.get("original_address", "")[:30],
            ).add_to(marker_cluster)

        marker_cluster.add_to(feature_group_markers)
    else:
        for i, (gcj_lat, gcj_lon, wgs_lat, wgs_lon, item) in enumerate(gcj_points):
            source = item.get("source", "unknown")
            color = source_colors.get(source, "gray")
            orig_addr = item.get("original_address", "N/A") or "N/A"
            formatted_addr = item.get("formatted_address", "N/A") or "N/A"
            coord_sys = item.get("coordinate_system", "N/A") or "N/A"
            addr_js = html.escape(json.dumps(orig_addr), quote=True)
            source_js = html.escape(json.dumps(source), quote=True)

            popup_html = f"""
            <span class="dense-marker-idx" style="display:none;">{i}</span>
            <b>地址:</b> {html.escape(orig_addr)}<br>
            <b>标准化地址:</b> {html.escape(formatted_addr)}<br>
            <b>经纬度:</b> {wgs_lat:.6f}, {wgs_lon:.6f}<br>
            <b>数据来源:</b> {html.escape(source)}<br>
            <b>坐标系:</b> {html.escape(coord_sys)}
            <hr style="margin: 5px 0; border-color: #eee;">
            <div style="font-size: 11px;">
                <button onclick="setDistancePoint('start', {gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="two-point-btn" style="padding: 4px 10px; margin: 3px 2px; background: #2ecc71; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">设为起点</button>
                <button onclick="setDistancePoint('end', {gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="two-point-btn" style="padding: 4px 10px; margin: 3px 2px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">设为终点</button>
                <button onclick="addRecordPoint({gcj_lat}, {gcj_lon}, {addr_js}, {source_js})"
                        class="route-btn" style="padding: 4px 10px; margin: 3px 2px; background: #4a90d9; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; display: none;">记录点</button>
                <button onclick="selectDenseCenter({i})"
                        class="dense-btn" style="padding: 4px 10px; margin: 3px 2px; background: white; color: #ff9800; border: 1.5px solid #ff9800; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 500; display: none;">选为圆心</button>
            </div>
            """

            folium.Marker(
                location=[gcj_lat, gcj_lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon="info-sign"),
                tooltip=item.get("original_address", "")[:30],
            ).add_to(feature_group_markers)

    feature_group_markers.add_to(m)

    if use_heatmap and len(gcj_points) > 1:
        heat_data = [[p[0], p[1]] for p in gcj_points]
        HeatMap(
            heat_data,
            name="热力图",
            min_opacity=0.3,
            max_opacity=0.8,
            radius=25,
            blur=15,
            show=False,
        ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)

    folium.plugins.Fullscreen(
        position="topleft",
        title="全屏",
        title_cancel="退出全屏",
        force_separate_button=True,
    ).add_to(m)

    folium.plugins.MeasureControl(
        position="bottomleft",
        primary_length_unit="kilometers",
        secondary_length_unit="meters",
        primary_area_unit="sqmeters",
    ).add_to(m)

    title_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background-color: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <h4 style="margin: 0;">{title}</h4>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
            共 {len(valid_points)} 个点位
        </p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 9999;
                background-color: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="margin: 0; font-weight: bold;">数据来源</p>
        <p style="margin: 5px 0;"><span style="color: blue;">●</span> 高德地图</p>
        <p style="margin: 5px 0;"><span style="color: green;">●</span> 天地图</p>
        <p style="margin: 5px 0;"><span style="color: red;">●</span> 百度地图</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # 注入测距/搜索功能（内联嵌入，无外部依赖）
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _inline_js = DISTANCE_JS.strip()
    if _inline_js.startswith("<script>"):
        _inline_js = _inline_js[len("<script>"):]
    if _inline_js.endswith("</script>"):
        _inline_js = _inline_js[:-len("</script>")]
    m.get_root().html.add_child(
        folium.Element(f'<script>{_inline_js}</script>')
    )
    m.get_root().html.add_child(folium.Element(DISTANCE_PANEL))

    # 注入密集搜索功能
    m.get_root().html.add_child(folium.Element(DENSE_SEARCH_PANEL))
    # 注入地图搜索栏
    m.get_root().html.add_child(folium.Element(MAP_SEARCH_BAR))
    # 序列化标记数据（GCJ-02 坐标，匹配地图瓦片），供密集搜索使用
    marker_data = []
    for i, (gcj_lat, gcj_lon, wgs_lat, wgs_lon, item) in enumerate(gcj_points):
        orig_addr = item.get("original_address", "N/A") or "N/A"
        marker_data.append({
            "idx": i,
            "gcjLat": gcj_lat, "gcjLon": gcj_lon,
            "wgsLat": wgs_lat, "wgsLon": wgs_lon,
            "address": orig_addr,
            "source": item.get("source", "unknown")
        })
    m.get_root().html.add_child(
        folium.Element(f'<script>_denseMarkerData = {json.dumps(marker_data, ensure_ascii=False)};</script>')
    )

    m.save(str(output_path))

    return str(output_path.absolute())


# ==================== 路线地图可视化 ====================

ROUTE_MAP_JS = """
<script>
// 路线地图增强 - 实际路线渲染

// 模式颜色配置
var MODE_COLORS = {
    'driving': '#2196F3',
    'transit': '#4CAF50',
    'walking': '#FF9800',
    'bicycling': '#00BCD4'
};

var MODE_NAMES = {
    'driving': '驾车',
    'transit': '公共交通',
    'walking': '步行',
    'bicycling': '骑行'
};

// 路线渲染状态
var routeRenderState = {
    polylines: [],
    modeBadges: []
};

// 绘制实际路线
function drawRoutePolyline(coords, mode, weight, opacity) {
    var map = getMap();
    if (!map) return null;
    var color = MODE_COLORS[mode] || '#2196F3';
    var polyline = L.polyline(coords, {
        color: color,
        weight: weight || 5,
        opacity: opacity || 0.8,
        dashArray: null
    }).addTo(map);
    routeRenderState.polylines.push(polyline);
    return polyline;
}

// 绘制备选路线（虚线）
function drawAlternativeRoute(coords, mode) {
    var map = getMap();
    if (!map) return null;
    var color = MODE_COLORS[mode] || '#999';
    var polyline = L.polyline(coords, {
        color: color,
        weight: 4,
        opacity: 0.5,
        dashArray: '10, 10'
    }).addTo(map);
    routeRenderState.polylines.push(polyline);
    return polyline;
}

// 清除所有路线
function clearAllRoutes() {
    var map = getMap();
    if (!map) return;
    routeRenderState.polylines.forEach(function(l) {
        try { map.removeLayer(l); } catch(e) {}
    });
    routeRenderState.polylines = [];
    // 移除模式徽章
    routeRenderState.modeBadges.forEach(function(el) {
        if (el.parentNode) el.parentNode.removeChild(el);
    });
    routeRenderState.modeBadges = [];
}

// 添加模式图例徽章
function addModeBadge(mode, label) {
    var map = getMap();
    if (!map) return;
    var color = MODE_COLORS[mode] || '#2196F3';
    var badge = L.control({position: 'bottomright'});
    var name = label || MODE_NAMES[mode] || mode;
    badge.onAdd = function() {
        var div = L.DomUtil.create('div', 'route-mode-badge');
        div.innerHTML = '<div style="background: white; padding: 6px 12px; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); margin-bottom: 4px; font-size: 13px; border-left: 4px solid ' + color + ';">' + name + '</div>';
        return div;
    };
    badge.addTo(map);
    routeRenderState.modeBadges.push(badge);
}

// 显示路线信息弹出层
function showRouteInfo(routeData) {
    var html = '<div style="min-width: 280px; max-width: 400px;">';
    html += '<h4 style="margin: 0 0 8px 0; padding-bottom: 6px; border-bottom: 2px solid ' + (MODE_COLORS[routeData.mode] || '#2196F3') + ';">';
    html += (MODE_NAMES[routeData.mode] || routeData.mode) + ' 路线</h4>';

    html += '<table style="width: 100%; font-size: 13px; border-collapse: collapse;">';
    html += '<tr><td style="padding: 3px 0; color: #666;">距离</td><td style="padding: 3px 0; font-weight: bold;">' + routeData.total_distance_km.toFixed(2) + ' km</td></tr>';
    html += '<tr><td style="padding: 3px 0; color: #666;">预计时间</td><td style="padding: 3px 0; font-weight: bold;">' + routeData.total_duration_text + '</td></tr>';

    if (routeData.origin && routeData.origin.address) {
        html += '<tr><td style="padding: 3px 0; color: #666;">起点</td><td style="padding: 3px 0;">' + routeData.origin.address.substring(0, 20) + '</td></tr>';
    }
    if (routeData.destination && routeData.destination.address) {
        html += '<tr><td style="padding: 3px 0; color: #666;">终点</td><td style="padding: 3px 0;">' + routeData.destination.address.substring(0, 20) + '</td></tr>';
    }
    html += '<tr><td style="padding: 3px 0; color: #666;">分段</td><td style="padding: 3px 0;">' + (routeData.segments ? routeData.segments.length : 0) + ' 段</td></tr>';
    html += '</table>';

    // 分段详情
    if (routeData.segments && routeData.segments.length > 0) {
        html += '<h5 style="margin: 8px 0 4px 0; font-size: 12px; color: #666;">路线详情</h5>';
        html += '<div style="max-height: 200px; overflow-y: auto; font-size: 12px;">';
        routeData.segments.slice(0, 20).forEach(function(seg, i) {
            html += '<div style="padding: 4px 0; border-bottom: 1px solid #eee;">';
            html += '<span style="color: #999;">' + (i+1) + '.</span> ';
            html += seg.instruction ? escapeHtml(seg.instruction.substring(0, 40)) : '-';
            html += ' <span style="color: #999; float: right;">' + (seg.distance_km || 0).toFixed(1) + 'km</span>';
            html += '</div>';
        });
        if (routeData.segments.length > 20) {
            html += '<div style="color: #999; text-align: center; padding: 4px;">... 共 ' + routeData.segments.length + ' 段</div>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// 多模式对比渲染
function showModeComparison(results) {
    clearAllRoutes();
    var map = getMap();
    if (!map) return;

    var bounds = [];
    results.forEach(function(r, i) {
        if (r.segments && r.segments.length > 0) {
            var allCoords = [];
            r.segments.forEach(function(seg) {
                if (seg.polyline && seg.polyline.length > 0) {
                    seg.polyline.forEach(function(c) {
                        allCoords.push(c);
                        bounds.push(c);
                    });
                }
            });
            // 使用不同偏移避免完全重叠
            var offset = i * 0.0002;
            var offsetCoords = allCoords.map(function(c) {
                return [c[0] + offset, c[1] + offset];
            });
            drawRoutePolyline(offsetCoords, r.mode, 5 - i, 0.7 - i * 0.1);
            addModeBadge(r.mode, MODE_NAMES[r.mode] + ' ' + r.total_distance_km.toFixed(1) + 'km');
        }

        // 标记起点终点
        if (r.origin) {
            L.circleMarker([r.origin.lat, r.origin.lon], {
                radius: 8, color: '#2ecc71', fillColor: '#2ecc71', fillOpacity: 0.9
            }).addTo(map).bindTooltip('起点: ' + (r.origin.address || ''), {permanent: false});
        }
        if (r.destination) {
            L.circleMarker([r.destination.lat, r.destination.lon], {
                radius: 8, color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.9
            }).addTo(map).bindTooltip('终点: ' + (r.destination.address || ''), {permanent: false});
        }
    });

    // 自适应视野
    if (bounds.length > 0) {
        map.fitBounds(bounds, {padding: [50, 50]});
    }
}
</script>
"""


def create_route_map(
    route_results: List[Dict],
    output_file: str = str(OutputPaths.MAP / "路线规划_地图.html"),
    title: str = "路线规划地图",
    default_zoom: int = 6,
) -> str:
    """创建带有实际路线的交互式路线规划地图

    Args:
        route_results: RouteResult.to_dict() 列表
        output_file: 输出 HTML 文件路径
        title: 地图标题
        default_zoom: 默认缩放级别

    Returns:
        输出文件路径
    """
    if not route_results:
        raise ValueError("路线数据为空")

    # 收集所有坐标点
    all_lats, all_lons = [], []
    route_data_js = []

    for result in route_results:
        result["mode_display"] = TravelMode(result["mode"]).display_name
        origin = result.get("origin")
        dest = result.get("destination")
        origin_gcj = None
        dest_gcj = None
        if origin and origin.get("lat"):
            o_lat, o_lon = wgs84_to_gcj02(origin["lat"], origin["lon"])
            origin_gcj = {"lat": o_lat, "lon": o_lon, "address": origin.get("address", "")}
        if dest and dest.get("lat"):
            d_lat, d_lon = wgs84_to_gcj02(dest["lat"], dest["lon"])
            dest_gcj = {"lat": d_lat, "lon": d_lon, "address": dest.get("address", "")}

        route_data_js.append({
            "mode": result["mode"],
            "mode_display": result["mode_display"],
            "total_distance_km": result["total_distance_km"],
            "total_duration_text": result["total_duration_text"],
            "origin": origin_gcj,
            "destination": dest_gcj,
            "segments": result.get("segments", []),
            "ai_summary": result.get("ai_summary", ""),
        })

        # 收集坐标
        for seg in result.get("segments", []):
            for pt in seg.get("polyline", []):
                all_lats.append(pt[0])
                all_lons.append(pt[1])

        # 起点终点坐标（转为 GCJ-02 以对齐瓦片）
        if origin_gcj:
            all_lats.append(origin_gcj["lat"])
            all_lons.append(origin_gcj["lon"])
        if dest_gcj:
            all_lats.append(dest_gcj["lat"])
            all_lons.append(dest_gcj["lon"])

    if not all_lats:
        raise ValueError("没有可渲染的坐标点")

    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=default_zoom,
        tiles=None,
    )

    # 底图
    folium.TileLayer(
        tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        attr="高德地图",
        name="高德底图",
        subdomains="1234",
        max_zoom=18,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星图",
        name="卫星影像",
        subdomains="1234",
        max_zoom=18,
        show=False,
    ).add_to(m)

    # 绘制路线
    mode_colors = {
        "driving": "#2196F3",
        "transit": "#4CAF50",
        "walking": "#FF9800",
        "bicycling": "#00BCD4",
    }

    for i, result in enumerate(route_results):
        color = mode_colors.get(result["mode"], "#2196F3")
        all_coords = []

        for seg in result.get("segments", []):
            polyline = seg.get("polyline", [])
            if polyline:
                coords = [(pt[0], pt[1]) for pt in polyline]
                all_coords.extend(coords)

                # 每个分段用独立 polyline（更好的鼠标交互）
                folium.PolyLine(
                    locations=coords,
                    color=color,
                    weight=5 - i * 0.5,
                    opacity=0.8 - i * 0.1,
                    popup=f"<b>第{result.get('segments', []).index(seg) + 1}段</b><br>{seg.get('instruction', '')[:50]}",
                    tooltip=f"{TravelMode(result['mode']).display_name}: {seg.get('distance_km', 0):.1f}km",
                ).add_to(m)

        # 起点终点标记
        origin = result.get("origin", {})
        destination = result.get("destination", {})

        if origin and origin.get("lat"):
            o_lat, o_lon = wgs84_to_gcj02(origin["lat"], origin["lon"])
            folium.CircleMarker(
                location=[o_lat, o_lon],
                radius=10,
                color="#2ecc71",
                fill=True,
                fillColor="#2ecc71",
                fillOpacity=0.9,
                popup=f"<b>起点:</b> {origin.get('address', '')}<br><b>坐标:</b> {origin['lat']:.4f}, {origin['lon']:.4f}",
            ).add_to(m)

            folium.Marker(
                location=[o_lat, o_lon],
                icon=folium.DivIcon(html=f'<div style="background:#fff;color:#2ecc71;font-weight:bold;font-size:16px;width:28px;height:28px;line-height:28px;text-align:center;border-radius:50%;border:3px solid #2ecc71;">起</div>'),
            ).add_to(m)

        if destination and destination.get("lat"):
            d_lat, d_lon = wgs84_to_gcj02(destination["lat"], destination["lon"])
            folium.CircleMarker(
                location=[d_lat, d_lon],
                radius=10,
                color="#e74c3c",
                fill=True,
                fillColor="#e74c3c",
                fillOpacity=0.9,
                popup=f"<b>终点:</b> {destination.get('address', '')}<br><b>坐标:</b> {destination['lat']:.4f}, {destination['lon']:.4f}",
            ).add_to(m)

            folium.Marker(
                location=[d_lat, d_lon],
                icon=folium.DivIcon(html=f'<div style="background:#fff;color:#e74c3c;font-weight:bold;font-size:16px;width:28px;height:28px;line-height:28px;text-align:center;border-radius:50%;border:3px solid #e74c3c;">终</div>'),
            ).add_to(m)

        # 途经点标记
        for wp in result.get("waypoints", []):
            if wp.get("lat"):
                wp_lat, wp_lon = wgs84_to_gcj02(wp["lat"], wp["lon"])
                folium.CircleMarker(
                    location=[wp_lat, wp_lon],
                    radius=7,
                    color="#f39c12",
                    fill=True,
                    fillColor="#f39c12",
                    fillOpacity=0.8,
                    popup=f"<b>途经点 {wp.get('order', '')}:</b> {wp.get('address', '')}",
                ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)

    folium.plugins.Fullscreen(
        position="topleft",
        title="全屏",
        title_cancel="退出全屏",
        force_separate_button=True,
    ).add_to(m)

    # 路线信息面板（汇总所有路线）
    route_summary_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background-color: white; padding: 12px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2); max-width: 320px;">
        <h4 style="margin: 0 0 8px 0;">{title}</h4>
        <div style="font-size: 12px;">
    """
    for result in route_results:
        color = mode_colors.get(result["mode"], "#2196F3")
        route_summary_html += f"""
        <div style="border-left: 4px solid {color}; padding: 4px 8px; margin: 4px 0; background: #f8f9fa; border-radius: 0 3px 3px 0;">
            <strong>{TravelMode(result['mode']).display_name}</strong><br>
            <span>{result['total_distance_km']:.2f} km | {result['total_duration_text']}</span>
        </div>
        """

    route_summary_html += """
        </div>
    </div>
    """

    # 图例
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 9999;
                background-color: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="margin: 0 0 4px 0; font-weight: bold;">出行方式</p>
        <p style="margin: 2px 0;"><span style="color: #2196F3;">━</span> 驾车</p>
        <p style="margin: 2px 0;"><span style="color: #4CAF50;">━</span> 公共交通</p>
        <p style="margin: 2px 0;"><span style="color: #FF9800;">━</span> 步行</p>
        <p style="margin: 2px 0;"><span style="color: #00BCD4;">━</span> 骑行</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(route_summary_html))
    m.get_root().html.add_child(folium.Element(legend_html))

    # 注入 JS
    m.get_root().html.add_child(folium.Element(ROUTE_MAP_JS))

    # 注入路线数据
    route_data_json = json.dumps(route_data_js, ensure_ascii=False)
    route_data_script = f"""
    <script>
    var routeResults = {route_data_json};
    // 自动渲染第一条路线
    if (typeof getMap === 'function' && routeResults.length > 0) {{
        setTimeout(function() {{
            var r = routeResults[0];
            if (r.segments && r.segments.length > 0 && typeof showRouteInfo === 'function') {{
                // 渲染第一条路线
                r.segments.forEach(function(seg) {{
                    if (seg.polyline && seg.polyline.length > 0) {{
                        drawRoutePolyline(seg.polyline, r.mode, 5, 0.8);
                    }}
                }});
                addModeBadge(r.mode, r.mode_display + ' ' + r.total_distance_km.toFixed(1) + 'km');
            }}
        }}, 500);
    }}
    </script>
    """
    m.get_root().html.add_child(folium.Element(route_data_script))

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))

    return str(output_path.absolute())


# ==================== AI 路线规划地图 ====================


def create_map_with_routes(
    data: List[Dict],
    routes: List[Dict],
    start_point: Optional[Tuple[float, float]] = None,
    output_file: str = str(OutputPaths.MAP / "路线规划_地图.html"),
    title: str = "路线规划地图",
    default_zoom: int = 10,
) -> str:
    """创建带 AI 路线绘制的交互式地图"""
    if not data:
        raise ValueError("数据为空")

    # 预转换 start_point 一次（后续多处使用）
    gcj_start = None
    if start_point:
        gcj_start = wgs84_to_gcj02(start_point[0], start_point[1])

    all_lats, all_lons = [], []
    for item in data:
        lat, lon = item.get("latitude"), item.get("longitude")
        if lat and lon:
            gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)
            all_lats.append(gcj_lat)
            all_lons.append(gcj_lon)
    for route in routes:
        for wp in route.get("waypoints", []):
            if wp.get("lat") and wp.get("lon"):
                gcj_lat, gcj_lon = wgs84_to_gcj02(wp["lat"], wp["lon"])
                all_lats.append(gcj_lat)
                all_lons.append(gcj_lon)
    if gcj_start:
        all_lats.append(gcj_start[0])
        all_lons.append(gcj_start[1])

    if not all_lats:
        raise ValueError("没有可渲染的坐标点")

    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=default_zoom, tiles=None)

    folium.TileLayer(
        tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        attr="高德地图", name="高德底图", subdomains="1234", max_zoom=18,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星图", name="卫星影像", subdomains="1234", max_zoom=18, show=False,
    ).add_to(m)

    source_colors = {"amap": "blue", "tianditu": "green", "baidu": "red"}
    marker_cluster = MarkerCluster(name="地址标记")
    for item in data:
        lat, lon = item.get("latitude"), item.get("longitude")
        if not lat or not lon:
            continue
        gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)
        source = item.get("source", "unknown")
        color = source_colors.get(source, "gray")
        addr = item.get("original_address", "")
        addr_js = html.escape(json.dumps(addr), quote=True) if addr else '""'
        source_js = html.escape(json.dumps(source), quote=True)
        popup_html = (
            f"<b>地址:</b> {html.escape(item.get('original_address', ''))}<br>"
            f"<b>标准化:</b> {html.escape(item.get('formatted_address', ''))}<br>"
            f"<b>坐标:</b> {lat:.6f}, {lon:.6f}<br>"
            f"<b>来源:</b> {html.escape(source)}"
            f"<hr style='margin:5px 0;border-color:#eee;'>"
            f"<div style='font-size:11px;'>"
            f"<button onclick=\"setDistancePoint('start',{gcj_lat},{gcj_lon},{addr_js},{source_js})\""
            f" style='padding:3px 8px;margin:2px;background:#2ecc71;color:white;border:none;border-radius:3px;cursor:pointer;'>设为起点</button>"
            f"<button onclick=\"setDistancePoint('end',{gcj_lat},{gcj_lon},{addr_js},{source_js})\""
            f" style='padding:3px 8px;margin:2px;background:#e74c3c;color:white;border:none;border-radius:3px;cursor:pointer;'>设为终点</button>"
            f"<button onclick=\"addRecordPoint({gcj_lat},{gcj_lon},{addr_js},{source_js})\""
            f" style='padding:3px 8px;margin:2px;background:#4a90d9;color:white;border:none;border-radius:3px;cursor:pointer;display:none;'>记录点</button>"
            f"</div>"
        )
        folium.Marker(
            location=[gcj_lat, gcj_lon],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon="info-sign"),
            tooltip=addr[:30] if addr else "",
        ).add_to(marker_cluster)
    marker_cluster.add_to(m)

    route_colors = ["#e74c3c", "#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]
    route_names = ["路线一", "路线二", "路线三", "路线四", "路线五"]

    for i, route in enumerate(routes):
        color = route_colors[i % len(route_colors)]
        route_name = route.get("name", route_names[i % len(route_names)])
        coords = []
        waypoints = route.get("waypoints", [])
        if gcj_start:
            coords.append([gcj_start[0], gcj_start[1]])
        for wp in waypoints:
            if wp.get("lat") and wp.get("lon"):
                gcj_lat, gcj_lon = wgs84_to_gcj02(wp["lat"], wp["lon"])
                coords.append([gcj_lat, gcj_lon])
        if len(coords) < 2:
            continue

        route["_index"] = i
        popup_text = _build_route_popup_html(route)
        ttip = f"{route_name}: {route.get('computed_distance_km', route.get('estimated_distance_km', 0)):.1f}km"

        route_group = folium.FeatureGroup(name=route_name, show=True)
        folium.PolyLine(
            locations=coords, color=color, weight=5, opacity=0.8,
            tooltip=ttip,
        ).add_to(route_group)

        for j, wp in enumerate(waypoints):
            if wp.get("lat") and wp.get("lon"):
                gcj_lat, gcj_lon = wgs84_to_gcj02(wp["lat"], wp["lon"])
                folium.CircleMarker(
                    location=[gcj_lat, gcj_lon],
                    radius=5, color=color, fill=True,
                    fillColor=color, fillOpacity=0.7,
                    popup=f"<b>{j + 1}.</b> {wp.get('address', '')}",
                ).add_to(route_group)
        route_group.add_to(m)

    if start_point:
        s_lat, s_lon = wgs84_to_gcj02(start_point[0], start_point[1])
        folium.CircleMarker(
            location=[s_lat, s_lon],
            radius=14, color="#e74c3c", fill=True,
            fillColor="#e74c3c", fillOpacity=0.9, weight=3,
            popup="<b>总起点</b>",
        ).add_to(m)
        folium.Marker(
            location=[s_lat, s_lon],
            icon=folium.DivIcon(
                html=('<div style="background:#fff;color:#e74c3c;font-weight:bold;font-size:14px;'
                      'width:28px;height:28px;line-height:28px;text-align:center;border-radius:50%;'
                      'border:3px solid #e74c3c;box-shadow:0 2px 4px rgba(0,0,0,0.3);">起</div>')
            ),
        ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)
    folium.plugins.Fullscreen(
        position="topleft", title="全屏",
        title_cancel="退出全屏", force_separate_button=True,
    ).add_to(m)

    title_el = (
        f'<div style="position:fixed;top:10px;left:50px;z-index:9999;'
        f'background:white;padding:10px 15px;border-radius:5px;'
        f'box-shadow:0 2px 5px rgba(0,0,0,0.2);">'
        f'<h4 style="margin:0;">{title}</h4>'
        f'<p style="margin:4px 0 0 0;font-size:12px;color:#666;">'
        f'{len(data)} 个地址 | {len(routes)} 条路线</p></div>'
    )
    m.get_root().html.add_child(folium.Element(title_el))

    legend_items = "".join(
        f'<p style="margin:2px 0;">'
        f'<span style="color:{route_colors[i % len(route_colors)]};">━</span> '
        f'{r.get("name", route_names[i % len(route_names)])}'
        f' ({r.get("computed_distance_km", r.get("estimated_distance_km", 0)):.1f}km)</p>'
        for i, r in enumerate(routes)
    )
    legend_html = (
        f'<div style="position:fixed;bottom:50px;left:50px;z-index:9999;'
        f'background:white;padding:10px;border-radius:5px;'
        f'box-shadow:0 2px 5px rgba(0,0,0,0.2);font-size:13px;">'
        f'<p style="margin:0 0 4px 0;font-weight:bold;">路线方案</p>'
        f'{legend_items}</div>'
    )
    m.get_root().html.add_child(folium.Element(legend_html))

    # 注入测距/搜索功能（内联嵌入，无外部依赖）
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _inline_js = DISTANCE_JS.strip()
    if _inline_js.startswith("<script>"):
        _inline_js = _inline_js[len("<script>"):]
    if _inline_js.endswith("</script>"):
        _inline_js = _inline_js[:-len("</script>")]
    m.get_root().html.add_child(
        folium.Element(f'<script>{_inline_js}</script>')
    )
    m.get_root().html.add_child(folium.Element(DISTANCE_PANEL))

    route_data_json = json.dumps(routes, ensure_ascii=False)
    m.get_root().html.add_child(folium.Element(
        f'<script>var aiRouteData = {route_data_json};</script>'
    ))

    # 注入路线点击弹窗 JS
    route_popup_htmls = []
    for r in routes:
        route_popup_htmls.append(_build_route_popup_html(r))
    route_popup_json = json.dumps(route_popup_htmls, ensure_ascii=False)
    click_handler_js = (
        '<script>'
        'var _routePopups = ' + route_popup_json + ';'
        '(function(){'
        'function _bind(){'
        'var m=null;'
        'for(var k in window){if(k.startsWith("map_")&&window[k] instanceof L.Map){m=window[k];break}}'
        'if(!m){setTimeout(_bind,500);return}'
        'm.on("popupopen",function(){'
        'if(typeof updatePopupButtons==="function"){setTimeout(updatePopupButtons,50)}'
        '});'
        'var idx=0;'
        'function walk(layer){'
        'if(layer instanceof L.Polyline&&layer.options&&layer.options.weight>2){'
        '(function(i){'
        'layer.on("click",function(e){'
        'L.popup().setLatLng(e.latlng).setContent(_routePopups[i]).setMaxWidth(400).openOn(m)'
        '})'
        '})(idx);'
        'idx++;'
        '}'
        'if(layer.eachLayer){layer.eachLayer(function(c){walk(c)})}'
        '}'
        'm.eachLayer(walk);'
        'if(idx===0){setTimeout(function(){m.eachLayer(walk)},1500)}'
        '}'
        '_bind()'
        '})()'
        '</script>'
    )
    m.get_root().html.add_child(folium.Element(click_handler_js))

    m.save(str(output_path))

    return str(output_path.absolute())


def _build_route_popup_html(route: Dict) -> str:
    """构建路线弹出 HTML（点击路线显示 AI 描述）"""
    name = route.get("name", "路线")
    desc = route.get("description", "")
    tips = route.get("travel_tips", "")
    dist = route.get("computed_distance_km") or route.get("estimated_distance_km", 0)
    duration = route.get("estimated_duration_minutes", 0)
    waypoints = route.get("waypoints", [])
    mode_names = {"driving": "驾车", "transit": "公交", "walking": "步行", "bicycling": "骑行"}
    mode = mode_names.get(route.get("mode", "driving"), "驾车")

    html = (
        f'<div style="min-width:260px;max-width:380px;font-family:sans-serif;">'
        f'<h4 style="margin:0 0 8px 0;padding-bottom:6px;border-bottom:2px solid #333;">'
        f'{name} <span style="font-size:12px;color:#666;">({mode})</span></h4>'
        f'<table style="width:100%;font-size:13px;border-collapse:collapse;">'
        f'<tr><td style="padding:2px 0;color:#666;">距离</td>'
        f'<td style="padding:2px 0;font-weight:bold;">{dist:.1f} km</td></tr>'
        f'<tr><td style="padding:2px 0;color:#666;">预计时间</td>'
        f'<td style="padding:2px 0;font-weight:bold;">{duration:.0f} 分钟</td></tr>'
        f'<tr><td style="padding:2px 0;color:#666;">途经地址</td>'
        f'<td style="padding:2px 0;font-weight:bold;">{len(waypoints)} 处</td></tr></table>'
    )
    if desc:
        html += (
            f'<div style="margin-top:8px;padding:8px;background:#f8f9fa;border-radius:4px;'
            f'font-size:12px;line-height:1.5;"><strong>路线描述</strong><br>{desc}</div>'
        )
    if tips:
        html += (
            f'<div style="margin-top:6px;padding:8px;background:#fff3e0;border-radius:4px;'
            f'font-size:12px;line-height:1.5;"><strong>出行建议</strong><br>{tips}</div>'
        )
    if waypoints:
        html += '<h5 style="margin:8px 0 4px 0;font-size:12px;color:#666;">途经顺序</h5>'
        html += '<ol style="margin:0;padding-left:20px;font-size:12px;max-height:150px;overflow-y:auto;">'
        for wp in waypoints:
            html += f'<li style="padding:2px 0;">{wp.get("address", "")[:25]}</li>'
        html += '</ol>'
    html += "</div>"
    return html


# ==================== AI 路线规划可视化地图 ====================


def create_ai_route_map(
    data: List[Dict],
    routes_data: List[Dict],
    analysis: Optional[Dict] = None,
    output_file: str = str(OutputPaths.MAP / "路线规划_地图.html"),
    title: str = "AI 路线规划",
    default_zoom: int = 11,
) -> str:
    """创建 AI 路线规划可视化地图，带侧边栏路线开关和 AI 分析。

    Args:
        data: 地址列表，每项含 latitude, longitude, original_address, source
        routes_data: AI 路线方案列表，每项含 name, waypoints, total_distance_km 等
        analysis: AI 分析摘要，含 density_analysis, cluster_analysis
        output_file: 输出 HTML 文件路径
        title: 地图标题
        default_zoom: 默认缩放级别
    """
    if not data:
        raise ValueError("地址数据为空")

    all_lats, all_lons = [], []
    for item in data:
        lat = item.get("latitude") or (item[1] if isinstance(item, (list, tuple)) else None)
        lon = item.get("longitude") or (item[2] if isinstance(item, (list, tuple)) else None)
        if lat is not None and lon is not None:
            try:
                gcj_lat, gcj_lon = wgs84_to_gcj02(float(lat), float(lon))
                all_lats.append(gcj_lat)
                all_lons.append(gcj_lon)
            except (ValueError, TypeError):
                continue

    for route in routes_data:
        for wp in route.get("waypoints", []):
            if wp.get("lat") and wp.get("lon"):
                try:
                    gcj_lat, gcj_lon = wgs84_to_gcj02(float(wp["lat"]), float(wp["lon"]))
                    all_lats.append(gcj_lat)
                    all_lons.append(gcj_lon)
                except (ValueError, TypeError):
                    continue

    if not all_lats:
        raise ValueError("没有有效的坐标点")

    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=default_zoom, tiles=None)

    folium.TileLayer(
        tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        attr="高德地图", name="高德底图", subdomains="1234", max_zoom=18,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星图", name="卫星影像", subdomains="1234", max_zoom=18, show=False,
    ).add_to(m)

    # 地址标记
    source_colors = {"amap": "blue", "tianditu": "green", "baidu": "red"}
    marker_cluster = MarkerCluster(name="地址标记")
    for item in data:
        if isinstance(item, dict):
            lat = item.get("latitude")
            lon = item.get("longitude")
            addr = item.get("original_address", "")
            source = item.get("source", "unknown")
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            addr, lat, lon = item[0], item[1], item[2]
            source = "unknown"
        else:
            continue
        if not lat or not lon:
            continue
        try:
            lat, lon = float(lat), float(lon)
            gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)
        except (ValueError, TypeError):
            continue
        color = source_colors.get(source, "gray")
        folium.Marker(
            location=[gcj_lat, gcj_lon],
            popup=folium.Popup(
                f"<b>{addr[:50]}</b><br>坐标: {lat:.6f}, {lon:.6f}<br>来源: {source}",
                max_width=280
            ),
            icon=folium.Icon(color=color, icon="info-sign"),
            tooltip=addr[:30] if addr else "",
        ).add_to(marker_cluster)
    marker_cluster.add_to(m)

    # 路线绘制
    route_colors = ["#e74c3c", "#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]
    route_names = ["路线一", "路线二", "路线三", "路线四", "路线五"]
    route_groups = []

    for i, route in enumerate(routes_data):
        color = route_colors[i % len(route_colors)]
        route_name = route.get("name", route_names[i % len(route_names)])
        coords = []
        for wp in route.get("waypoints", []):
            if wp.get("lat") and wp.get("lon"):
                try:
                    gcj_lat, gcj_lon = wgs84_to_gcj02(float(wp["lat"]), float(wp["lon"]))
                    coords.append([gcj_lat, gcj_lon])
                except (ValueError, TypeError):
                    continue
        if len(coords) < 2:
            continue

        dist = route.get("total_distance_km",
               route.get("computed_distance_km",
               route.get("estimated_distance_km", 0)))
        gid = f"route_group_{i}"
        route_group = folium.FeatureGroup(name=route_name, show=True)
        folium.PolyLine(
            locations=coords, color=color, weight=5, opacity=0.8,
            tooltip=f"{route_name}: {dist:.1f}km",
        ).add_to(route_group)

        for j, wp in enumerate(route.get("waypoints", [])):
            if wp.get("lat") and wp.get("lon"):
                try:
                    gcj_lat, gcj_lon = wgs84_to_gcj02(float(wp["lat"]), float(wp["lon"]))
                except (ValueError, TypeError):
                    continue
                folium.CircleMarker(
                    location=[gcj_lat, gcj_lon],
                    radius=5, color=color, fill=True,
                    fillColor=color, fillOpacity=0.7,
                    popup=f"<b>{j + 1}.</b> {wp.get('address', '')}",
                ).add_to(route_group)
        route_group.add_to(m)
        route_groups.append({"name": route_name, "color": color, "dist": dist,
                             "desc": route.get("description", ""), "index": i})

    # 全屏控件
    folium.plugins.Fullscreen(
        position="topleft", title="全屏",
        title_cancel="退出全屏", force_separate_button=True,
    ).add_to(m)

    # 图例
    legend_items = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0;font-size:12px;">'
        f'<span style="width:20px;height:3px;background:{rg["color"]};border-radius:2px;flex-shrink:0;"></span>'
        f'<span>{rg["name"]} {rg["dist"]:.1f}km</span></div>'
        for rg in route_groups
    )
    legend_html = (
        f'<div style="position:fixed;bottom:50px;left:50px;z-index:9999;'
        f'background:white;padding:12px 14px;border-radius:8px;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.15);font-size:13px;">'
        f'<div style="font-weight:bold;margin-bottom:6px;">路线方案</div>'
        f'{legend_items}</div>'
    )
    m.get_root().html.add_child(folium.Element(legend_html))

    # AI 侧边面板
    analysis_html = ""
    if analysis:
        density = analysis.get("density_analysis", "")
        cluster = analysis.get("cluster_analysis", "")
        if density:
            analysis_html += f'<div style="font-size:11px;color:#666;margin-bottom:6px;">{density}</div>'
        if cluster:
            analysis_html += f'<div style="font-size:11px;color:#666;margin-bottom:6px;">{cluster}</div>'

    toggle_items = "".join(
        f'<button id="route-btn-{rg["index"]}" onclick="toggleAIRoute({rg["index"]})" '
        f'style="display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;margin:3px 0;'
        f'border:1px solid #e5e7eb;border-radius:6px;background:#fff;cursor:pointer;font-size:12px;'
        f'text-align:left;transition:all 0.15s;">'
        f'<span style="width:14px;height:14px;border-radius:3px;background:{rg["color"]};flex-shrink:0;"></span>'
        f'<span style="flex:1;font-weight:500;">{rg["name"]}</span>'
        f'<span style="color:#999;font-size:11px;">{rg["dist"]:.1f}km</span>'
        f'</button>'
        for rg in route_groups
    )

    panel_html = (
        f'<div id="ai-route-panel" style="position:fixed;top:10px;right:10px;z-index:9999;'
        f'background:white;border-radius:12px;padding:14px;'
        f'box-shadow:0 4px 16px rgba(0,0,0,0.12);width:260px;max-height:75vh;overflow-y:auto;'
        f'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;">'
        f'<h4 style="margin:0 0 6px;font-size:14px;color:#1f2937;">{title}</h4>'
        f'{analysis_html}'
        f'<div style="font-size:11px;color:#9ca3af;margin-bottom:8px;">点击按钮切换路线显示</div>'
        f'{toggle_items}'
        f'</div>'
    )
    m.get_root().html.add_child(folium.Element(panel_html))

    # 路线切换 JS
    route_groups_json = json.dumps(
        [{"index": rg["index"], "name": rg["name"]} for rg in route_groups],
        ensure_ascii=False
    )
    toggle_js = (
        '<script>'
        f'var _aiRouteGroups = {route_groups_json};'
        'function _findMap() {'
        '  for(var k in window){if(k.startsWith("map_")&&window[k] instanceof L.Map) return window[k];}'
        '  return null;'
        '}'
        'function toggleAIRoute(idx) {'
        '  var m = _findMap(); if(!m) return;'
        '  var btn = document.getElementById("route-btn-"+idx);'
        '  m.eachLayer(function(layer) {'
        '    if(layer instanceof L.FeatureGroup) {'
        '      var found = false;'
        '      layer.eachLayer(function(child) {'
        '        if(child instanceof L.Polyline && child.options && child.options.weight > 2)'
        '          found = true;'
        '      });'
        '      if(found && layer.options && layer._routeIdx === idx) {'
        '        if(m.hasLayer(layer)) { m.removeLayer(layer); btn.style.opacity="0.4"; }'
        '        else { m.addLayer(layer); btn.style.opacity="1"; }'
        '      }'
        '    }'
        '  });'
        '}'
        '(function _tagRoutes() {'
        '  setTimeout(function() {'
        '    var m = _findMap(); if(!m) { setTimeout(_tagRoutes, 300); return; }'
        '    var idx = 0;'
        '    m.eachLayer(function(layer) {'
        '      if(layer instanceof L.FeatureGroup && layer.eachLayer) {'
        '        var hasPoly = false;'
        '        layer.eachLayer(function(c) {'
        '          if(c instanceof L.Polyline && c.options && c.options.weight > 2) hasPoly = true;'
        '        });'
        '        if(hasPoly) { layer._routeIdx = idx; idx++; }'
        '      }'
        '    });'
        '  }, 800);'
        '})();'
        '</script>'
    )
    m.get_root().html.add_child(folium.Element(toggle_js))

    # 保存
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    return str(output_path.absolute())