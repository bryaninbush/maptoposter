#!/usr/bin/env python3
"""
Smart View Calculator - 智能視圖計算工具

功能：
1. 從 my_custom_points.json 中選擇指定的景點
2. 自動計算最佳中心點座標
3. 自動計算最佳地圖範圍（distance）
4. 生成只包含這些景點的地圖
5. 創建景點清單檔案（只包含選中的景點）

使用方式：
    python smart_view_calculator.py "景點1" "景點2" "景點3"
    
範例：
    python smart_view_calculator.py "湖龍飯店" "某咖啡廳" "阿里山森林遊樂區"
"""

import json
import sys
import math
import os
from typing import List, Tuple, Dict


def load_all_points(json_path: str = "my_custom_points.json") -> List[Dict]:
    """載入所有景點資料"""
    if not os.path.exists(json_path):
        print(f"❌ 找不到檔案: {json_path}")
        sys.exit(1)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_points_by_names(all_points: List[Dict], names: List[str]) -> List[Dict]:
    """根據名稱找到對應的景點"""
    found = []
    not_found = []
    
    for name in names:
        # 模糊匹配（部分符合即可）
        matches = [p for p in all_points if name.lower() in p['name'].lower()]
        
        if matches:
            # 如果有多個匹配，選最接近的
            best_match = min(matches, key=lambda p: len(p['name']))
            found.append(best_match)
            print(f"✓ 找到: {best_match['name']}")
        else:
            not_found.append(name)
            print(f"✗ 找不到: {name}")
    
    if not_found:
        print(f"\n⚠️  以下景點找不到，請檢查名稱:")
        for name in not_found:
            print(f"   - {name}")
        
        # 列出一些可能的選項
        print(f"\n💡 可能的選項（前 20 個）:")
        for i, point in enumerate(all_points[:20], 1):
            print(f"   {i}. {point['name']}")
    
    return found


def calculate_center_and_bounds(points: List[Dict]) -> Tuple[float, float, float]:
    """
    計算最佳中心點和地圖範圍
    
    Returns:
        (center_lat, center_lng, distance_meters)
    """
    if not points:
        raise ValueError("沒有景點可以計算")
    
    # 計算中心點（平均座標）
    lats = [p['lat'] for p in points]
    lngs = [p['lng'] for p in points]
    
    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)
    
    # 計算所需的最小半徑（使用 Haversine 公式）
    max_distance = 0
    for point in points:
        distance = haversine_distance(
            center_lat, center_lng,
            point['lat'], point['lng']
        )
        max_distance = max(max_distance, distance)
    
    # 加上 30% 的 padding，確保所有點都在視圖內且不會太擁擠
    distance_with_padding = max_distance * 1.3
    
    # 設定最小和最大範圍
    min_distance = 2000   # 最小 2km
    max_distance_limit = 50000  # 最大 50km
    
    distance = max(min_distance, min(distance_with_padding, max_distance_limit))
    
    return center_lat, center_lng, distance


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    計算兩個座標之間的距離（公尺）
    使用 Haversine 公式
    """
    R = 6371000  # 地球半徑（公尺）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def save_selected_points(points: List[Dict], output_path: str = "selected_points.json"):
    """儲存選中的景點到新檔案"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(points, f, ensure_ascii=False, indent=2)
    print(f"✓ 已儲存選中的景點到: {output_path}")


def generate_map_command(
    center_lat: float,
    center_lng: float,
    distance: float,
    city: str = "Custom",
    country: str = "Taiwan",
    theme: str = "terracotta",
    use_selected_points: bool = True
) -> str:
    """生成地圖指令"""
    cmd = f"""python create_map_poster.py \\
  -c "{city}" \\
  -C "{country}" \\
  -lat {center_lat:.6f} \\
  -long {center_lng:.6f} \\
  -d {int(distance)} \\
  -t {theme}"""
    
    if use_selected_points:
        cmd += "\n\n# 注意：請先修改 create_map_poster.py"
        cmd += "\n# 將 custom_points_path 改成 'selected_points.json'"
    
    return cmd


def main():
    print("=" * 70)
    print("🎯 智能視圖計算工具")
    print("=" * 70)
    
    # 檢查參數
    if len(sys.argv) < 2:
        print("\n使用方式:")
        print('  python smart_view_calculator.py "景點1" "景點2" "景點3"')
        print('\n範例:')
        print('  python smart_view_calculator.py "湖龍飯店" "某咖啡廳"')
        sys.exit(1)
    
    # 取得景點名稱
    point_names = sys.argv[1:]
    print(f"\n📍 要顯示的景點 ({len(point_names)} 個):")
    for i, name in enumerate(point_names, 1):
        print(f"   {i}. {name}")
    
    # 載入所有景點
    print(f"\n📂 載入景點資料...")
    all_points = load_all_points()
    print(f"   總共 {len(all_points)} 個景點")
    
    # 尋找指定的景點
    print(f"\n🔍 搜尋景點...")
    selected_points = find_points_by_names(all_points, point_names)
    
    if not selected_points:
        print("\n❌ 沒有找到任何景點，請檢查名稱")
        sys.exit(1)
    
    if len(selected_points) < len(point_names):
        print(f"\n⚠️  只找到 {len(selected_points)} 個景點，繼續處理...")
    
    # 計算最佳視圖
    print(f"\n📐 計算最佳視圖...")
    center_lat, center_lng, distance = calculate_center_and_bounds(selected_points)
    
    # 顯示結果
    print("\n" + "=" * 70)
    print("✅ 計算結果")
    print("=" * 70)
    print(f"中心座標: {center_lat:.6f}, {center_lng:.6f}")
    print(f"地圖範圍: {int(distance)} 公尺 ({distance/1000:.2f} 公里)")
    print(f"包含景點: {len(selected_points)} 個")
    
    # 儲存選中的景點
    save_selected_points(selected_points)
    
    # 生成地圖指令
    print("\n" + "=" * 70)
    print("🚀 生成地圖指令")
    print("=" * 70)
    
    cmd = generate_map_command(center_lat, center_lng, distance)
    print(cmd)
    
    # 儲存到檔案
    with open("map_command.sh", 'w', encoding='utf-8') as f:
        f.write("#!/bin/bash\n")
        f.write("# 自動生成的地圖指令\n\n")
        f.write(cmd.replace("\\", ""))
    
    print("\n✓ 指令已儲存到: map_command.sh")
    
    # 顯示景點詳細資訊
    print("\n" + "=" * 70)
    print("📋 選中的景點詳細資訊")
    print("=" * 70)
    for i, point in enumerate(selected_points, 1):
        print(f"\n{i}. {point['name']}")
        print(f"   座標: {point['lat']:.6f}, {point['lng']:.6f}")
        if 'address' in point:
            print(f"   地址: {point.get('address', 'N/A')}")
        
        # 計算距離中心點的距離
        dist_from_center = haversine_distance(
            center_lat, center_lng,
            point['lat'], point['lng']
        )
        print(f"   距中心: {dist_from_center/1000:.2f} 公里")
    
    print("\n" + "=" * 70)
    print("✨ 完成！")
    print("=" * 70)
    print("\n下一步:")
    print("1. 執行上面的地圖指令")
    print("2. 或直接執行: bash map_command.sh")
    print("3. 記得在 create_map_poster.py 中")
    print("   將 custom_points_path 改成 'selected_points.json'")
    print("   或暫時關閉標記功能")


if __name__ == "__main__":
    main()