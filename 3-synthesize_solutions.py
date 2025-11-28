#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛力斯/问界 舆情分析结果综合解决方案生成工具
从多个分析结果文件中提取预警和高危问题，通过AI生成综合解决方案
"""

import json
import os
import glob
from collections import Counter
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
from dotenv import load_dotenv
from json_repair import repair_json

# ==================== 加载环境变量 ====================
load_dotenv()

# ==================== 配置 ====================
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.tu-zi.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-5-20250929")
API_KEY = os.environ.get("API_KEY", "")

# ==================== 初始化客户端 ====================
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY
)

# ==================== 扫描分析结果文件 ====================
def scan_analysis_files(analysis_dir: str = "analysis_results", index_file: str = "analysis_results/files_index.json") -> List[str]:
    """从索引文件中读取需要分析的文件列表"""
    
    # 首先检查索引文件是否存在
    if not os.path.exists(index_file):
        print(f"⚠️  索引文件不存在: {index_file}")
        print(f"   回退到扫描目录模式...")
        # 回退到原来的扫描方式
        if not os.path.exists(analysis_dir):
            print(f"⚠️  分析结果目录不存在: {analysis_dir}")
            return []
        
        pattern = os.path.join(analysis_dir, "*.json")
        files = glob.glob(pattern)
        files = [f for f in files if not f.endswith("files_index.json")]
        files.sort()
        return files
    
    # 读取索引文件
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        file_list = index_data.get("files", [])
        
        if not file_list:
            print(f"⚠️  索引文件中没有文件列表")
            return []
        
        # 构建完整路径
        files = []
        for filename in file_list:
            file_path = os.path.join(analysis_dir, filename)
            if os.path.exists(file_path):
                files.append(file_path)
            else:
                print(f"⚠️  文件不存在，已跳过: {filename}")
        
        files.sort()
        print(f"✓ 从索引文件读取到 {len(files)} 个文件")
        return files
        
    except Exception as e:
        print(f"✗ 读取索引文件失败 {index_file}: {e}")
        print(f"   回退到扫描目录模式...")
        # 回退到原来的扫描方式
        if not os.path.exists(analysis_dir):
            print(f"⚠️  分析结果目录不存在: {analysis_dir}")
            return []
        
        pattern = os.path.join(analysis_dir, "*.json")
        files = glob.glob(pattern)
        files = [f for f in files if not f.endswith("files_index.json")]
        files.sort()
        return files

# ==================== 加载分析结果 ====================
def load_analysis_data(file_path: str) -> List[Dict]:
    """加载单个分析结果文件"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"✓ 加载文件: {os.path.basename(file_path)} ({len(data)} 条数据)")
        return data
    except Exception as e:
        print(f"✗ 加载文件失败 {file_path}: {e}")
        return []

# ==================== 加载GEO方法论文件 ====================
def load_geo_methodology(method_file: str = "ref_md/GEO方法论与实战全案.md") -> str:
    """加载GEO方法论文件内容"""
    
    try:
        if not os.path.exists(method_file):
            print(f"⚠️  GEO方法论文件不存在: {method_file}")
            return ""
        
        with open(method_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✓ 已加载GEO方法论文件: {method_file}")
        return content
    except Exception as e:
        print(f"✗ 加载GEO方法论文件失败 {method_file}: {e}")
        return ""

# ==================== 提取平台信息 ====================
def extract_platforms(critical_issues: Dict[str, List[Dict]]) -> str:
    """
    从关键问题中提取平台信息
    返回最常见的平台，如果有多个平台则返回平台列表
    """
    all_platforms = []
    for category in ["高危", "预警"]:
        for item in critical_issues[category]:
            platform = item.get("Platform", "").strip()
            if platform:
                # 统一平台名称（处理大小写不一致）
                platform_normalized = platform
                if platform.lower() == "deepseek":
                    platform_normalized = "DeepSeek"
                all_platforms.append(platform_normalized)
    
    if not all_platforms:
        return "多个AI平台"
    
    # 统计平台出现次数
    platform_counter = Counter(all_platforms)
    
    # 如果只有一个平台或某个平台占主导（>70%），返回该平台
    most_common_platform, count = platform_counter.most_common(1)[0]
    total_count = len(all_platforms)
    
    if count / total_count > 0.7:
        return most_common_platform
    else:
        # 多个平台，返回前3个最常见的平台
        top_platforms = [p for p, _ in platform_counter.most_common(3)]
        return "、".join(top_platforms)

# ==================== 提取预警和高危内容 ====================
def extract_critical_issues(all_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    提取所有预警(🟡)和高危(🔴)的分析结果
    按安全状态分类
    """
    
    critical_issues = {
        "高危": [],
        "预警": []
    }
    
    for item in all_data:
        security_status = item.get("Security_Status", "")
        
        if "🔴" in security_status or "高危" in security_status:
            critical_issues["高危"].append(item)
        elif "🟡" in security_status or "预警" in security_status:
            critical_issues["预警"].append(item)
    
    return critical_issues

# ==================== 构建综合分析提示词 ====================
def build_synthesis_prompt(critical_issues: Dict[str, List[Dict]], method_content: str, platform: str) -> str:
    """构建用于生成综合解决方案的提示词"""
    
    # 统计信息
    high_risk_count = len(critical_issues["高危"])
    warning_count = len(critical_issues["预警"])
    
    # 准备高危问题摘要
    high_risk_summary = []
    for idx, item in enumerate(critical_issues["高危"][:10], 1):  # 最多展示10个
        high_risk_summary.append(f"""
【高危问题 {idx}】
- 平台: {item.get('Platform', 'N/A')}
- 用户提问: {item.get('User_Query', 'N/A')}
- 风险诊断: {item.get('Risk_Diagnosis', 'N/A')[:200]}...
- 策略建议: {item.get('Strategy_Action', 'N/A')[:300]}...
""")
    
    # 准备预警问题摘要
    warning_summary = []
    for idx, item in enumerate(critical_issues["预警"][:15], 1):  # 最多展示15个
        warning_summary.append(f"""
【预警问题 {idx}】
- 平台: {item.get('Platform', 'N/A')}
- 用户提问: {item.get('User_Query', 'N/A')}
- 风险诊断: {item.get('Risk_Diagnosis', 'N/A')[:200]}...
- 品牌印象评分: {item.get('Brand_Impression', 'N/A')[:100]}...
""")
    
    prompt = f"""你是一位资深的GEO (Generative Engine Optimization，生成式引擎优化) 专家和AI内容生态治理顾问，专注于新能源汽车行业的品牌声誉管理。

# 任务背景

我们对赛力斯/问界品牌在 **{platform}** 的内容表现进行了全面分析，发现了{high_risk_count}个高危问题和{warning_count}个预警问题。这些问题可能严重影响品牌在AI引擎中的呈现和用户决策。

# 高危问题汇总

{chr(10).join(high_risk_summary)}

# 预警问题汇总

{chr(10).join(warning_summary)}

# GEO方法论框架（必须严格遵循）

{method_content}

# 你的任务

请基于以上GEO方法论和实际问题分析，**从3-6个不同维度**提出综合解决方案。

**重要原则**：

1. **维度数量灵活**：根据问题复杂度和覆盖面，自行决定3-6个维度。
2. **GEO导向**：所有策略必须严格基于上述GEO方法论中定义的核心策略要点（如关键词策略、内容矩阵、技术SEO等），具体到平台、技术、内容形式。
3. **维度差异性**：各维度之间必须有明显区别，对应GEO方法论中的不同策略模块。
4. **可执行性**：每个行动项要具体到工具（如LowFruits, Firecrawl）、平台、时间节点。
5. **禁止直接向AI平台提交请求**：**严禁**生成任何涉及"向AI平台提交官方事实核查请求包"、"向平台提交申诉"、"联系平台客服"等直接与AI平台官方沟通的行动项。所有策略必须通过内容优化、技术SEO、数据投喂等GEO方法来实现，而非直接与平台沟通。

**建议维度选择**（请严格依据GEO方法论的章节结构）：

- **内容矩阵构建维度**：聚焦E-E-A-T增强、DSS标准（深度/数据/权威）落实，以及"认知真空"的发现与填补。
- **技术SEO基础设施维度**：Schema标记（Article/Product）、GEOHead动态注入、LLMS.txt站点地图建设等针对AI Bot的优化。
- **平台差异化渠道维度**：基于GEO方法论中"平台底层逻辑"图表，制定针对 **{platform}** 的差异化投喂策略（如DeepSeek偏向技术源，豆包偏向字节系）。
- **关键词策略维度**：核心大词与长尾问句（Long-tail Questions）的结合，以及“卡片式”数据引用格式的部署。
- **品牌实体的权威性维度**：专家矩阵建立、维基百科/权威媒体提及（Mentions）、Canonical标签规范化。

**维度数量建议**：

- 高危问题集中在内容质量/权威性 → 3-4个深度维度（侧重内容结构与DSS）
- 问题涉及多平台多领域 → 5-6个覆盖面广的维度（涵盖技术SEO与多渠道分发）
- 既有紧急危机又需长期建设 → 4-5个短中长期结合的维度（如“排名上榜”与“排名优化”结合）

# 输出要求

请严格按照以下JSON格式输出，不要添加任何其他文字、注释或说明：

{{ "metadata": {{ "生成时间": "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "分析数据来源": "赛力斯舆情分析系统", "目标平台": "{platform}", "高危问题数量": {high_risk_count}, "预警问题数量": {warning_count}, "总问题数量": {high_risk_count + warning_count} }}, "executive_summary": {{ "核心问题概述": "用2-3句话总结当前最严重的声誉风险", "紧急程度评估": "高/中/低", "预计影响范围": "描述这些问题可能影响的用户群体和决策场景" }}, "solutions": [ {{ "dimension": "维度名称（必须对应GEO方法论中的策略方向，如'内容矩阵构建'或'技术SEO优化'）", "priority": "高/中/低", "target_problems": ["针对的核心问题1", "针对的核心问题2"], "strategy_overview": "该维度的整体策略描述（200字左右）。请务必聚焦于解决方案的**具体内容**（Content）和执行逻辑，必须引用GEO方法论中的具体概念（如'认知真空'、'DSS原则'等），拒绝空话套话。", "geo_principles": ["应用的GEO原则1（如：摘要前置）", "应用的GEO原则2（如：GEOHead注入）"], "action_items": [ {{ "action": "具体行动项标题", "description": "详细描述该行动项的执行内容。若为内容策略，请提供**具体选题、核心话术或数据引用格式**；若为技术策略，请提供**具体工具配置或标签写法**。**禁止**包含任何需要直接与AI平台官方沟通的内容（如提交请求包、申诉等），必须通过GEO技术手段实现。", "geo_method": "对应的GEO方法（需与GEO方法论保持一致）", "platforms": ["{platform}"], "expected_outcome": "预期效果（如：AI可见性指数提升）", "timeline": "执行时间线", "kpi": "关键绩效指标" }} ], "resources_needed": ["所需资源1", "所需资源2"], "risk_mitigation": "该策略可能遇到的风险及应对方式" }} // 请根据实际情况生成3-6个维度的解决方案对象 ], "implementation_roadmap": {{ "phase_1_immediate": {{ "timeframe": "0-2周（依据GEO方法论中的'排名上榜'阶段）", "focus": "最紧急的行动", "key_milestones": ["里程碑1", "里程碑2"] }}, "phase_2_short_term": {{ "timeframe": "2周-2个月", "focus": "短期改善", "key_milestones": ["里程碑"] }}, "phase_3_long_term": {{ "timeframe": "2-6个月（依据GEO方法论中的'排名优化'阶段）", "focus": "长期建设", "key_milestones": ["里程碑"] }} }}, "success_metrics": {{ "primary_kpis": [ {{ "indicator": "指标名称（参考GEO方法论中的KPI部分，如AI可见性指数）", "current_baseline": "当前基线", "target_3_months": "3个月目标", "target_6_months": "6个月目标" }} ] }} }}

关键要求：

1. **GEO方法论为核心**：所有策略必须基于上述GEO方法论，明确标注geo_principles和geo_method。
2. **维度数量灵活**：根据问题严重程度和覆盖面，输出3-6个维度（建议4-5个）。
3. **平台针对性**：明确每个行动项针对的AI平台，依据GEO方法论中的平台逻辑表。
4. **技术具体性**：涉及技术手段时要具体（如Schema标记类型、LLMS.txt、Canonical标签）。
5. **禁止平台直接沟通策略**：**严格禁止**在action_items中包含以下类型的行动项：
   - "向AI平台提交官方事实核查请求包"
   - "向平台提交申诉/投诉"
   - "联系平台客服/官方"
   - "向平台发送官方声明"
   - 任何需要直接与AI平台官方沟通的行动
   所有解决方案必须通过内容优化、技术SEO、数据源建设、关键词策略等GEO技术手段实现，而非依赖平台官方介入。
6. **输出必须是纯JSON格式**，可以被标准JSON解析器解析。
7. **不要用`json`包裹，不要添加任何解释文字**。
"""
    
    return prompt

# ==================== 调用AI生成综合解决方案 ====================
def generate_solutions(critical_issues: Dict[str, List[Dict]], method_content: str, platform: str, max_retries: int = 3) -> Dict:
    """调用AI生成综合解决方案"""
    
    print("\n" + "="*80)
    print("正在生成综合解决方案...")
    print(f"- 高危问题: {len(critical_issues['高危'])} 个")
    print(f"- 预警问题: {len(critical_issues['预警'])} 个")
    print(f"- 目标平台: {platform}")
    print("="*80 + "\n")
    
    prompt = build_synthesis_prompt(critical_issues, method_content, platform)
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"  第 {attempt + 1} 次尝试...")
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 尝试解析JSON
            try:
                result = json.loads(result_text)
                print("✓ 解决方案生成成功！")
                return result
            except json.JSONDecodeError:
                # 尝试修复JSON
                print("  尝试修复JSON格式...")
                repaired = repair_json(result_text)
                result = json.loads(repaired)
                print("✓ JSON修复成功，解决方案生成完成！")
                return result
                
        except Exception as e:
            print(f"✗ 尝试 {attempt + 1} 失败: {e}")
            if attempt == max_retries - 1:
                print(f"✗ 已达到最大重试次数")
                return {
                    "error": "生成失败",
                    "message": str(e),
                    "metadata": {
                        "生成时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "高危问题数量": len(critical_issues['高危']),
                        "预警问题数量": len(critical_issues['预警'])
                    }
                }
    
    return {}

# ==================== 保存解决方案 ====================
def save_solutions(solutions: Dict, output_dir: str = "solution"):
    """保存综合解决方案到JSON文件"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"综合解决方案_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(solutions, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✓ 综合解决方案已保存至: {filepath}")
    
    # 打印摘要信息
    if "metadata" in solutions:
        metadata = solutions["metadata"]
        print(f"\n数据统计:")
        print(f"  - 高危问题: {metadata.get('高危问题数量', 0)} 个")
        print(f"  - 预警问题: {metadata.get('预警问题数量', 0)} 个")
        print(f"  - 总问题数: {metadata.get('总问题数量', 0)} 个")
    
    if "executive_summary" in solutions:
        summary = solutions["executive_summary"]
        print(f"\n核心摘要:")
        print(f"  - 紧急程度: {summary.get('紧急程度评估', 'N/A')}")
        print(f"  - 问题概述: {summary.get('核心问题概述', 'N/A')[:100]}...")
    
    if "solutions" in solutions:
        print(f"\n解决方案维度: {len(solutions['solutions'])} 个")
        for idx, sol in enumerate(solutions['solutions'], 1):
            print(f"  {idx}. {sol.get('dimension', 'N/A')} (优先级: {sol.get('priority', 'N/A')})")
    
    print(f"{'='*80}\n")
    
    return filepath

# ==================== 主函数 ====================
def main():
    """主函数"""
    
    print("\n" + "="*80)
    print("赛力斯/问界 舆情分析综合解决方案生成工具".center(80))
    print("="*80 + "\n")
    
    # 检查API密钥
    if not API_KEY:
        print("⚠️  错误: 请在.env文件中配置API_KEY")
        return
    
    # 从索引文件读取分析结果文件列表
    analysis_dir = "analysis_results"
    index_file = os.path.join(analysis_dir, "files_index.json")
    files = scan_analysis_files(analysis_dir, index_file)
    
    if not files:
        print(f"\n⚠️  未找到需要分析的文件（从索引文件: {index_file}）")
        return
    
    print(f"\n从索引文件读取到 {len(files)} 个分析结果文件:")
    for idx, file in enumerate(files, 1):
        print(f"  {idx}. {os.path.basename(file)}")
    
    # 加载所有分析数据
    print("\n正在加载分析数据...")
    all_data = []
    for file in files:
        data = load_analysis_data(file)
        all_data.extend(data)
    
    print(f"\n✓ 共加载 {len(all_data)} 条分析数据")
    
    # 提取预警和高危问题
    print("\n正在提取预警和高危问题...")
    critical_issues = extract_critical_issues(all_data)
    
    print(f"✓ 提取完成:")
    print(f"  - 高危问题: {len(critical_issues['高危'])} 个")
    print(f"  - 预警问题: {len(critical_issues['预警'])} 个")
    
    if len(critical_issues['高危']) == 0 and len(critical_issues['预警']) == 0:
        print("\n✓ 太棒了！未发现高危或预警问题")
        return
    
    # 加载GEO方法论文件
    print("\n正在加载GEO方法论文件...")
    method_file = "ref_md/GEO方法论与实战全案.md"
    method_content = load_geo_methodology(method_file)
    
    if not method_content:
        print("⚠️  警告: 未加载到GEO方法论内容，将使用空内容")
        method_content = ""
    
    # 提取平台信息
    print("\n正在分析平台分布...")
    platform = extract_platforms(critical_issues)
    print(f"✓ 主要平台: {platform}")
    
    # 生成综合解决方案
    solutions = generate_solutions(critical_issues, method_content, platform)
    
    # 保存解决方案到solution目录
    if solutions and "error" not in solutions:
        output_file = save_solutions(solutions, output_dir="solution")
        print(f"✓ 任务完成！")
        print(f"下一步: 可以使用该JSON文件进行可视化展示")
    else:
        print("\n✗ 解决方案生成失败，请检查错误信息")

if __name__ == "__main__":
    main()

