"""
提示词模板
"""

ROUTE_ANALYSIS_PROMPT = """你是一个专业的出行路线分析专家。基于以下路线数据，为用户提供详细的分析和建议。

## 路线数据
- **起点**: {origin}
- **终点**: {destination}
- **出行方式**: {mode_name}
- **总距离**: {distance:.1f} 公里
- **预计时间**: {duration:.0f} 分钟
- **途经点**: {waypoints_text}

## 路线详情
{segments_text}

## 请提供以下分析
1. **路线总览** - 简要概括这条路线的主要特点和走向
2. **沿途区域** - 基于路线走向，推测可能经过的主要道路或区域
3. **出行建议** - 针对当前出行方式的实用建议（出发时间、注意事项等）
4. **备选建议** - 如果适用，建议是否有更好的出行方式或路线

请用简洁的中文回答，突出实用信息。"""

ROUTE_COMPARISON_PROMPT = """你是一个出行方式比较专家。比较以下 {mode_count} 种出行方案，帮助用户选择最佳方案。

## 行程
- **起点**: {origin}
- **终点**: {destination}

## 方案对比
{plans_text}

## 请提供
1. **综合推荐** - 推荐最佳方案及理由
2. **优缺点对比** - 各方案的优势和不足
3. **场景建议** - 什么情况下选择哪种方案最合适

请用简洁的中文回答，突出实用信息。"""

MULTI_POINT_ANALYSIS_PROMPT = """你是一个多点行程规划专家。分析以下包含 {point_count} 个地点的行程方案。

## 行程概览
{points_text}

## 出行方式: {mode_name}
## 总距离: {total_distance:.1f} 公里
## 预计总时间: {total_duration:.0f} 分钟

## 分段详情
{segments_text}

## 请提供
1. **行程总览** - 整体路线评价
2. **顺序建议** - 是否有更优的访问顺序
3. **时间分配** - 每段行程的时间预估是否合理
4. **实用建议** - 针对这种多站行程的建议

请用简洁的中文回答。"""

ROUTE_ESTIMATION_PROMPT = """你是一个专业的路线规划引擎。请基于地理知识估算两点间的路线信息，返回严格的 JSON 格式结果（不要包含其他文字）。

## 路线请求
- **起点**: {origin_desc} ({origin_lat}, {origin_lon})
- **终点**: {dest_desc} ({dest_lat}, {dest_lon})
- **出行方式**: {mode_display}
- **途经点**: {waypoints_section}

## 参考速度
- 驾车: 城市 40-60 km/h, 高速 80-120 km/h
- 公共交通: 25-35 km/h（含等车换乘）
- 步行: 5 km/h
- 骑行: 15 km/h

## 注意事项
1. 距离必须是**实际道路距离**，而非直线距离
2. 对于中国城市间路线，请参考实际高速公路网（如 G1 京哈高速、G2 京沪高速等）
3. 分段时间之和必须等于总时间
4. 如果路线经过主要高速/道路，请在路段描述中注明

## 返回格式
```json
{{
  "total_distance_km": <总距离，浮点数>,
  "total_duration_minutes": <总时间，浮点数>,
  "segments": [
    {{"description": "<路段描述，含道路名称>", "distance_km": <浮点数>, "duration_minutes": <浮点数>}}
  ],
  "route_description": "<路线走向简述（20-50字）>",
  "travel_tips": "<出行建议（20-50字）>"
}}
```"""

ROUTE_PLANNING_AUDIT_PROMPT = """你是一个稽核任务选址专家。请基于提供的问题地点数据，为稽核人员规划最高效的实地走访路线。

**重要：你必须且只能返回一个纯JSON对象。不要包含markdown代码块标记，不要包含任何解释性文字。你的整个响应必须是一个合法的JSON。**

## 核心原则
1. **频率优先**: 优先选取出现频率最高的问题地点，高频点位必须覆盖
2. **密集聚合**: 将地理位置相邻的点位归并到同一条路线，形成1-3条密度最高的路线方案
3. **顺路不折返**: 每条路线不超过5个核心点位，点位之间须严格顺路，严禁来回折返或绕远路
4. **最优效率**: 综合距离、交通条件、路网走向等因素，给出最优访问顺序和路线方案

## 地址数据（含坐标）
{addresses_text}

## 出行参数
- 出行方式: {travel_mode}
- 出发点: {start_address}
- 特殊要求: {requirements}
- 途经点偏好: {waypoints}

## 分析要求
1. 识别出现频率最高的点位，优先覆盖这些高频点
2. 分析点位的地理分布和聚合情况，将邻近点位分为1-3个片区
3. 每个片区生成一条独立路线，每线不超过5个核心点位
4. 每条路线内部的点位顺序须严格按顺路原则排布（最近邻贪心+局部优化），确保不走回头路
5. 结合出行方式和实际路网，合理估算每段距离和时间
6. 提供实用的交通建议和稽核注意事项

## 返回格式（严格JSON，不要包含其他文字，不要markdown代码块标记）
{{
  "analysis": {{
    "total_locations": <有效地址总数>,
    "density_analysis": "<密度分布和频次分析>",
    "cluster_analysis": "<聚合分析和路线分组逻辑>"
  }},
  "routes": [
    {{
      "name": "<路线名称，体现区域特征>",
      "description": "<路线描述20-50字>",
      "total_distance_km": <总距离公里数>,
      "total_duration_minutes": <总时间分钟数>,
      "priority_score": <0-1之间的推荐优先级评分>,
      "waypoints": [
        {{"order": 1, "address": "<地址>", "lat": <纬度>, "lon": <经度>, "frequency": <频次整数>, "note": "<选点理由>"}}
      ],
      "segments": [
        {{"from": "<起点>", "to": "<终点>", "distance_km": <距离>, "duration_minutes": <时间>, "mode": "<出行方式>", "instruction": "<行车指引>"}}
      ]
    }}
  ],
  "traffic_advice": "<交通建议50-150字>",
  "cautions": ["<注意事项1>", "<注意事项2>"]
}}"""

ROUTE_PLANNING_PROMPT = """你是一个专业的出行路线规划师。请基于提供的地址数据，综合考虑地理分布、交通状况、时间效率等因素，为用户规划最佳出行路线。

**重要：你必须且只能返回一个纯JSON对象。不要包含markdown代码块标记，不要包含任何解释性文字。你的整个响应必须是一个合法的JSON。**

## 地址数据（含坐标）
{addresses_text}

## 出行参数
- 出行方式: {travel_mode}
- 出发点: {start_address}
- 特殊要求: {requirements}
- 途经点偏好: {waypoints}

## 分析要求
1. 分析地址的密度分布和地理聚合情况，排除明显的地理噪音点
2. 识别合理的访问顺序（考虑顺路程度和实际路网走向）
3. 结合出行方式，估算每段距离和时间（参考中国实际路网和交通规律）
4. 提供交通建议和注意事项
5. 如果地址分布较广，提供多条备选路线方案

## 返回格式（严格JSON，不要包含其他文字，不要markdown代码块标记）
{{
  "analysis": {{
    "total_locations": <有效地址总数>,
    "density_analysis": "<地址密度和地理分布分析>",
    "cluster_analysis": "<聚合情况分析>"
  }},
  "routes": [
    {{
      "name": "<路线名称>",
      "description": "<路线描述20-50字>",
      "total_distance_km": <总距离公里数>,
      "total_duration_minutes": <总时间分钟数>,
      "priority_score": <0-1之间的推荐优先级评分>,
      "waypoints": [
        {{"order": 1, "address": "<地址>", "lat": <纬度>, "lon": <经度>, "note": "<简短备注>"}}
      ],
      "segments": [
        {{"from": "<起点>", "to": "<终点>", "distance_km": <距离>, "duration_minutes": <时间>, "mode": "<出行方式>", "instruction": "<行车指引>"}}
      ]
    }}
  ],
  "traffic_advice": "<交通建议50-150字>",
  "cautions": ["<注意事项1>", "<注意事项2>"]
}}"""


# ── 提示词模式注册表 ───────────────────────────────────────────
ROUTE_PROMPTS = {
    "general": {"name": "通用出行规划", "template": ROUTE_PLANNING_PROMPT},
    "audit": {"name": "稽核任务选址", "template": ROUTE_PLANNING_AUDIT_PROMPT},
}


ROUTE_DESCRIPTION_PROMPT = """你是一个旅游路线描述专家。为以下推荐路线生成简洁生动的描述（50-100字中文）。

## 路线信息
- **路线名称**: {route_name}
- **途经点**: {waypoints_text}
- **总距离**: {total_distance_km} km
- **覆盖位置数**: {total_locations}
- **策略**: {strategy}

请用中文生成一段描述，突出这条路线的特点和推荐理由。"""


def get_route_prompt(mode: str = "general") -> dict:
    """获取路线规划提示词模板。返回 {"name": ..., "template": ...}。"""
    return ROUTE_PROMPTS.get(mode, ROUTE_PROMPTS["general"])
