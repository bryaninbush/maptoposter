import pandas as pd
import googlemaps
import json
import os
import time
from datetime import datetime

# ==================== 配置區 ====================
API_KEY = ''
TARGET_FILES = ["住住.csv", "吃吃.csv", "咖咖.csv", "喝喝.csv", "想去的地點.csv"]

# 取得腳本所在的目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 檔案路徑
CSV_FOLDER = os.path.join(SCRIPT_DIR, "Saved")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "my_custom_points.json")
FAILED_JSON = os.path.join(SCRIPT_DIR, "failed_places.json")

# ==================== 功能開關 ====================
RETRY_FAILED = False           # 是否重試之前失敗的地點
ENABLE_GLOBAL_SEARCH = True    # 啟用全球搜尋（當台灣搜尋失敗時）
UPDATE_EXISTING = True         # 是否更新現有地點的缺失欄位

# ==================== 欄位定義 ====================
# 定義需要從 API 取得的欄位及其提取方法
REQUIRED_FIELDS = {
    'name': {
        'required': True,           # 必要欄位（永遠存在）
        'extract': lambda r: None   # name 來自 CSV，不從 API 提取
    },
    'lat': {
        'required': True,
        'extract': lambda r: r['geometry']['location']['lat'] if r else None
    },
    'lng': {
        'required': True,
        'extract': lambda r: r['geometry']['location']['lng'] if r else None
    },
    'list_type': {
        'required': True,
        'extract': lambda r: None   # 來自檔名，不從 API 提取
    },
    'address': {
        'required': False,          # 選用欄位
        'extract': lambda r: r.get('formatted_address') if r else None
    }
    # 'place_id': {
    #     'required': False,
    #     'extract': lambda r: r.get('place_id') if r else None
    # },
    # 'rating': {
    #     'required': False,
    #     'extract': lambda r: r.get('rating') if r else None
    # },
    # 'user_ratings_total': {
    #     'required': False,
    #     'extract': lambda r: r.get('user_ratings_total') if r else None
    # },
    # 'types': {
    #     'required': False,
    #     'extract': lambda r: r.get('types', []) if r else []
    # },
    # 未來可以輕鬆新增更多欄位，例如：
    # 'phone': {
    #     'required': False,
    #     'extract': lambda r: r.get('formatted_phone_number') if r else None
    # },
    # 'website': {
    #     'required': False,
    #     'extract': lambda r: r.get('website') if r else None
    # },
}

# ==================== Google Maps 初始化 ====================
gmaps = googlemaps.Client(key=API_KEY)

print(f"📁 工作目錄設定:")
print(f"   腳本位置: {SCRIPT_DIR}")
print(f"   CSV 資料夾: {CSV_FOLDER}")
print(f"   成功點位檔: {OUTPUT_JSON}")
print(f"   失敗記錄檔: {FAILED_JSON}")
print(f"\n⚙️  功能設定:")
print(f"   全球搜尋: {'啟用' if ENABLE_GLOBAL_SEARCH else '停用'}")
print(f"   更新現有資料: {'啟用' if UPDATE_EXISTING else '停用'}")
print(f"   重試失敗地點: {'啟用' if RETRY_FAILED else '停用'}")
print()

# ==================== 輔助函數 ====================

def load_failed_history():
    """載入失敗記錄"""
    if os.path.exists(FAILED_JSON):
        with open(FAILED_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_failed_history(failed_dict):
    """儲存失敗記錄"""
    with open(FAILED_JSON, 'w', encoding='utf-8') as f:
        json.dump(failed_dict, f, ensure_ascii=False, indent=2)

def get_missing_fields(point_data):
    """
    檢查某個地點缺少哪些欄位
    
    Args:
        point_data: 地點的資料字典
    
    Returns:
        list: 缺少的欄位名稱列表
    """
    missing = []
    for field_name, field_config in REQUIRED_FIELDS.items():
        # 跳過不從 API 取得的欄位
        if field_config['extract'](None) is None and field_name in ['name', 'list_type']:
            continue
        
        # 檢查欄位是否存在且有值
        if field_name not in point_data or point_data[field_name] is None:
            missing.append(field_name)
    
    return missing

def extract_fields_from_result(api_result, existing_data=None):
    """
    從 API 結果中提取所有定義的欄位
    
    Args:
        api_result: Google Places API 的回應結果
        existing_data: 現有的地點資料（用於保留不需更新的欄位）
    
    Returns:
        dict: 包含所有欄位的字典
    """
    if existing_data is None:
        existing_data = {}
    
    extracted = existing_data.copy()
    
    for field_name, field_config in REQUIRED_FIELDS.items():
        # 保留 name 和 list_type（不從 API 更新）
        if field_name in ['name', 'list_type']:
            continue
        
        # 如果欄位已存在且不需要更新，跳過
        if field_name in extracted and extracted[field_name] is not None:
            continue
        
        # 從 API 結果提取欄位值
        try:
            value = field_config['extract'](api_result)
            if value is not None:
                extracted[field_name] = value
        except Exception as e:
            print(f"      ⚠️  提取欄位 {field_name} 時發生錯誤: {e}")
    
    return extracted

def search_place_with_fallback(name, gmaps_client):
    """
    兩階段搜尋：先台灣，失敗後全球
    
    Args:
        name: 地點名稱
        gmaps_client: Google Maps 客戶端
    
    Returns:
        tuple: (result, search_type)
            - result: API 回應結果
            - search_type: 'taiwan' | 'global' | None
    """
    # 第一階段：台灣搜尋
    try:
        result = gmaps_client.places(query=f"{name} 台灣", language='zh-TW')
        if result['status'] == 'OK':
            return result['results'][0], 'taiwan'
    except Exception as e:
        print(f"      ⚠️  台灣搜尋發生錯誤: {e}")
    
    # 第二階段：全球搜尋（如果啟用）
    if ENABLE_GLOBAL_SEARCH:
        try:
            time.sleep(0.1)  # 避免太頻繁
            result = gmaps_client.places(query=name, language='zh-TW')
            if result['status'] == 'OK':
                return result['results'][0], 'global'
        except Exception as e:
            print(f"      ⚠️  全球搜尋發生錯誤: {e}")
    
    return None, None

# ==================== 主程式 ====================

def fetch_all_coords():
    # 載入已成功的點位
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            all_points = json.load(f)
        print(f"📂 載入現有成功點位: {len(all_points)} 個")
    else:
        all_points = []
        print(f"📂 尚無成功點位記錄")

    # 建立名稱索引（用於快速查找）
    points_by_name = {p['name']: p for p in all_points}
    
    # 載入失敗記錄
    failed_history = load_failed_history()
    print(f"📂 載入失敗記錄: {len(failed_history)} 個")
    
    # ==================== 階段 1: 檢查現有資料缺失欄位 ====================
    if UPDATE_EXISTING and all_points:
        print("\n" + "="*70)
        print("🔍 階段 1: 檢查現有資料缺失欄位")
        print("="*70)
        
        points_need_update = []
        for point in all_points:
            missing = get_missing_fields(point)
            if missing:
                points_need_update.append((point, missing))
        
        if points_need_update:
            print(f"發現 {len(points_need_update)} 個地點需要更新")
            print(f"\n是否要更新這些地點的資訊？ (會消耗 API quota)")
            
            # 顯示部分範例
            for i, (point, missing) in enumerate(points_need_update[:5], 1):
                print(f"  {i}. {point['name']} - 缺少: {', '.join(missing)}")
            if len(points_need_update) > 5:
                print(f"  ... 還有 {len(points_need_update) - 5} 個地點")
            
            # 這裡可以加入互動式確認，或直接執行
            print(f"\n開始更新 {len(points_need_update)} 個地點...")
            
            update_success = 0
            update_failed = 0
            
            for point, missing in points_need_update:
                print(f"\n  🔄 更新: {point['name']} (缺少: {', '.join(missing)})")
                
                # 使用兩階段搜尋
                api_result, search_type = search_place_with_fallback(point['name'], gmaps)
                
                if api_result:
                    # 更新欄位
                    updated_point = extract_fields_from_result(api_result, point)
                    points_by_name[point['name']] = updated_point
                    
                    # 顯示新增了哪些欄位
                    newly_added = get_missing_fields(point)
                    newly_filled = [f for f in newly_added if f not in get_missing_fields(updated_point)]
                    
                    update_success += 1
                    region = "🇹🇼 台灣" if search_type == 'taiwan' else "🌍 全球"
                    print(f"      ✅ 更新成功 ({region}) - 新增: {', '.join(newly_filled)}")
                else:
                    update_failed += 1
                    print(f"      ❌ 更新失敗 - 無法找到地點")
                
                time.sleep(0.1)
            
            # 更新 all_points 列表
            all_points = list(points_by_name.values())
            
            print(f"\n📊 更新結果: 成功 {update_success} 個, 失敗 {update_failed} 個")
        else:
            print("✅ 所有現有地點資料完整，無需更新")
    
    # ==================== 階段 2: 處理 CSV 中的地點 ====================
    print("\n" + "="*70)
    print("🔍 階段 2: 處理 CSV 中的地點")
    print("="*70)
    
    # 統計變數
    total_in_csv = 0
    total_already_complete = 0
    total_skip_failed = 0
    total_retry = 0
    total_new_success = 0
    total_taiwan_search = 0
    total_global_search = 0
    total_new_failed = 0
    
    current_run_failed = {}

    for file_name in TARGET_FILES:
        path = os.path.join(CSV_FOLDER, file_name)
        if not os.path.exists(path): 
            print(f"⚠️  檔案不存在: {path}")
            continue
        
        print(f"\n📋 正在處理清單: {file_name}")
        print("-" * 70)
        
        df = pd.read_csv(path, skiprows=1, encoding='utf-8-sig').dropna(subset=['Titles'])
        
        for _, row in df.iterrows():
            name = row['Titles']
            total_in_csv += 1
            
            # 情況 1: 已存在且資料完整
            if name in points_by_name:
                existing_point = points_by_name[name]
                missing = get_missing_fields(existing_point)
                
                if not missing:
                    total_already_complete += 1
                    print(f"  ✅ [資料完整] {name}")
                    continue
                else:
                    # 這個情況在階段 1 應該已經處理過了
                    # 但以防萬一還是顯示一下
                    print(f"  ℹ️  [已存在但不完整] {name} - 缺少: {', '.join(missing)}")
                    continue
            
            # 情況 2: 之前失敗過
            if name in failed_history:
                if not RETRY_FAILED:
                    total_skip_failed += 1
                    fail_count = failed_history[name]['fail_count']
                    print(f"  ⏭️  [跳過失敗] {name} (已失敗 {fail_count} 次)")
                    continue
                else:
                    total_retry += 1
                    print(f"  🔄 [重試] {name}")
            
            # 情況 3: 新地點或重試 - 使用兩階段搜尋
            print(f"  🔍 [查詢] {name}")
            
            try:
                api_result, search_type = search_place_with_fallback(name, gmaps)
                
                if api_result:
                    # 建立新的點位資料
                    new_point = {
                        'name': name,
                        'list_type': file_name.replace('.csv', '')
                    }
                    
                    # 提取所有欄位
                    new_point = extract_fields_from_result(api_result, new_point)
                    
                    # 加入清單
                    all_points.append(new_point)
                    points_by_name[name] = new_point
                    total_new_success += 1
                    
                    # 統計搜尋類型
                    if search_type == 'taiwan':
                        total_taiwan_search += 1
                        region_icon = "🇹🇼"
                        region_text = "台灣"
                    else:
                        total_global_search += 1
                        region_icon = "🌍"
                        region_text = "全球"
                    
                    # 如果之前失敗過，現在成功了，從失敗記錄中移除
                    if name in failed_history:
                        del failed_history[name]
                        print(f"      🎉 [重試成功] {region_icon} {region_text}搜尋 - {new_point.get('address', '無地址')}")
                    else:
                        print(f"      ✅ [新增成功] {region_icon} {region_text}搜尋 - {new_point.get('address', '無地址')}")
                else:
                    # 兩階段搜尋都失敗
                    total_new_failed += 1
                    
                    search_attempt = "台灣搜尋"
                    if ENABLE_GLOBAL_SEARCH:
                        search_attempt += " + 全球搜尋"
                    
                    if name in failed_history:
                        failed_history[name]['fail_count'] += 1
                        failed_history[name]['last_attempt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        failed_history[name]['search_type'] = search_attempt
                    else:
                        failed_history[name] = {
                            'fail_count': 1,
                            'first_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'last_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'search_type': search_attempt,
                            'source_file': file_name
                        }
                    
                    current_run_failed[name] = failed_history[name]
                    print(f"      ❌ [查詢失敗] {search_attempt}都找不到")
                
                time.sleep(0.1)
                
            except Exception as e:
                total_new_failed += 1
                
                if name in failed_history:
                    failed_history[name]['fail_count'] += 1
                    failed_history[name]['last_attempt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    failed_history[name]['last_error'] = str(e)
                else:
                    failed_history[name] = {
                        'fail_count': 1,
                        'first_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'last_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'last_error': str(e),
                        'source_file': file_name
                    }
                
                current_run_failed[name] = failed_history[name]
                print(f"      ❌ [查詢錯誤] {e}")

    # ==================== 儲存結果 ====================
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_points, f, ensure_ascii=False, indent=2)
    
    save_failed_history(failed_history)
    
    # ==================== 執行摘要 ====================
    print("\n" + "="*70)
    print("📊 執行摘要")
    print("="*70)
    print(f"CSV 中總地點數: {total_in_csv}")
    print(f"├─ ✅ 資料完整 (跳過): {total_already_complete}")
    print(f"├─ ⏭️  曾失敗 (跳過): {total_skip_failed}")
    print(f"├─ 🔄 重試次數: {total_retry}")
    print(f"├─ 🎉 新增成功: {total_new_success}")
    if total_new_success > 0:
        print(f"│  ├─ 🇹🇼 台灣搜尋: {total_taiwan_search}")
        print(f"│  └─ 🌍 全球搜尋: {total_global_search}")
    print(f"└─ ❌ 本次失敗: {total_new_failed}")
    
    print(f"\n目前狀態:")
    print(f"✅ 成功點位總數: {len(all_points)}")
    print(f"❌ 失敗記錄總數: {len(failed_history)}")
    
    # 分析資料完整度
    complete_count = sum(1 for p in all_points if not get_missing_fields(p))
    incomplete_count = len(all_points) - complete_count
    
    if incomplete_count > 0:
        print(f"\n📋 資料完整度:")
        print(f"✅ 完整資料: {complete_count} 個")
        print(f"⚠️  不完整資料: {incomplete_count} 個")
        print(f"   💡 下次執行時可設定 UPDATE_EXISTING=True 來補齊")
    
    # 失敗地點詳細資訊
    if current_run_failed:
        print(f"\n" + "="*70)
        print(f"❌ 本次執行失敗的地點 ({len(current_run_failed)} 個):")
        print("-" * 70)
        for i, (name, info) in enumerate(sorted(current_run_failed.items()), 1):
            print(f"{i}. {name}")
            print(f"   失敗次數: {info['fail_count']}")
            print(f"   搜尋範圍: {info.get('search_type', 'N/A')}")
    
    if failed_history:
        print(f"\n💡 提示:")
        if not RETRY_FAILED:
            print(f"   - 設定 RETRY_FAILED=True 可重試失敗的地點")
        if not ENABLE_GLOBAL_SEARCH:
            print(f"   - 設定 ENABLE_GLOBAL_SEARCH=True 啟用全球搜尋")
        if incomplete_count > 0:
            print(f"   - 設定 UPDATE_EXISTING=True 補齊不完整的資料")
    
    print(f"\n✅ 資料已儲存:")
    print(f"   - 成功點位: {OUTPUT_JSON}")
    print(f"   - 失敗記錄: {FAILED_JSON}")

if __name__ == "__main__":
    fetch_all_coords()