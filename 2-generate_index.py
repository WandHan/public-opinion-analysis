#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成 analysis_results 目录的 JSON 文件索引
用于前端动态加载所有分析结果
"""

import json
import os
from pathlib import Path
from datetime import datetime

def generate_file_index():
    """生成 analysis_results 目录下所有 JSON 文件的索引"""
    
    analysis_dir = Path('./analysis_results')
    
    if not analysis_dir.exists():
        print(f"[ERROR] 目录不存在: {analysis_dir}")
        return
    
    # 获取所有 JSON 文件
    json_files = sorted(
        [f.name for f in analysis_dir.glob('*.json') if f.name != 'files_index.json'],
        reverse=True  # 最新的文件在前面
    )
    
    if not json_files:
        print(f"[WARNING] 在 {analysis_dir} 目录下没有找到 JSON 文件")
        return
    
    # 生成索引数据
    index_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(json_files),
        "files": json_files
    }
    
    # 写入索引文件
    index_file = analysis_dir / 'files_index.json'
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"[SUCCESS] 索引文件已生成: {index_file}")
    print(f"[INFO] 找到 {len(json_files)} 个 JSON 文件:")
    for i, filename in enumerate(json_files, 1):
        file_path = analysis_dir / filename
        file_size = file_path.stat().st_size / 1024  # KB
        print(f"   {i}. {filename} ({file_size:.1f} KB)")

if __name__ == '__main__':
    generate_file_index()

