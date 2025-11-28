#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛力斯/问界 舆情分析结果综合解决方案生成工具
从多个分析结果文件中提取预警和高危问题，通过AI生成综合解决方案
"""

import json
import os
import glob
import sys
import time
from collections import Counter
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
from dotenv import load_dotenv
from json_repair import repair_json
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # 简单的进度显示替代方案
    class tqdm:
        def __init__(self, iterable=None, total=None, desc="", unit="", ncols=80, leave=True, **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable else 0)
            self.desc = desc
            self.unit = unit
            self.current = 0
            self._n = 0  # 当前值（用于百分比模式）
            self.ncols = ncols
            self.leave = leave
            self.start_time = time.time()
        
        @property
        def n(self):
            return self._n
        
        @n.setter
        def n(self, value):
            self._n = value
            if self.total > 0:
                self.current = int((self._n / 100) * self.total) if self.total == 100 else self._n
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            self.close()
        
        def __iter__(self):
            if self.iterable:
                for item in self.iterable:
                    yield item
                    self.update(1)
        
        def update(self, n=1):
            self.current += n
            self._n = min((self.current / self.total) * 100, 100) if self.total > 0 else self.current
            self.refresh()
        
        def refresh(self):
            """刷新显示"""
            elapsed = time.time() - self.start_time
            if self.total > 0:
                if self.total == 100:
                    # 百分比模式
                    percent = self._n
                    current_display = int(self._n)
                else:
                    percent = (self.current / self.total) * 100
                    current_display = self.current
                
                bar_length = 30
                filled = int(bar_length * percent / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                # 使用 \r 回到行首，并用空格清除旧内容
                line = f'{self.desc} [{bar}] {percent:.1f}% ({current_display}/{self.total} {self.unit}) 耗时: {elapsed:.1f}s'
                # 确保行长度不超过 ncols，避免换行
                if len(line) > self.ncols:
                    line = line[:self.ncols-3] + '...'
                sys.stdout.write(f'\r{line}' + ' ' * max(0, self.ncols - len(line)))
                sys.stdout.flush()
        
        def set_description(self, desc):
            self.desc = desc
            self.refresh()
        
        def write(self, s):
            """写入消息（换行显示）"""
            sys.stdout.write('\n' + s)
            sys.stdout.flush()
        
        def close(self):
            if self.leave:
                sys.stdout.write('\n')
            else:
                # 清除当前行
                sys.stdout.write('\r' + ' ' * self.ncols + '\r')
            sys.stdout.flush()

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
def load_analysis_data(file_path: str, pbar: Optional[tqdm] = None) -> List[Dict]:
    """加载单个分析结果文件"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        filename = os.path.basename(file_path)
        if pbar:
            # 只更新描述，不打印，避免重复输出
            pbar.set_description(f"加载: {filename[:25]}... ({len(data)}条)")
        else:
            print(f"✓ 加载文件: {filename} ({len(data)} 条数据)")
        return data
    except Exception as e:
        if pbar:
            pbar.set_description(f"✗ 加载失败: {os.path.basename(file_path)[:30]}...")
        else:
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
def extract_critical_issues(all_data: List[Dict], show_progress: bool = True) -> Dict[str, List[Dict]]:
    """
    提取所有预警(🟡)和高危(🔴)的分析结果
    按安全状态分类
    """
    
    critical_issues = {
        "高危": [],
        "预警": []
    }
    
    if show_progress:
        pbar = tqdm(total=len(all_data), desc="提取关键问题", unit="条", ncols=80, leave=False)
    else:
        pbar = None
    
    current_count = 0
    try:
        for item in all_data:
            security_status = item.get("Security_Status", "")
            
            if "🔴" in security_status or "高危" in security_status:
                critical_issues["高危"].append(item)
            elif "🟡" in security_status or "预警" in security_status:
                critical_issues["预警"].append(item)
            
            if pbar:
                pbar.update(1)
                current_count += 1
                # 减少更新频率，避免过于频繁的刷新
                update_interval = max(1, len(all_data) // 20)
                if current_count % update_interval == 0 or current_count == len(all_data):
                    pbar.set_description(f"提取中 (高危:{len(critical_issues['高危'])}, 预警:{len(critical_issues['预警'])})")
    finally:
        if pbar:
            pbar.close()
    
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
6. **完整性要求**：**每个维度必须包含完整的字段**，包括：action_items（至少2-3个行动项）、resources_needed、risk_mitigation。**严禁**省略任何字段或截断内容。如果内容较长，请确保所有字段都完整输出。

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

{{ "metadata": {{ "生成时间": "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "分析数据来源": "赛力斯舆情分析系统", "目标平台": "{platform}", "高危问题数量": {high_risk_count}, "预警问题数量": {warning_count}, "总问题数量": {high_risk_count + warning_count} }}, "executive_summary": {{ "核心问题概述": "用2-3句话总结当前最严重的声誉风险", "紧急程度评估": "高/中/低", "预计影响范围": "描述这些问题可能影响的用户群体和决策场景" }}, "solutions": [ {{ "dimension": "维度名称（必须对应GEO方法论中的策略方向，如'内容矩阵构建'或'技术SEO优化'）", "priority": "高/中/低", "target_problems": ["针对的核心问题1", "针对的核心问题2"], "strategy_overview": "该维度的整体策略描述（200字左右）。请务必聚焦于解决方案的**具体内容**（Content）和执行逻辑，必须引用GEO方法论中的具体概念（如'认知真空'、'DSS原则'等），拒绝空话套话。", "geo_principles": ["应用的GEO原则1（如：摘要前置）", "应用的GEO原则2（如：GEOHead注入）"], "action_items": [ {{ "action": "具体行动项标题", "description": "详细描述该行动项的执行内容。若为内容策略，请提供**具体选题、核心话术或数据引用格式**；若为技术策略，请提供**具体工具配置或标签写法**。**禁止**包含任何需要直接与AI平台官方沟通的内容（如提交请求包、申诉等），必须通过GEO技术手段实现。", "geo_method": "对应的GEO方法（需与GEO方法论保持一致）", "platforms": ["{platform}"], "expected_outcome": "预期效果（如：AI可见性指数提升）", "timeline": "执行时间线（必须完整，不能截断）", "kpi": "关键绩效指标" }} ], "resources_needed": ["所需资源1", "所需资源2"], "risk_mitigation": "该策略可能遇到的风险及应对方式（必须完整描述，不能省略）" }} // 请根据实际情况生成3-6个维度的解决方案对象，**每个维度必须包含完整的action_items（至少2-3个）、resources_needed和risk_mitigation字段，严禁省略或截断** ], "implementation_roadmap": {{ "phase_1_immediate": {{ "timeframe": "0-2周（依据GEO方法论中的'排名上榜'阶段）", "focus": "最紧急的行动", "key_milestones": ["里程碑1", "里程碑2"] }}, "phase_2_short_term": {{ "timeframe": "2周-2个月", "focus": "短期改善", "key_milestones": ["里程碑"] }}, "phase_3_long_term": {{ "timeframe": "2-6个月（依据GEO方法论中的'排名优化'阶段）", "focus": "长期建设", "key_milestones": ["里程碑"] }} }}, "success_metrics": {{ "primary_kpis": [ {{ "indicator": "指标名称（参考GEO方法论中的KPI部分，如AI可见性指数）", "current_baseline": "当前基线", "target_3_months": "3个月目标", "target_6_months": "6个月目标" }} ] }} }}

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
6. **完整性要求（非常重要）**：
   - **每个维度必须包含至少2-3个action_items**，不能只有1个
   - **每个维度必须包含resources_needed字段**（至少2-3项资源）
   - **每个维度必须包含risk_mitigation字段**（完整描述风险和应对方式，不能省略）
   - **所有action_items的timeline、kpi等字段必须完整**，不能截断
   - **如果内容较长，请确保所有字段都完整输出，不要因为长度限制而省略**
7. **输出必须是纯JSON格式**，可以被标准JSON解析器解析。
8. **不要用`json`包裹，不要添加任何解释文字**。
"""
    
    return prompt

# ==================== 验证解决方案完整性 ====================
def validate_solution_completeness(result: Dict) -> List[str]:
    """验证生成的解决方案是否完整"""
    errors = []
    
    if "solutions" not in result:
        return ["缺少solutions字段"]
    
    for idx, solution in enumerate(result.get("solutions", []), 1):
        dimension = solution.get("dimension", f"维度{idx}")
        
        # 检查action_items
        action_items = solution.get("action_items", [])
        if len(action_items) < 2:
            errors.append(f"{dimension}: action_items数量不足（当前{len(action_items)}个，建议至少2-3个）")
        
        # 检查每个action_item的完整性
        for i, item in enumerate(action_items, 1):
            required_fields = ["action", "description", "geo_method", "platforms", "expected_outcome", "timeline", "kpi"]
            for field in required_fields:
                if field not in item or not item[field] or (isinstance(item[field], str) and len(item[field].strip()) == 0):
                    errors.append(f"{dimension} - action_item {i}: 缺少或为空字段 '{field}'")
            
            # 检查timeline是否被截断（以常见截断字符结尾）
            timeline = item.get("timeline", "")
            if timeline and (timeline.endswith("互") or timeline.endswith("...") or len(timeline) < 10):
                errors.append(f"{dimension} - action_item {i}: timeline可能被截断")
        
        # 检查resources_needed
        if "resources_needed" not in solution or not solution["resources_needed"]:
            errors.append(f"{dimension}: 缺少resources_needed字段")
        elif len(solution["resources_needed"]) < 2:
            errors.append(f"{dimension}: resources_needed数量不足（当前{len(solution['resources_needed'])}个，建议至少2-3个）")
        
        # 检查risk_mitigation
        if "risk_mitigation" not in solution or not solution["risk_mitigation"]:
            errors.append(f"{dimension}: 缺少risk_mitigation字段")
        elif len(solution["risk_mitigation"].strip()) < 50:
            errors.append(f"{dimension}: risk_mitigation内容过短，可能不完整")
    
    return errors

# ==================== 调用AI生成综合解决方案 ====================
def generate_solutions(critical_issues: Dict[str, List[Dict]], method_content: str, platform: str, max_retries: int = 3) -> Dict:
    """调用AI生成综合解决方案"""
    
    print(f"正在生成综合解决方案 (高危:{len(critical_issues['高危'])}个, 预警:{len(critical_issues['预警'])}个, 平台:{platform})...")
    
    prompt = build_synthesis_prompt(critical_issues, method_content, platform)
    
    # 显示进度状态
    with tqdm(total=100, desc="AI生成中", unit="%", ncols=80, leave=False) as status_pbar:
        for attempt in range(max_retries):
            try:
                status_pbar.set_description(f"AI生成中 (尝试 {attempt + 1}/{max_retries})")
                status_pbar.n = 0
                status_pbar.refresh()
                
                if attempt > 0:
                    status_pbar.write(f"  第 {attempt + 1} 次尝试...")
                
                # 显示API调用状态
                status_pbar.set_description(f"正在调用API ({MODEL_NAME})...")
                status_pbar.n = 20
                status_pbar.refresh()
                
                start_time = time.time()
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=16000  # 增加token限制，确保完整输出
                )
                elapsed = time.time() - start_time
                
                result_text = response.choices[0].message.content.strip()
                
                status_pbar.set_description("正在解析响应...")
                status_pbar.n = 80
                status_pbar.refresh()
                
                # 尝试解析JSON
                try:
                    result = json.loads(result_text)
                    
                    # 验证JSON完整性
                    validation_errors = validate_solution_completeness(result)
                    if validation_errors:
                        status_pbar.write("⚠️  警告: 检测到不完整的字段:")
                        for error in validation_errors:
                            status_pbar.write(f"  - {error}")
                    
                    status_pbar.n = 100
                    status_pbar.set_description("✓ 生成成功")
                    status_pbar.refresh()
                    print(f"✓ 解决方案生成成功 (耗时: {elapsed:.1f}秒)")
                    return result
                except json.JSONDecodeError:
                    # 尝试修复JSON
                    status_pbar.set_description("修复JSON格式...")
                    status_pbar.refresh()
                    repaired = repair_json(result_text)
                    result = json.loads(repaired)
                    
                    # 验证修复后的JSON完整性
                    validation_errors = validate_solution_completeness(result)
                    if validation_errors:
                        status_pbar.write("⚠️  警告: 修复后仍存在不完整的字段:")
                        for error in validation_errors:
                            status_pbar.write(f"  - {error}")
                    
                    status_pbar.n = 100
                    status_pbar.set_description("✓ 修复成功")
                    status_pbar.refresh()
                    print(f"✓ JSON修复成功，解决方案生成完成 (耗时: {elapsed:.1f}秒)")
                    return result
                    
            except Exception as e:
                status_pbar.n = (attempt + 1) * 30
                status_pbar.set_description(f"✗ 尝试 {attempt + 1} 失败")
                status_pbar.refresh()
                # 使用 write 方法避免与进度条冲突
                if attempt == 0:
                    status_pbar.write(f"✗ 尝试 {attempt + 1} 失败: {str(e)[:50]}...")
                
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
                else:
                    # 等待后重试
                    wait_time = min(2 ** attempt, 10)  # 指数退避，最多10秒
                    status_pbar.set_description(f"等待 {wait_time}s 后重试...")
                    status_pbar.refresh()
                    for i in range(wait_time):
                        time.sleep(1)
                        status_pbar.n = min(status_pbar.n + (100 // wait_time), 99)
                        status_pbar.refresh()
    
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
    
    # 整体进度跟踪
    total_steps = 6
    current_step = 0
    
    def update_main_progress(step_name: str):
        nonlocal current_step
        current_step += 1
        progress_pct = (current_step / total_steps) * 100
        print(f"[{current_step}/{total_steps}] {step_name} ({progress_pct:.0f}%)")
    
    # 步骤1: 扫描文件
    update_main_progress("扫描分析结果文件")
    analysis_dir = "analysis_results"
    index_file = os.path.join(analysis_dir, "files_index.json")
    files = scan_analysis_files(analysis_dir, index_file)
    
    if not files:
        print(f"\n⚠️  未找到需要分析的文件（从索引文件: {index_file}）")
        return
    
    print(f"✓ 从索引文件读取到 {len(files)} 个分析结果文件")
    if len(files) <= 5:  # 只有文件数量少时才显示列表
        for idx, file in enumerate(files, 1):
            print(f"  {idx}. {os.path.basename(file)}")
    
    # 步骤2: 加载所有分析数据
    update_main_progress("加载分析数据")
    all_data = []
    
    with tqdm(total=len(files), desc="加载文件", unit="个", ncols=80, leave=False) as pbar:
        for file in files:
            data = load_analysis_data(file, pbar)
            all_data.extend(data)
            pbar.update(1)
    
    print(f"✓ 共加载 {len(all_data)} 条分析数据")
    
    # 步骤3: 提取预警和高危问题
    update_main_progress("提取关键问题")
    critical_issues = extract_critical_issues(all_data, show_progress=True)
    
    print(f"✓ 提取完成: 高危 {len(critical_issues['高危'])} 个, 预警 {len(critical_issues['预警'])} 个")
    
    if len(critical_issues['高危']) == 0 and len(critical_issues['预警']) == 0:
        print("\n✓ 太棒了！未发现高危或预警问题")
        return
    
    # 步骤4: 加载GEO方法论文件
    update_main_progress("加载GEO方法论")
    method_file = "ref_md/GEO方法论与实战全案.md"
    method_content = load_geo_methodology(method_file)
    
    if not method_content:
        print("⚠️  警告: 未加载到GEO方法论内容，将使用空内容")
        method_content = ""
    
    # 步骤5: 提取平台信息
    update_main_progress("分析平台分布")
    platform = extract_platforms(critical_issues)
    print(f"✓ 主要平台: {platform}")
    
    # 步骤6: 生成综合解决方案
    update_main_progress("生成综合解决方案")
    solutions = generate_solutions(critical_issues, method_content, platform)
    
    # 保存解决方案到solution目录
    if solutions and "error" not in solutions:
        print("\n" + "="*80)
        print("保存解决方案".center(80))
        print("="*80)
        output_file = save_solutions(solutions, output_dir="solution")
        print(f"\n{'='*80}")
        print("✓ 任务完成！".center(80))
        print(f"{'='*80}")
        print(f"下一步: 可以使用该JSON文件进行可视化展示")
    else:
        print("✗ 解决方案生成失败，请检查错误信息")

if __name__ == "__main__":
    main()

