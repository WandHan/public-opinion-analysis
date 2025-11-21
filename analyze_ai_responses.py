#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛力斯/问界 AI声誉分析工具
根据品牌价值理解与声誉安全框架分析AI回答
"""

import csv
import json
import os
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
import glob
import time
from json_repair import repair_json
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

# ==================== 加载环境变量 ====================
load_dotenv()  # 从.env文件加载环境变量

# ==================== 配置 ====================
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.tu-zi.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-5-20250929")
API_KEY = os.environ.get("API_KEY", "")  # 从.env文件读取API密钥

# ==================== 初始化客户端 ====================
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY
)

# ==================== 读取分析框架 ====================
def load_analysis_framework():
    """加载分析框架文档内容"""
    framework_path = "ref_md/基于品牌价值理解与声誉安全的AI内容分析框架_20251119.md"
    with open(framework_path, 'r', encoding='utf-8') as f:
        return f.read()

def load_output_framework():
    """加载输出框架文档内容"""
    output_path = "ref_md/赛力斯_问界AI声誉分析结果框架设计（用于生成网页）.md"
    with open(output_path, 'r', encoding='utf-8') as f:
        return f.read()

# ==================== 构建分析提示词 ====================
def build_analysis_prompt(analysis_framework: str, output_framework: str, 
                          question: str, ai_response: str, platform: str) -> str:
    """构建用于AI分析的提示词"""
    
    prompt = f"""你是一位品牌声誉管理和AI内容分析专家。

# 任务说明
请基于以下【分析框架】，对某AI平台针对"赛力斯/问界"品牌的回答进行深度分析。

# 分析框架
{analysis_framework}

# 输出要求
请严格按照以下【输出框架】生成JSON格式的分析结果：
{output_framework}

# 待分析数据
- **平台**: {platform}
- **用户提问**: {question}
- **AI回答**: 
{ai_response}

# 输出格式要求（非常重要！）
请直接输出一个**严格标准**的JSON对象，不要添加任何其他文字、注释或说明。

JSON格式如下（请确保所有引号、逗号、括号完全匹配）：

{{
  "Platform": "{platform}",
  "User_Query": "用户提问原文",
  "AI_Response": "AI回答原文",
  "Security_Status": "🔴高危 / 🟡预警 / 🟢安全 (必须三选一)",
  "Risk_Diagnosis": "风险诊断说明（如：语义投毒、谣言放大、恶意关联等，无风险则写无明显风险）",
  "Fact_Tech": "事实与技术评估（准确性、是否使用官方技术词汇等）",
  "Brand_Impression": "品牌印象评分（1-5分）及简评（是否有品格感、关怀度、温度）",
  "Comp_Position": "🏆优势 / 🛡️均势 / 📉劣势 (必须三选一)",
  "Strategy_Action": "详细的行动建议和优化策略（500字左右，体现专业的品牌管理能力）"
}}

关键要求：
1. 分析犀利、客观、深入，基于5C+1S框架进行全方位评估
2. 特别关注声誉安全问题（数据投毒、谣言、恶意关联）
3. 行动建议要具体、可执行
4. **输出必须是纯JSON格式，不要用```json```包裹，不要添加任何解释**
5. **所有字符串值内如有引号请用中文引号「」或转义**
6. **确保JSON格式完全正确，可以被标准JSON解析器解析**
"""
    
    return prompt

# ==================== 智能JSON提取与修复 ====================
def extract_and_parse_json(text: str) -> Dict:
    """智能提取并解析JSON，支持多种格式和自动修复"""
    
    # 策略1: 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 策略2: 提取代码块中的JSON
    if "```json" in text:
        try:
            json_text = text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_text)
        except:
            pass
    
    if "```" in text:
        try:
            json_text = text.split("```")[1].split("```")[0].strip()
            return json.loads(json_text)
        except:
            pass
    
    # 策略3: 查找第一个 { 到最后一个 } 之间的内容
    try:
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            json_text = text[first_brace:last_brace+1]
            return json.loads(json_text)
    except:
        pass
    
    # 策略4: 使用 json-repair 修复损坏的JSON
    try:
        # 先尝试提取可能的JSON部分
        json_candidates = [text]
        
        if "```json" in text:
            json_candidates.append(text.split("```json")[1].split("```")[0].strip())
        
        if "```" in text:
            json_candidates.append(text.split("```")[1].split("```")[0].strip())
        
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            json_candidates.append(text[first_brace:last_brace+1])
        
        # 对每个候选尝试修复
        for candidate in json_candidates:
            try:
                repaired = repair_json(candidate)
                result = json.loads(repaired)
                print("✓ JSON已自动修复")
                return result
            except:
                continue
    except:
        pass
    
    # 所有策略都失败
    raise ValueError("无法提取或修复JSON")

# ==================== 调用AI进行分析（带重试机制）====================
def analyze_single_response(question: str, ai_response: str, platform: str,
                            analysis_framework: str, output_framework: str,
                            max_retries: int = 3) -> Dict:
    """对单条AI回答进行分析，支持失败重试"""
    
    print(f"\n正在分析: 平台={platform}, 问题=【{question[:50]}...】")
    
    prompt = build_analysis_prompt(analysis_framework, output_framework, 
                                   question, ai_response, platform)
    
    # 重试机制
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"  第 {attempt + 1} 次尝试...")
                time.sleep(2)  # 重试前等待2秒
            
            # 调用AI
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 使用智能JSON提取与修复
            result = extract_and_parse_json(result_text)
            
            # 验证必要字段
            required_fields = ['Platform', 'User_Query', 'AI_Response', 'Security_Status']
            if all(field in result for field in required_fields):
                print(f"✓ 分析完成: 安全状态={result.get('Security_Status', 'N/A')}")
                return result
            else:
                missing = [f for f in required_fields if f not in result]
                raise ValueError(f"缺少必要字段: {missing}")
        
        except Exception as e:
            error_msg = str(e)
            print(f"✗ 尝试 {attempt + 1} 失败: {error_msg}")
            
            # 如果是最后一次尝试，返回错误结果
            if attempt == max_retries - 1:
                print(f"✗ 已达到最大重试次数，分析失败")
                if 'result_text' in locals():
                    print(f"原始回复前500字符: {result_text[:500]}...")
                
                return {
                    "Platform": platform,
                    "User_Query": question,
                    "AI_Response": ai_response,
                    "Security_Status": "⚠️ 分析失败",
                    "Risk_Diagnosis": f"解析错误（已重试{max_retries}次）: {error_msg}",
                    "Fact_Tech": "N/A",
                    "Brand_Impression": "N/A",
                    "Comp_Position": "N/A",
                    "Strategy_Action": "需要手动检查原始回复"
                }
    
    # 理论上不会到这里，但以防万一
    return {
        "Platform": platform,
        "User_Query": question,
        "AI_Response": ai_response,
        "Security_Status": "⚠️ 分析失败",
        "Risk_Diagnosis": "未知错误",
        "Fact_Tech": "N/A",
        "Brand_Impression": "N/A",
        "Comp_Position": "N/A",
        "Strategy_Action": "需要手动检查"
    }

# ==================== 断点续传功能 ====================
PROGRESS_FILE = ".analysis_progress.json"

def save_progress(csv_path: str, total: int, processed: int, results: List[Dict], 
                  start_time: str, rows_data: List[Dict]):
    """保存处理进度"""
    progress_data = {
        "csv_file": csv_path,
        "csv_file_abs": os.path.abspath(csv_path),
        "start_time": start_time,
        "total": total,
        "processed": processed,
        "results": results,
        "rows_data": rows_data,  # 保存所有行数据，以便恢复
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)

def load_progress() -> Optional[Dict]:
    """加载未完成的进度"""
    if not os.path.exists(PROGRESS_FILE):
        return None
    
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  无法加载进度文件: {e}")
        return None

def clear_progress():
    """清除进度文件"""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("✓ 进度文件已清除")

def check_unfinished_task() -> Optional[Dict]:
    """检查是否有未完成的任务"""
    progress = load_progress()
    
    if progress is None:
        return None
    
    # 检查CSV文件是否还存在
    csv_file = progress.get('csv_file', '')
    if not os.path.exists(csv_file):
        print(f"⚠️  原CSV文件 {csv_file} 不存在，忽略进度")
        clear_progress()
        return None
    
    # 检查是否已完成
    if progress.get('processed', 0) >= progress.get('total', 0):
        print("⚠️  进度文件显示任务已完成，将清除进度")
        clear_progress()
        return None
    
    return progress

# ==================== 读取CSV并批量分析 ====================
def analyze_csv_data(csv_path: str = "数据表.csv", resume_progress: Optional[Dict] = None) -> List[Dict]:
    """读取CSV数据并进行批量分析，支持断点续传
    
    Args:
        csv_path: CSV文件路径
        resume_progress: 要恢复的进度数据（如果提供）
    """
    
    # 加载框架
    print("正在加载分析框架...")
    analysis_framework = load_analysis_framework()
    output_framework = load_output_framework()
    print("✓ 框架加载完成")
    
    # 判断是否从断点恢复
    if resume_progress:
        print(f"\n从断点恢复处理...")
        start_time = resume_progress.get('start_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        results = resume_progress.get('results', [])
        rows = resume_progress.get('rows_data', [])
        start_idx = resume_progress.get('processed', 0)
        total = len(rows)
        
        print(f"✓ 已完成 {start_idx}/{total} 条")
        print(f"✓ 将从第 {start_idx + 1} 条开始继续处理\n")
    else:
        # 全新开始
        print(f"\n正在读取CSV文件: {csv_path}")
        results = []
        start_idx = 0
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total = len(rows)
        
        print(f"✓ 共找到 {total} 条数据\n")
    
    print("=" * 80)
    
    try:
        for idx in range(start_idx, len(rows)):
            row = rows[idx]
            current_idx = idx + 1
            
            print(f"\n[{current_idx}/{total}] 处理中...")
            
            question = row.get('问题', '')
            ai_response = row.get('回答', '')
            platform = row.get('AI平台', '')
            
            if not question or not ai_response:
                print("⚠️  跳过空数据")
                # 即使跳过也要保存进度
                save_progress(csv_path, total, current_idx, results, start_time, rows)
                continue
            
            # 调用AI分析
            analysis_result = analyze_single_response(
                question=question,
                ai_response=ai_response,
                platform=platform,
                analysis_framework=analysis_framework,
                output_framework=output_framework
            )
            
            # 添加原始数据的序号和填写人信息
            analysis_result['序号'] = row.get('序号', current_idx)
            analysis_result['填写人'] = row.get('填写人', '')
            
            results.append(analysis_result)
            
            # 每处理完一条就保存进度
            save_progress(csv_path, total, current_idx, results, start_time, rows)
            print(f"✓ 进度已保存 ({current_idx}/{total})")
            
            print("-" * 80)
        
        # 全部完成后清除进度文件
        clear_progress()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  检测到中断信号 (Ctrl+C)")
        print(f"✓ 进度已保存！已完成 {len(results)}/{total} 条")
        print(f"✓ 下次运行时可以选择从断点继续")
        raise
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        print(f"✓ 进度已保存！已完成 {len(results)}/{total} 条")
        print(f"✓ 修复问题后可以从断点继续")
        raise
    
    return results

# ==================== 列出CSV文件 ====================
def list_csv_files() -> List[str]:
    """列出当前目录下所有CSV文件"""
    
    csv_files = glob.glob("*.csv")
    csv_files.sort()
    
    return csv_files

def select_csv_file() -> Optional[str]:
    """让用户通过图形化对话框选择CSV文件"""
    
    print("\n正在打开文件选择对话框...")
    
    try:
        # 创建一个隐藏的Tkinter根窗口
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes('-topmost', True)  # 确保对话框在最前面
        
        # 获取当前工作目录
        initial_dir = os.getcwd()
        
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="请选择CSV文件 / Select CSV File",
            initialdir=initial_dir,
            filetypes=[
                ("CSV文件", "*.csv"),
                ("所有文件", "*.*")
            ]
        )
        
        # 销毁Tkinter根窗口
        root.destroy()
        
        if file_path:
            print(f"✓ 已选择文件: {os.path.basename(file_path)}")
            
            # 显示文件信息
            try:
                file_size = os.path.getsize(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    row_count = sum(1 for row in reader) - 1  # 减去表头
                    
                print(f"   数据行数: {row_count} 行 | 大小: {file_size/1024:.1f} KB")
            except Exception as e:
                print(f"   (无法读取文件信息: {e})")
            
            return file_path
        else:
            print("⚠️  未选择文件")
            return None
            
    except Exception as e:
        print(f"⚠️  无法打开文件选择对话框: {e}")
        print("   正在切换到命令行模式...")
        
        # 如果GUI失败，回退到命令行模式
        csv_files = list_csv_files()
        
        if not csv_files:
            print("\n⚠️  当前目录下未找到任何CSV文件")
            return None
        
        print("\n找到以下CSV文件：")
        print("-" * 80)
        for idx, filepath in enumerate(csv_files, 1):
            file_size = os.path.getsize(filepath)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    row_count = sum(1 for row in reader) - 1
                    
                print(f"{idx}. {filepath}")
                print(f"   数据行数: {row_count} 行 | 大小: {file_size/1024:.1f} KB")
                print()
            except:
                print(f"{idx}. {filepath}")
                print(f"   大小: {file_size/1024:.1f} KB")
                print()
        
        print("-" * 80)
        
        while True:
            choice = input(f"\n请选择CSV文件序号 (1-{len(csv_files)}) 或输入 0 返回: ").strip()
            
            if choice == '0':
                return None
            
            try:
                idx = int(choice)
                if 1 <= idx <= len(csv_files):
                    return csv_files[idx - 1]
                else:
                    print(f"⚠️  请输入 1 到 {len(csv_files)} 之间的数字")
            except ValueError:
                print("⚠️  无效输入，请输入数字")

# ==================== 列出已有的分析结果 ====================
def list_analysis_results(output_dir: str = "analysis_results") -> List[str]:
    """列出所有已完成的分析结果JSON文件"""
    
    if not os.path.exists(output_dir):
        return []
    
    pattern = os.path.join(output_dir, "ai_reputation_analysis_*.json")
    files = glob.glob(pattern)
    files.sort(reverse=True)  # 最新的在前面
    
    return files

# ==================== 读取已有的分析结果 ====================
def load_analysis_results(filepath: str) -> List[Dict]:
    """读取已有的分析结果JSON文件"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

# ==================== 查找失败的分析 ====================
def find_failed_analyses(results: List[Dict]) -> List[int]:
    """找出所有分析失败的条目索引"""
    
    failed_indices = []
    for idx, result in enumerate(results):
        if result.get('Security_Status') == '⚠️ 分析失败':
            failed_indices.append(idx)
    
    return failed_indices

# ==================== 重新分析失败的条目 ====================
def reanalyze_failed_items(results: List[Dict], failed_indices: List[int],
                           analysis_framework: str, output_framework: str) -> List[Dict]:
    """重新分析失败的条目"""
    
    if not failed_indices:
        print("✓ 没有发现失败的分析条目")
        return results
    
    print(f"\n发现 {len(failed_indices)} 条分析失败的数据，开始重新分析...")
    print("=" * 80)
    
    for idx, failed_idx in enumerate(failed_indices, 1):
        result = results[failed_idx]
        
        print(f"\n[{idx}/{len(failed_indices)}] 重新分析索引 {failed_idx}...")
        print(f"平台: {result.get('Platform', 'N/A')}")
        print(f"问题: {result.get('User_Query', '')[:50]}...")
        
        # 重新分析
        new_result = analyze_single_response(
            question=result.get('User_Query', ''),
            ai_response=result.get('AI_Response', ''),
            platform=result.get('Platform', ''),
            analysis_framework=analysis_framework,
            output_framework=output_framework
        )
        
        # 保留原有的序号和填写人信息
        new_result['序号'] = result.get('序号', '')
        new_result['填写人'] = result.get('填写人', '')
        
        # 更新结果
        results[failed_idx] = new_result
        
        print("-" * 80)
    
    return results

# ==================== 保存结果 ====================
def save_results(results: List[Dict], output_dir: str = "analysis_results", 
                 filepath: Optional[str] = None, csv_filename: Optional[str] = None):
    """保存分析结果到JSON文件
    
    Args:
        results: 分析结果列表
        output_dir: 输出目录
        filepath: 完整的输出文件路径（如果提供，则直接使用）
        csv_filename: CSV源文件名（用于生成JSON文件名）
    """
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 如果提供了filepath，则覆盖原文件；否则创建新文件
    if filepath is None:
        if csv_filename:
            # 基于CSV文件名生成JSON文件名
            base_name = os.path.splitext(os.path.basename(csv_filename))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base_name}_analysis_{timestamp}.json"
        else:
            # 使用默认文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ai_reputation_analysis_{timestamp}.json"
        
        filepath = os.path.join(output_dir, filename)
    
    # 保存JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✓ 分析完成！结果已保存至: {filepath}")
    print(f"✓ 共分析 {len(results)} 条数据")
    
    # 统计安全状态
    security_stats = {}
    for result in results:
        status = result.get('Security_Status', 'Unknown')
        security_stats[status] = security_stats.get(status, 0) + 1
    
    print(f"\n安全状态统计:")
    for status, count in security_stats.items():
        print(f"  {status}: {count} 条")
    
    print(f"{'='*80}\n")
    
    return filepath

# ==================== 显示菜单并获取用户选择 ====================
def show_menu(has_unfinished: bool = False) -> str:
    """显示主菜单并返回用户选择"""
    print("\n请选择操作模式：")
    
    if has_unfinished:
        print("⚡ 发现未完成的任务！")
        print("R. 从断点继续未完成的任务 (推荐)")
        print("-" * 40)
    
    print("1. 从CSV文件开始新的分析")
    print("2. 选择已有的分析结果进行补足（重新分析失败的条目）")
    print("0. 退出")
    
    valid_choices = ['0', '1', '2']
    if has_unfinished:
        valid_choices.append('r')
        valid_choices.append('R')
    
    while True:
        if has_unfinished:
            choice = input("\n请输入选项 (R/0/1/2): ").strip()
        else:
            choice = input("\n请输入选项 (0/1/2): ").strip()
        
        if choice.lower() in [c.lower() for c in valid_choices]:
            return choice.upper() if choice.upper() == 'R' else choice
        
        if has_unfinished:
            print("⚠️  无效输入，请输入 R、0、1 或 2")
        else:
            print("⚠️  无效输入，请输入 0、1 或 2")

def select_json_file() -> Optional[str]:
    """让用户选择已有的JSON文件"""
    
    # 列出所有分析结果文件
    files = list_analysis_results()
    
    if not files:
        print("\n⚠️  未找到任何已有的分析结果文件")
        return None
    
    print("\n找到以下分析结果文件：")
    print("-" * 80)
    for idx, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        
        # 读取文件统计信息
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_count = len(data)
                failed_count = sum(1 for item in data if item.get('Security_Status') == '⚠️ 分析失败')
                
            print(f"{idx}. {filename}")
            print(f"   数据总数: {total_count} 条 | 失败: {failed_count} 条 | 大小: {file_size/1024:.1f} KB")
            print()
        except:
            print(f"{idx}. {filename}")
            print(f"   大小: {file_size/1024:.1f} KB")
            print()
    
    print("-" * 80)
    
    while True:
        choice = input(f"\n请选择文件序号 (1-{len(files)}) 或输入 0 返回: ").strip()
        
        if choice == '0':
            return None
        
        try:
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
            else:
                print(f"⚠️  请输入 1 到 {len(files)} 之间的数字")
        except ValueError:
            print("⚠️  无效输入，请输入数字")

# ==================== 主函数 ====================
def main():
    """主函数"""
    print("\n" + "="*80)
    print("赛力斯/问界 AI声誉分析工具 (支持断点续传)".center(80))
    print("="*80 + "\n")
    
    # 检查API密钥
    if API_KEY == "your-api-key-here":
        print("⚠️  警告: 请设置环境变量 OPENAI_API_KEY 或在代码中配置API密钥")
        print("   export OPENAI_API_KEY='your-actual-api-key'\n")
        return
    
    try:
        # 检查未完成的任务
        unfinished_progress = check_unfinished_task()
        
        if unfinished_progress:
            print("=" * 80)
            print("⚡ 发现未完成的任务！")
            print("=" * 80)
            print(f"CSV文件: {unfinished_progress.get('csv_file', 'N/A')}")
            print(f"开始时间: {unfinished_progress.get('start_time', 'N/A')}")
            print(f"总数据量: {unfinished_progress.get('total', 0)} 条")
            print(f"已完成: {unfinished_progress.get('processed', 0)} 条")
            print(f"剩余: {unfinished_progress.get('total', 0) - unfinished_progress.get('processed', 0)} 条")
            print(f"上次更新: {unfinished_progress.get('last_update', 'N/A')}")
            print("=" * 80)
        
        # 显示菜单
        choice = show_menu(has_unfinished=bool(unfinished_progress))
        
        if choice == '0':
            print("\n再见！")
            return
        
        elif choice == 'R':
            # 模式R: 从断点继续
            print("\n" + "="*80)
            print("模式R: 从断点继续未完成的任务")
            print("="*80)
            
            if not unfinished_progress:
                print("⚠️  没有未完成的任务")
                return
            
            csv_file = unfinished_progress.get('csv_file', '')
            
            # 从断点继续分析
            results = analyze_csv_data(csv_file, resume_progress=unfinished_progress)
            
            # 保存结果
            output_file = save_results(results, csv_filename=csv_file)
            
            print("✓ 所有任务完成！")
            print(f"下一步: 可以将 {output_file} 中的数据整合到 index.html 中展示")
        
        elif choice == '1':
            # 模式1: 从CSV开始新的分析
            print("\n" + "="*80)
            print("模式1: 从CSV文件开始新的分析")
            print("="*80)
            
            # 如果有未完成的任务，警告用户
            if unfinished_progress:
                print("\n⚠️  警告: 开始新任务将会覆盖当前未完成的进度！")
                confirm = input("是否确认开始新任务？(y/n): ").strip().lower()
                if confirm != 'y':
                    print("\n操作已取消")
                    return
                clear_progress()
            
            # 让用户选择CSV文件
            csv_file = select_csv_file()
            
            if csv_file is None:
                print("\n⚠️  未选择CSV文件，退出")
                return
            
            print(f"\n已选择CSV文件: {csv_file}")
            
            # 分析CSV数据
            results = analyze_csv_data(csv_file)
            
            # 保存结果（使用CSV文件名作为基础名称）
            output_file = save_results(results, csv_filename=csv_file)
            
            print("✓ 所有任务完成！")
            print(f"下一步: 可以将 {output_file} 中的数据整合到 index.html 中展示")
        
        elif choice == '2':
            # 模式2: 选择已有JSON并补足失败的分析
            print("\n" + "="*80)
            print("模式2: 补足已有分析结果中的失败条目")
            print("="*80)
            
            # 选择文件
            selected_file = select_json_file()
            
            if selected_file is None:
                print("\n⚠️  未选择文件，退出")
                return
            
            print(f"\n已选择文件: {os.path.basename(selected_file)}")
            
            # 加载已有结果
            print("\n正在加载分析结果...")
            results = load_analysis_results(selected_file)
            print(f"✓ 加载完成，共 {len(results)} 条数据")
            
            # 查找失败的分析
            failed_indices = find_failed_analyses(results)
            
            if not failed_indices:
                print("\n✓ 太棒了！所有数据都已成功分析，无需补足")
                return
            
            print(f"\n发现 {len(failed_indices)} 条分析失败的数据")
            
            # 确认是否继续
            confirm = input(f"\n是否重新分析这些失败的条目？(y/n): ").strip().lower()
            if confirm != 'y':
                print("\n操作已取消")
                return
            
            # 加载框架
            print("\n正在加载分析框架...")
            analysis_framework = load_analysis_framework()
            output_framework = load_output_framework()
            print("✓ 框架加载完成")
            
            # 重新分析失败的条目
            results = reanalyze_failed_items(
                results, 
                failed_indices, 
                analysis_framework, 
                output_framework
            )
            
            # 保存到原文件（覆盖）
            save_results(results, filepath=selected_file)
            
            print("\n✓ 补足完成！")
            print(f"✓ 结果已更新到: {selected_file}")
            
    except FileNotFoundError as e:
        print(f"\n✗ 文件未找到: {e}")
        print("请确保以下文件存在于当前目录:")
        print("  - 数据表.csv")
        print("  - ref_md/基于品牌价值理解与声誉安全的AI内容分析框架_20251119.md")
        print("  - ref_md/赛力斯_问界AI声誉分析结果框架设计（用于生成网页）.md")
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

