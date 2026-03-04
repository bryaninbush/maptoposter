#!/bin/bash
# 自動生成的地圖指令

python create_map_poster.py 
  -c "Custom" 
  -C "Taiwan" 
  -lat 24.133689 
  -long 120.663928 
  -d 2000 
  -t terracotta

# 注意：請先修改 create_map_poster.py
# 將 custom_points_path 改成 'selected_points.json'