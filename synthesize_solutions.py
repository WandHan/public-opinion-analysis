#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛力斯/问界 舆情分析结果综合解决方案生成工具
从多个分析结果文件中提取预警和高危问题，通过AI生成综合解决方案
"""

import json
import os
import glob
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
def scan_analysis_files(analysis_dir: str = "analysis_results") -> List[str]:
    """扫描分析结果目录下的所有JSON文件"""
    
    if not os.path.exists(analysis_dir):
        print(f"⚠️  分析结果目录不存在: {analysis_dir}")
        return []
    
    pattern = os.path.join(analysis_dir, "*.json")
    files = glob.glob(pattern)
    
    # 排除索引文件
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
def build_synthesis_prompt(critical_issues: Dict[str, List[Dict]]) -> str:
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
我们对赛力斯/问界品牌在各大AI平台（DeepSeek、豆包、元宝、Kimi等）的内容表现进行了全面分析，发现了{high_risk_count}个高危问题和{warning_count}个预警问题。这些问题可能严重影响品牌在AI引擎中的呈现和用户决策。

# 高危问题汇总
{chr(10).join(high_risk_summary)}

# 预警问题汇总
{chr(10).join(warning_summary)}

# GEO方法论框架（必须遵循）

你需要基于最新的GEO方法论来制定解决方案。核心原则是**"投AI所好"**——为AI模型提供结构化、权威且易于引用的"信息燃料"。

## GEO核心策略要点：

### 1. 内容生态建设 (Content Ecosystem)
- **E-E-A-T原则**：Experience(经验)、Expertise(专业)、Authoritativeness(权威)、Trustworthiness(可信)
- **DSS质量标准**：Depth(语义深度)、Support(数据支持)、Source(权威来源)
- **结构化内容**：摘要前置、H标签层级、短段落、FAQ、对比表格
- **"卡片式"数据引用**：采用"结论+来源"格式，如"根据《XX白皮书》，75%用户认为..."

### 2. 技术话语权与Schema部署
- **Schema标记**：Article、FAQPage、Product、Organization等结构化数据
- **GEOHead动态注入**：向网页注入JSON-LD描述核心要点、业务能力
- **LLMS.txt**：专为AI爬虫设计的站点地图
- **品牌词矩阵**：核心大词+精准长尾词+关联词

### 3. 平台渠道策略（针对不同AI平台）
- **DeepSeek**：权威网站、GitHub、ArXiv、技术媒体（36氪、虎嗅）
- **豆包(字节)**：头条号、抖音、悟空问答、什么值得买
- **Kimi(月之暗面)**：知乎、公众号、网易、新浪、搜狐
- **腾讯元宝**：微信公众号、搜一搜
- **共性规律**：高权重垂直站点、高活跃自媒体、发布时间靠前

### 4. 内容创作最佳实践
- **排行榜/盘点类**：效果最好，包含时间(2025年)、第三方中立角度
- **问句优化**：长尾问句(如"2025年适合家用的新能源SUV有哪些？")
- **客观平衡**：展示优缺点，避免绝对化用词("最好的"改为"在XX方面更优")
- **主题权威**：轮辐式内容集群，支柱页面+深度资源页

### 5. 技术SEO基础
- **AI爬虫友好**：允许GPTBot、CCBot、ClaudeBot等
- **HTML优先**：核心内容不依赖JS动态加载
- **禁用nosnippet**：严禁使用max-snippet:0等限制AI引用的标签
- **Canonical标签**：明确内容原始权威版本

### 6. 数据驱动与监测
- **认知真空**：寻找AI回答模糊的领域，填补内容蓝海
- **AI爬虫监测**：服务器日志分析GPTBot访问频率
- **KPI指标**：AI可见性指数、引用率、内容准确性、目标提示词覆盖率

# 你的任务

请基于以上GEO方法论和实际问题分析，**从3-6个不同维度**提出综合解决方案。

**重要原则**：
1. **维度数量灵活**：根据问题复杂度和覆盖面，自行决定3-6个维度
2. **GEO导向**：所有策略必须基于GEO方法论，具体到平台、技术、内容形式
3. **维度差异性**：各维度之间必须有明显区别，避免重复或交叉
4. **可执行性**：每个行动项要具体到工具、平台、时间节点

**建议维度选择**（根据实际问题选择和组合）：
- **内容生态重构**：E-E-A-T提升、DSS内容标准、结构化改造
- **技术基础设施**：Schema部署、LLMS.txt、GEOHead注入、爬虫监测
- **平台渠道矩阵**：针对DeepSeek/豆包/Kimi等的定向内容投喂
- **品牌词体系建设**：核心词+长尾问句、排行榜内容、对比话术
- **权威背书构建**：专家矩阵、独家数据、第三方认证、媒体提及
- **危机预警机制**：AI爬虫监测、负面舆情快速响应、内容纠偏
- **用户场景化表达**：将技术参数转化为用户价值、真实故事、UGC共创

**维度数量建议**：
- 高危问题集中在内容质量/权威性 → 3-4个深度维度
- 问题涉及多平台多领域 → 5-6个覆盖面广的维度
- 既有紧急危机又需长期建设 → 4-5个短中长期结合的维度

# 输出要求
请严格按照以下JSON格式输出，不要添加任何其他文字、注释或说明：

{{
  "metadata": {{
    "生成时间": "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "分析数据来源": "赛力斯舆情分析系统",
    "高危问题数量": {high_risk_count},
    "预警问题数量": {warning_count},
    "总问题数量": {high_risk_count + warning_count}
  }},
  "executive_summary": {{
    "核心问题概述": "用2-3句话总结当前最严重的声誉风险",
    "紧急程度评估": "高/中/低",
    "预计影响范围": "描述这些问题可能影响的用户群体和决策场景"
  }},
  "solutions": [
    {{
      "dimension": "维度1名称（根据实际问题和GEO方法论确定）",
      "priority": "高/中/低",
      "target_problems": ["针对的核心问题1", "针对的核心问题2"],
      "strategy_overview": "该维度的整体策略描述（200字左右），必须基于GEO方法论",
      "geo_principles": ["应用的GEO原则1（如：E-E-A-T）", "应用的GEO原则2（如：Schema标记）"],
      "action_items": [
        {{
          "action": "具体行动项标题",
          "description": "详细描述该行动项的执行方式，包含具体平台/工具/技术",
          "geo_method": "对应的GEO方法（如：结构化内容、平台投喂、Schema部署等）",
          "platforms": ["目标平台1（如：DeepSeek）", "目标平台2（如：知乎）"],
          "expected_outcome": "预期效果",
          "timeline": "执行时间线（如：1-2周/1个月/持续进行）",
          "kpi": "关键绩效指标（如：AI可见性指数提升20%）"
        }}
      ],
      "resources_needed": ["所需资源1", "所需资源2"],
      "risk_mitigation": "该策略可能遇到的风险及应对方式"
    }},
    {{
      "dimension": "维度2名称（基于GEO方法论）",
      "priority": "高/中/低",
      "target_problems": ["针对的核心问题"],
      "strategy_overview": "策略描述",
      "geo_principles": ["GEO原则"],
      "action_items": [
        {{
          "action": "行动项",
          "description": "详细描述",
          "geo_method": "GEO方法",
          "platforms": ["平台"],
          "expected_outcome": "预期效果",
          "timeline": "时间线",
          "kpi": "KPI"
        }}
      ],
      "resources_needed": ["资源需求"],
      "risk_mitigation": "风险应对"
    }},
    {{
      "dimension": "维度3名称",
      "priority": "高/中/低",
      "target_problems": ["核心问题"],
      "strategy_overview": "策略描述",
      "geo_principles": ["GEO原则"],
      "action_items": [
        {{
          "action": "行动项",
          "description": "描述",
          "geo_method": "方法",
          "platforms": ["平台"],
          "expected_outcome": "效果",
          "timeline": "时间",
          "kpi": "指标"
        }}
      ],
      "resources_needed": ["资源"],
      "risk_mitigation": "风险"
    }}
    // 根据实际需要，可以有3-6个维度
    // 每个维度必须明确关联GEO方法论中的具体策略
  ],
  "implementation_roadmap": {{
    "phase_1_immediate": {{
      "timeframe": "0-2周",
      "focus": "最紧急的行动",
      "key_milestones": ["里程碑1", "里程碑2"]
    }},
    "phase_2_short_term": {{
      "timeframe": "2周-2个月",
      "focus": "短期改善",
      "key_milestones": ["里程碑"]
    }},
    "phase_3_long_term": {{
      "timeframe": "2-6个月",
      "focus": "长期建设",
      "key_milestones": ["里程碑"]
    }}
  }},
  "success_metrics": {{
    "primary_kpis": [
      {{
        "indicator": "指标名称",
        "current_baseline": "当前基线",
        "target_3_months": "3个月目标",
        "target_6_months": "6个月目标"
      }}
    ]
  }}
}}

关键要求：
1. **GEO方法论为核心**：所有策略必须基于GEO方法论，明确标注geo_principles和geo_method
2. **维度数量灵活**：根据问题严重程度和覆盖面，输出3-6个维度（建议4-5个）
3. **平台针对性**：明确每个行动项针对的AI平台（DeepSeek/豆包/Kimi/元宝等）
4. **技术具体性**：涉及技术手段时要具体（如Schema标记、LLMS.txt、GEOHead等）
5. **内容形式明确**：内容策略要明确形式（排行榜、FAQ、长尾问句、对比文章等）
6. **可衡量KPI**：KPI要具体可衡量（如AI可见性指数、引用率、爬虫访问量等）
7. **维度差异性**：各维度之间必须有明显区别，覆盖GEO方法论的不同方面
8. **优先级合理**：高危问题对应的维度应标记为"高"优先级
9. **输出必须是纯JSON格式**，可以被标准JSON解析器解析
10. **不要用```json```包裹，不要添加任何解释文字**
"""
    
    return prompt

# ==================== 调用AI生成综合解决方案 ====================
def generate_solutions(critical_issues: Dict[str, List[Dict]], max_retries: int = 3) -> Dict:
    """调用AI生成综合解决方案"""
    
    print("\n" + "="*80)
    print("正在生成综合解决方案...")
    print(f"- 高危问题: {len(critical_issues['高危'])} 个")
    print(f"- 预警问题: {len(critical_issues['预警'])} 个")
    print("="*80 + "\n")
    
    prompt = build_synthesis_prompt(critical_issues)
    
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
    
    # 扫描分析结果文件
    analysis_dir = "analysis_results"
    files = scan_analysis_files(analysis_dir)
    
    if not files:
        print(f"\n⚠️  在 {analysis_dir} 目录下未找到分析结果文件")
        return
    
    print(f"\n找到 {len(files)} 个分析结果文件:")
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
    
    # 生成综合解决方案
    solutions = generate_solutions(critical_issues)
    
    # 保存解决方案到solution目录
    if solutions and "error" not in solutions:
        output_file = save_solutions(solutions, output_dir="solution")
        print(f"✓ 任务完成！")
        print(f"下一步: 可以使用该JSON文件进行可视化展示")
    else:
        print("\n✗ 解决方案生成失败，请检查错误信息")

if __name__ == "__main__":
    main()

