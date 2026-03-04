"""
Gemini Spiral Search Layout Algorithm
提供給 maptoposter 進行 A/B 測試的獨立佈局與繪圖模組
"""

import os
import numpy as np
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
from typing import List, Tuple

# 引入你現有專案的資料結構與工具
from custom_markers import PointMarker, load_custom_points, project_points, calculate_text_size
from advanced_layout import check_overlap

class GeminiLabelPlacer:
    def __init__(self, xlim: Tuple[float, float], ylim: Tuple[float, float], margin: float):
        self.xlim = xlim
        self.ylim = ylim
        self.margin = margin
        self.placed_boxes = []

    def check_collision(self, new_box, marker_pos) -> bool:
        nx, ny, nw, nh = new_box
        mx, my = marker_pos
        
        # 1. 檢查地圖邊界
        if (nx < self.xlim[0] or nx + nw > self.xlim[1] or 
            ny < self.ylim[0] or ny + nh > self.ylim[1]):
            return True
            
        # 2. 檢查是否蓋到橘點本身 (將橘點視為一個包含 margin 的隱形方框)
        marker_box = (mx - self.margin, my - self.margin, self.margin*2, self.margin*2)
        if check_overlap(new_box, marker_box, 0):
            return True

        # 3. 檢查是否與其他已經放置的文字方框重疊
        for placed_box in self.placed_boxes:
            if check_overlap(new_box, placed_box, self.margin):
                return True
                
        return False

def gemini_spiral_layout(markers: List[PointMarker], xlim: Tuple[float, float], ylim: Tuple[float, float], font_properties: FontProperties, margin: float = 20):
    print(f"\n🚀 [Gemini] 啟動螺旋搜尋佈局演算法 ({len(markers)} markers)")
    
    # 1. 事先計算所有文字方框的大小
    for marker in markers:
        name_width, name_height = calculate_text_size(marker.name, font_properties)
        if marker.address:
            addr_font_size = font_properties.get_size() * 0.7
            addr_font = FontProperties(fname=font_properties.get_file() if hasattr(font_properties, 'get_file') else None, size=addr_font_size)
            addr_width, addr_height = calculate_text_size(marker.address, addr_font)
            marker.label_width = max(name_width, addr_width) + 2 * margin
            marker.label_height = name_height + addr_height + 3 * margin
        else:
            marker.label_width = name_width + 2 * margin
            marker.label_height = name_height + 2 * margin

    # 2. 初始化放置器與地圖比例
    placer = GeminiLabelPlacer(xlim, ylim, margin)
    map_width = xlim[1] - xlim[0]
    min_link_length = map_width * 0.015  # 規定文字方框距離橘點的「最短距離」
    max_search_radius = map_width * 0.20 # 搜尋的極限半徑

    # 3. 執行螺旋搜尋
    for marker in markers:
        tw, th = marker.label_width, marker.label_height
        mx, my = marker.map_x, marker.map_y
        
        r = min_link_length
        theta = 0
        theta_step = 0.3  # 角度步進 (越小越密)
        r_step = min_link_length / 4  # 半徑增長速度
        
        placed = False
        while r < max_search_radius:
            cx = mx + r * np.cos(theta)
            cy = my + r * np.sin(theta)
            # 以候選中心點推算左下角坐標
            candidate_box = (cx - tw/2, cy - th/2, tw, th)
            
            if not placer.check_collision(candidate_box, (mx, my)):
                marker.label_x, marker.label_y = candidate_box[0], candidate_box[1]
                placer.placed_boxes.append(candidate_box)
                placed = True
                break
                
            theta += theta_step
            r = min_link_length + (theta / (2*np.pi)) * r_step
            
        if not placed:
            print(f"  ⚠ 空間過於擁擠，略過放置: {marker.name}")
            marker.label_x, marker.label_y = None, None

def draw_gemini_marker(ax, marker: PointMarker, config: dict, font_properties: FontProperties):
    """自定義的繪圖函數：包含八角點連線判斷"""
    if marker.label_x is None: return # 放不下的點就不畫
    
    # 1. 畫橘點
    ax.scatter(marker.map_x, marker.map_y, s=config['marker_size'], c=config['marker_color'], zorder=15, edgecolors='white', linewidths=1.5)
    
    # 2. 八角點最短連線計算
    bx, by = marker.label_x, marker.label_y
    bw, bh = marker.label_width, marker.label_height
    anchors = [
        (bx, by), (bx+bw/2, by), (bx+bw, by), # 下排: 左中右
        (bx, by+bh/2), (bx+bw, by+bh/2),      # 中排: 左右
        (bx, by+bh), (bx+bw/2, by+bh), (bx+bw, by+bh) # 上排: 左中右
    ]
    
    best_dist = float('inf')
    best_anchor = None
    for ax_pt, ay_pt in anchors:
        dist = np.sqrt((marker.map_x - ax_pt)**2 + (marker.map_y - ay_pt)**2)
        if dist < best_dist:
            best_dist = dist
            best_anchor = (ax_pt, ay_pt)
            
    # 畫連線
    ax.plot([marker.map_x, best_anchor[0]], [marker.map_y, best_anchor[1]], color=config['line_color'], linewidth=config['line_width'], zorder=14, alpha=0.7)
    
    # 3. 畫圓角方框與文字
    label_rect = mpatches.FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.01", facecolor=config['label_bg_color'], edgecolor=config['label_border_color'], linewidth=1.5, alpha=config['label_alpha'], zorder=16)
    ax.add_patch(label_rect)
    
    text_x = bx + bw / 2
    if marker.address:
        ax.text(text_x, by + bh * 0.65, marker.name, ha='center', va='center', fontproperties=font_properties, color=config['text_color'], zorder=17, weight='bold')
        addr_font = FontProperties(fname=font_properties.get_file() if hasattr(font_properties, 'get_file') else None, size=font_properties.get_size() * 0.7)
        ax.text(text_x, by + bh * 0.3, marker.address, ha='center', va='center', fontproperties=addr_font, color=config['text_color'], alpha=0.7, zorder=17)
    else:
        ax.text(text_x, by + bh / 2, marker.name, ha='center', va='center', fontproperties=font_properties, color=config['text_color'], zorder=17, weight='bold')

def add_gemini_markers_to_poster(ax, g_proj, json_path: str, font_properties: FontProperties, config: dict):
    """主要的呼叫入口"""
    markers = load_custom_points(json_path)
    if not markers: return
    
    project_points(markers, g_proj.graph['crs'])
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    
    visible_markers = [m for m in markers if xlim[0] <= m.map_x <= xlim[1] and ylim[0] <= m.map_y <= ylim[1]]
    if not visible_markers: return
    
    # 呼叫 Gemini 的螺旋演算法
    gemini_spiral_layout(visible_markers, xlim, ylim, font_properties, margin=config.get('margin', 30))
    
    # 呼叫 Gemini 的繪圖邏輯
    for marker in visible_markers:
        draw_gemini_marker(ax, marker, config, font_properties)