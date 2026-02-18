"""
Custom Markers Module - 終極優化版 v3

徹底解決：
1. 標籤框太大 → 減少 padding，緊湊佈局
2. 標籤框重疊 → 真正的碰撞檢測 + 位置優化
3. 精確的文字測量和框大小計算
"""

import json
import os
import numpy as np
from typing import List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
from shapely.geometry import Point as ShapelyPoint
import osmnx as ox


class PointMarker:
    """景點標記（含標籤框）"""
    
    def __init__(self, name: str, lat: float, lng: float, address: str = ""):
        self.name = name
        self.lat = lat
        self.lng = lng
        self.address = address
        self.map_x: Optional[float] = None
        self.map_y: Optional[float] = None
        self.label_x: Optional[float] = None
        self.label_y: Optional[float] = None
        self.label_width: Optional[float] = None
        self.label_height: Optional[float] = None


def load_custom_points(json_path: str) -> List[PointMarker]:
    """載入景點資料"""
    if not os.path.exists(json_path):
        print(f"⚠ 找不到檔案: {json_path}")
        return []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    markers = []
    for item in data:
        marker = PointMarker(
            name=item.get('name', 'Unknown'),
            lat=item['lat'],
            lng=item['lng'],
            address=item.get('address', '')
        )
        markers.append(marker)
    
    print(f"✓ 載入 {len(markers)} 個景點")
    return markers


def project_points(markers: List[PointMarker], target_crs: str):
    """座標投影"""
    for marker in markers:
        point = ShapelyPoint(marker.lng, marker.lat)
        projected = ox.projection.project_geometry(
            point, crs="EPSG:4326", to_crs=target_crs
        )[0]
        marker.map_x = projected.x
        marker.map_y = projected.y


def calculate_text_size(text: str, font_properties: FontProperties, ax) -> Tuple[float, float]:
    """
    精確測量文字大小（數據座標）
    """
    temp_text = ax.text(0, 0, text, fontproperties=font_properties, transform=ax.transData)
    ax.figure.canvas.draw()
    bbox = temp_text.get_window_extent(renderer=ax.figure.canvas.get_renderer())
    bbox_data = bbox.transformed(ax.transData.inverted())
    width, height = bbox_data.width, bbox_data.height
    temp_text.remove()
    return width, height


def check_boxes_overlap(box1: Tuple[float, float, float, float],
                        box2: Tuple[float, float, float, float],
                        margin: float = 0) -> bool:
    """
    檢查兩個方框是否重疊
    box format: (x, y, width, height)
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # 加上安全邊距
    x1 -= margin
    y1 -= margin
    w1 += 2 * margin
    h1 += 2 * margin
    
    # 檢查是否重疊
    overlap = not (
        x1 + w1 < x2 or  # box1 在 box2 左邊
        x2 + w2 < x1 or  # box2 在 box1 左邊
        y1 + h1 < y2 or  # box1 在 box2 下方
        y2 + h2 < y1     # box2 在 box1 下方
    )
    
    return overlap


def calculate_label_sizes(markers: List[PointMarker], 
                         font_properties: FontProperties,
                         ax,
                         padding: float = 20):  # ⭐ 減少到 20（原本 100）
    """
    計算所有標籤框的大小
    
    padding: 文字周圍的空白（像 Word 單行間距）
    """
    for marker in markers:
        # 測量名稱大小
        name_w, name_h = calculate_text_size(marker.name, font_properties, ax)
        
        if marker.address:
            # 地址使用較小字體
            addr_font = FontProperties(
                fname=font_properties.get_file() if hasattr(font_properties, 'get_file') else None,
                size=font_properties.get_size() * 0.7
            )
            addr_w, addr_h = calculate_text_size(marker.address, addr_font, ax)
            
            # 兩行：名稱 + 地址
            marker.label_width = max(name_w, addr_w) + padding * 2
            marker.label_height = name_h + addr_h + padding * 3  # 行間距
        else:
            # 單行：只有名稱
            marker.label_width = name_w + padding * 2
            marker.label_height = name_h + padding * 2


def optimize_label_positions(markers: List[PointMarker],
                            xlim: Tuple[float, float],
                            ylim: Tuple[float, float],
                            safety_margin: float = 50):
    """
    優化標籤位置，確保不重疊
    
    演算法：
    1. 為每個標記測試 8 個可能位置（上下左右 + 四個角）
    2. 選擇不重疊且距離其他標籤最遠的位置
    3. 如果無法完全避免重疊，選擇重疊最少的位置
    """
    map_width = xlim[1] - xlim[0]
    map_height = ylim[1] - ylim[0]
    
    # 標籤距離標記點的距離
    offset_dist = min(map_width, map_height) * 0.06  # 增加距離
    
    # 8 個方向（角度）
    angles = [0, 45, 90, 135, 180, 225, 270, 315]  # 度
    
    # 逐個處理標記
    for i, marker in enumerate(markers):
        best_position = None
        best_score = float('inf')  # 越小越好
        
        # 測試每個角度
        for angle_deg in angles:
            angle_rad = np.radians(angle_deg)
            
            # 計算這個角度的標籤位置
            # 標籤中心點
            label_center_x = marker.map_x + offset_dist * np.cos(angle_rad)
            label_center_y = marker.map_y + offset_dist * np.sin(angle_rad)
            
            # 標籤左下角（用於繪製）
            test_x = label_center_x - marker.label_width / 2
            test_y = label_center_y - marker.label_height / 2
            
            # 檢查是否在地圖範圍內
            if (test_x < xlim[0] or test_x + marker.label_width > xlim[1] or
                test_y < ylim[0] or test_y + marker.label_height > ylim[1]):
                continue
            
            # 計算這個位置的得分
            score = 0
            test_box = (test_x, test_y, marker.label_width, marker.label_height)
            
            # 檢查與已放置標籤的重疊
            for j in range(i):
                other_box = (
                    markers[j].label_x,
                    markers[j].label_y,
                    markers[j].label_width,
                    markers[j].label_height
                )
                
                if check_boxes_overlap(test_box, other_box, safety_margin):
                    score += 10000  # 重疊：重罰
                else:
                    # 計算距離（越遠越好）
                    center1_x = test_x + marker.label_width / 2
                    center1_y = test_y + marker.label_height / 2
                    center2_x = markers[j].label_x + markers[j].label_width / 2
                    center2_y = markers[j].label_y + markers[j].label_height / 2
                    
                    dist = np.sqrt((center1_x - center2_x)**2 + (center1_y - center2_y)**2)
                    score += 1000 / (dist + 1)  # 距離越遠，得分越低
            
            # 偏好右邊位置（對於從左到右的語言）
            if np.cos(angle_rad) > 0:
                score -= 100
            
            # 選擇最佳位置
            if score < best_score:
                best_score = score
                best_position = (test_x, test_y)
        
        # 應用最佳位置
        if best_position:
            marker.label_x, marker.label_y = best_position
            print(f"  {marker.name}: 得分 {best_score:.0f}")
        else:
            # 備用：放在右邊
            marker.label_x = marker.map_x + offset_dist
            marker.label_y = marker.map_y - marker.label_height / 2
            print(f"  ⚠ {marker.name}: 使用預設位置")


def draw_marker_and_label(ax, marker: PointMarker,
                          marker_color: str = '#FAA95F',
                          marker_size: float = 80,  # 減小標記
                          label_bg_color: str = '#FFFFFF',
                          label_border_color: str = '#FAA95F',
                          label_alpha: float = 0.95,
                          text_color: str = '#333333',
                          font_properties: FontProperties = None,
                          line_color: str = '#FAA95F',
                          line_width: float = 1.0):
    """繪製標記點、標籤和指示線"""
    
    # 1. 標記點
    ax.scatter(
        marker.map_x, marker.map_y,
        s=marker_size, c=marker_color,
        zorder=12, edgecolors='white', linewidths=1.5
    )
    
    # 2. 指示線
    label_center_x = marker.label_x + marker.label_width / 2
    label_center_y = marker.label_y + marker.label_height / 2
    
    # 連接到標籤框最近的邊
    if label_center_x > marker.map_x:
        line_end_x = marker.label_x
    else:
        line_end_x = marker.label_x + marker.label_width
    line_end_y = label_center_y
    
    ax.plot(
        [marker.map_x, line_end_x],
        [marker.map_y, line_end_y],
        color=line_color, linewidth=line_width,
        zorder=11, alpha=0.7
    )
    
    # 3. 標籤框（圓角矩形）
    label_rect = mpatches.FancyBboxPatch(
        (marker.label_x, marker.label_y),
        marker.label_width, marker.label_height,
        boxstyle="round,pad=0.005",  # ⭐ 減小圓角
        facecolor=label_bg_color,
        edgecolor=label_border_color,
        linewidth=1.2,  # ⭐ 減小邊框寬度
        alpha=label_alpha,
        zorder=11
    )
    ax.add_patch(label_rect)
    
    # 4. 文字
    if font_properties is None:
        font_properties = FontProperties(size=10)
    
    text_x = marker.label_x + marker.label_width / 2
    
    if marker.address:
        # 兩行
        name_y = marker.label_y + marker.label_height * 0.62
        addr_y = marker.label_y + marker.label_height * 0.38
        
        # 名稱
        ax.text(
            text_x, name_y, marker.name,
            ha='center', va='center',
            fontproperties=font_properties,
            color=text_color, zorder=12, weight='bold'
        )
        
        # 地址
        addr_font = FontProperties(
            fname=font_properties.get_file() if hasattr(font_properties, 'get_file') else None,
            size=font_properties.get_size() * 0.7
        )
        ax.text(
            text_x, addr_y, marker.address,
            ha='center', va='center',
            fontproperties=addr_font,
            color=text_color, alpha=0.7, zorder=12
        )
    else:
        # 單行
        text_y = marker.label_y + marker.label_height / 2
        ax.text(
            text_x, text_y, marker.name,
            ha='center', va='center',
            fontproperties=font_properties,
            color=text_color, zorder=12, weight='bold'
        )


def add_custom_markers_to_poster(ax, g_proj, custom_points_json: str,
                                font_properties: FontProperties = None,
                                marker_config: dict = None):
    """
    主函數：添加自定義標記到地圖
    
    ⭐ 終極優化版：
    - 緊湊的標籤框（padding = 20）
    - 真正的碰撞檢測和避免
    - 智能位置優化（8 方向測試）
    """
    if marker_config is None:
        marker_config = {
            'marker_color': '#FAA95F',
            'marker_size': 80,
            'label_bg_color': '#FFFFFF',
            'label_border_color': '#FAA95F',
            'label_alpha': 0.95,
            'text_color': '#333333',
            'line_color': '#FAA95F',
            'line_width': 1.0,
        }
    
    # 載入景點
    markers = load_custom_points(custom_points_json)
    if not markers:
        return
    
    # 投影座標
    project_points(markers, g_proj.graph['crs'])
    
    # 過濾可見標記
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    visible_markers = [
        m for m in markers
        if xlim[0] <= m.map_x <= xlim[1] and ylim[0] <= m.map_y <= ylim[1]
    ]
    
    if not visible_markers:
        print("⚠ 沒有可見的標記")
        return
    
    print(f"✓ {len(visible_markers)} 個標記可見")
    
    # 設定字體
    if font_properties is None:
        font_properties = FontProperties(size=10)
    
    # 🎯 步驟 1: 計算標籤大小（padding = 20，像 Word 單行間距）
    print("📏 計算標籤大小...")
    calculate_label_sizes(visible_markers, font_properties, ax, padding=20)
    
    # 🎯 步驟 2: 優化標籤位置（確保不重疊）
    print("🎯 優化標籤位置（避免重疊）...")
    optimize_label_positions(visible_markers, xlim, ylim, safety_margin=50)
    
    # 🎯 步驟 3: 繪製所有標記
    print("🎨 繪製標記和標籤...")
    for marker in visible_markers:
        draw_marker_and_label(ax, marker, font_properties=font_properties, **marker_config)
    
    # 最終檢查
    overlap_count = 0
    n = len(visible_markers)
    for i in range(n):
        box1 = (visible_markers[i].label_x, visible_markers[i].label_y,
                visible_markers[i].label_width, visible_markers[i].label_height)
        for j in range(i + 1, n):
            box2 = (visible_markers[j].label_x, visible_markers[j].label_y,
                    visible_markers[j].label_width, visible_markers[j].label_height)
            if check_boxes_overlap(box1, box2, margin=0):
                overlap_count += 1
    
    if overlap_count > 0:
        print(f"⚠ 警告: {overlap_count} 對標籤仍有輕微重疊（可能需要增加地圖範圍）")
    else:
        print(f"✓ 完成！所有標籤均無重疊")