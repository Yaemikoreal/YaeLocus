from typing import List, Dict, Optional
import folium
from folium.plugins import MarkerCluster, HeatMap
from pathlib import Path


def create_map(
    data: List[Dict],
    output_file: str = "output/地图输出.html",
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
        if item.get("latitude") and item.get("longitude")
    ]

    if not valid_points:
        raise ValueError("没有有效的经纬度数据")

    center_lat = sum(p[0] for p in valid_points) / len(valid_points)
    center_lon = sum(p[1] for p in valid_points) / len(valid_points)

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

        for lat, lon, item in valid_points:
            source = item.get("source", "unknown")
            color = source_colors.get(source, "gray")

            popup_html = f"""
            <b>地址:</b> {item.get("original_address", "N/A")}<br>
            <b>标准化地址:</b> {item.get("formatted_address", "N/A")}<br>
            <b>经纬度:</b> {lat:.6f}, {lon:.6f}<br>
            <b>数据来源:</b> {source}<br>
            <b>坐标系:</b> {item.get("coordinate_system", "N/A")}
            """

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon="info-sign"),
                tooltip=item.get("original_address", "")[:30],
            ).add_to(marker_cluster)

        marker_cluster.add_to(feature_group_markers)
    else:
        for lat, lon, item in valid_points:
            source = item.get("source", "unknown")
            color = source_colors.get(source, "gray")

            popup_html = f"""
            <b>地址:</b> {item.get("original_address", "N/A")}<br>
            <b>标准化地址:</b> {item.get("formatted_address", "N/A")}<br>
            <b>经纬度:</b> {lat:.6f}, {lon:.6f}<br>
            <b>数据来源:</b> {source}<br>
            <b>坐标系:</b> {item.get("coordinate_system", "N/A")}
            """

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon="info-sign"),
                tooltip=item.get("original_address", "")[:30],
            ).add_to(feature_group_markers)

    feature_group_markers.add_to(m)

    if use_heatmap and len(valid_points) > 1:
        heat_data = [[lat, lon] for lat, lon, _ in valid_points]
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

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))

    return str(output_path.absolute())