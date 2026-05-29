import json
import re
import os
from typing import Dict, Any, List, Optional

from ....models.schemas import TripPlan, TripRequest, DayPlan, Attraction, Meal


def _extract_json_array(text: str) -> Optional[List[Dict]]:
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    bracket_pattern = re.compile(r'\[[\s\S]*?\]', re.DOTALL)
    for match in bracket_pattern.finditer(text):
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            continue
    return None


def _build_poi_dict(poi: Dict) -> Dict:
    """从 AMap POI 数据构建完整字段字典，兼容 MCP 层不同序列化格式。"""
    result = {
        "id": poi.get("id", ""),
        "name": poi["name"],
        "address": poi.get("address", ""),
        "location": poi.get("location", ""),
        "type": poi.get("type", ""),
    }
    photos = poi.get("photos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        result["photo"] = first.get("url", "") if isinstance(first, dict) else str(first)
    else:
        result["photo"] = poi.get("photo", "")

    biz_ext = poi.get("biz_ext")
    if isinstance(biz_ext, dict):
        result["rating"] = biz_ext.get("rating", "")
        result["cost"] = biz_ext.get("cost", "")
    else:
        result["rating"] = poi.get("rating", "")
        result["cost"] = poi.get("cost", "")

    return result


def _extract_poi_names(text: str) -> List[Dict]:
    pois = []
    try:
        data = None
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    data = parsed
                elif isinstance(parsed, dict):
                    data = [parsed]
            except json.JSONDecodeError:
                pass

            if data is None:
                try:
                    import ast
                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, list):
                        data = parsed
                    elif isinstance(parsed, dict):
                        data = [parsed]
                except (ValueError, SyntaxError):
                    pass

            if data is None:
                for line in text.split('\n'):
                    line = line.strip()
                    if line.startswith("'text':") or line.startswith('"text":'):
                        content = line.split(':', 1)[1].strip().strip(',').strip('"').strip("'")
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict) and "pois" in parsed:
                                data = [parsed]
                                break
                        except json.JSONDecodeError:
                            continue

        if data is None:
            json_start = text.find('{')
            if json_start >= 0:
                json_end = text.rfind('}') + 1
                try:
                    parsed = json.loads(text[json_start:json_end])
                    if isinstance(parsed, dict) and "pois" in parsed:
                        data = [parsed]
                except json.JSONDecodeError:
                    pass

        if data:
            for item in data:
                if isinstance(item, dict) and "text" in item:
                    try:
                        inner = json.loads(item["text"]) if isinstance(item["text"], str) else item["text"]
                        if isinstance(inner, dict) and "pois" in inner:
                            for poi in inner["pois"]:
                                if "name" in poi:
                                    pois.append(_build_poi_dict(poi))
                    except (json.JSONDecodeError, TypeError):
                        continue
                elif isinstance(item, dict) and "pois" in item:
                    for poi in item["pois"]:
                        if "name" in poi:
                            pois.append(_build_poi_dict(poi))
    except Exception:
        pass

    return pois


# ============ 多层容错 JSON 解析 (移植自 TripStar) ============

def _sanitize_json_str(json_str: str) -> str:
    """清理大模型输出中常见的 JSON 格式污染"""
    # 1. 移除可能包裹在外面的 ```json ... ``` 标记
    json_str = re.sub(r'^```(?:json)?\s*', '', json_str.strip())
    json_str = re.sub(r'```\s*$', '', json_str.strip())
    # 2. 移除 JS 风格注释 // ... 和 /* ... */
    json_str = re.sub(r'//[^\n]*', '', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    # 3. 移除 JSON 值中的控制字符
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
    # 4. 修复尾部逗号: },] 或 },}
    json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
    # 5. 修复中文引号和全角标点
    json_str = json_str.replace('“', "'").replace('”', "'")
    json_str = json_str.replace('‘', "'").replace('’', "'")
    json_str = json_str.replace('：', ':')
    json_str = json_str.replace('，', ',')
    # 6. 修复 LLM 在 budget 等数值字段中输出算术表达式的问题
    def _fix_arithmetic_expr(m):
        expr = m.group(1).strip()
        if '=' in expr:
            return m.group(0).replace(m.group(1), expr.split('=')[-1].strip())
        else:
            try:
                result = eval(expr, {"__builtins__": {}}, {})
                return m.group(0).replace(m.group(1), str(result))
            except Exception:
                return m.group(0)
    json_str = re.sub(
        r':\s*(\d+(?:\s*[+\-*/]\s*\d+)+(?:\s*=\s*\d+)?)',
        _fix_arithmetic_expr,
        json_str
    )
    # 7. 移除常见标记词前缀
    json_str = re.sub(r'^.*?```(?:json)?\s*', '', json_str, flags=re.DOTALL)
    return json_str


def _fix_unescaped_quotes(json_str: str) -> str:
    """修复 JSON 字符串值内部未转义的双引号"""
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(json_str):
        ch = json_str[i]

        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue

        if ch == '\\' and in_string:
            escape_next = True
            result.append(ch)
            i += 1
            continue

        if ch == '"':
            if not in_string:
                in_string = True
                result.append(ch)
            else:
                rest = json_str[i+1:].lstrip()
                if rest and rest[0] in (',', '}', ']', ':'):
                    in_string = False
                    result.append(ch)
                elif not rest:
                    in_string = False
                    result.append(ch)
                else:
                    result.append("'")
        else:
            result.append(ch)

        i += 1

    return ''.join(result)


def _repair_truncated_json(json_str: str) -> str:
    """修复被 max_tokens 截断的不完整 JSON。"""
    s = json_str.rstrip()
    if not s:
        return s

    # Step 1: 关闭未终止的字符串
    in_str = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
    if in_str:
        s = s.rstrip('\\')
        s += '"'

    # Step 2: 移除尾部不完整的键值对碎片
    for _ in range(10):
        stripped = s.rstrip()
        if not stripped:
            break
        last = stripped[-1]
        if last in ('}', ']', '"', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'e', 'l', 's'):
            break
        s = stripped[:-1]

    # 移除尾部悬挂的逗号
    s = re.sub(r',\s*$', '', s)

    # Step 3: 补齐缺失的闭合括号
    stack = []
    in_str2 = False
    esc2 = False
    for ch in s:
        if esc2:
            esc2 = False
            continue
        if ch == '\\' and in_str2:
            esc2 = True
            continue
        if ch == '"':
            in_str2 = not in_str2
            continue
        if in_str2:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    closing = [']' if c == '[' else '}' for c in reversed(stack)]
    if closing:
        s += '\n' + ''.join(closing)

    return s


def _llm_repair_json(broken_json: str) -> str:
    """使用 LLM 修复无法自动修复的 JSON（最后手段）"""
    from ....services.llm_service import get_llm
    llm = get_llm()
    tail = broken_json[-2000:] if len(broken_json) > 2000 else broken_json
    head = broken_json[:500] if len(broken_json) > 500 else broken_json

    repair_prompt = f"""以下是一段被截断的旅行计划 JSON，请你补全它使其成为合法的 JSON。
只输出修复后的完整 JSON，不要输出任何解释文字。

开头部分:
{head}

...(中间省略)...

尾部被截断部分:
{tail}
"""
    try:
        response = llm.invoke(repair_prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return match.group()
        return content
    except Exception as e:
        print(f"⚠️  LLM 修复 JSON 失败: {e}")
        return broken_json


def _repair_json(json_str: str) -> str:
    """简单 JSON 修复（向后兼容旧代码）"""
    return _sanitize_json_str(json_str)


def _validate_plan_coordinates(trip_plan: TripPlan) -> TripPlan:
    for day in trip_plan.days:
        for attr in day.attractions:
            if attr.location is not None:
                lon = attr.location.longitude
                lat = attr.location.latitude
                if not (73 < lon < 136 and 3 < lat < 54):
                    attr.location = None
        for meal in day.meals:
            if meal.location is not None:
                lon = meal.location.longitude
                lat = meal.location.latitude
                if not (73 < lon < 136 and 3 < lat < 54):
                    meal.location = None
    return trip_plan


def _parse_response(response_text: str, request: TripRequest) -> TripPlan:
    """
    解析Agent响应，带有多层容错清理 (移植自 TripStar)

    Args:
        response_text: Agent响应文本
        request: 原始请求

    Returns:
        旅行计划
    """
    try:
        # 尝试从响应中提取JSON
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            if json_end == -1 or json_end <= json_start:
                json_str = response_text[json_start:].strip()
            else:
                json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            if json_end == -1 or json_end <= json_start:
                json_str = response_text[json_start:].strip()
            else:
                json_str = response_text[json_start:json_end].strip()
        elif "{" in response_text:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}")
            if json_end > json_start:
                json_str = response_text[json_start:json_end + 1]
            else:
                json_str = response_text[json_start:]
        else:
            raise ValueError("响应中未找到JSON数据")

        # ====== 第1轮：基础清理 + 解析 ======
        json_str = _sanitize_json_str(json_str)

        parse_attempts = [
            ("基础清理", json_str),
        ]

        # 预生成各轮修复候选
        fixed_quotes = _fix_unescaped_quotes(json_str)
        parse_attempts.append(("修复未转义引号", fixed_quotes))

        # 截断修复
        repaired = _repair_truncated_json(json_str)
        if repaired != json_str:
            parse_attempts.append(("截断修复", repaired))
            repaired_fixed = _fix_unescaped_quotes(repaired)
            if repaired_fixed != repaired:
                parse_attempts.append(("截断+引号修复", repaired_fixed))

        # 暴力正则提取
        match = re.search(r'\{[\s\S]*\}', json_str)
        if match:
            brutal = _sanitize_json_str(match.group())
            brutal = _fix_unescaped_quotes(brutal)
            parse_attempts.append(("正则提取", brutal))
            brutal_repaired = _repair_truncated_json(brutal)
            if brutal_repaired != brutal:
                parse_attempts.append(("正则+截断修复", brutal_repaired))

        # 依次尝试每种修复
        last_error = None
        for attempt_name, candidate in parse_attempts:
            try:
                data = json.loads(candidate)
                if attempt_name != "基础清理":
                    print(f"✅ JSON 通过「{attempt_name}」成功解析")
                return TripPlan(**data)
            except (json.JSONDecodeError, Exception) as e:
                last_error = e
                if attempt_name == "基础清理":
                    pos = e.pos if hasattr(e, 'pos') else 0
                    context_start = max(0, pos - 60)
                    context_end = min(len(candidate), pos + 60)
                    print(f"⚠️  首次 JSON 解析失败: {e}")
                    print(f"   出错位置附近内容: ...{candidate[context_start:context_end]}...")
                else:
                    print(f"⚠️  「{attempt_name}」仍失败: {e}")

        # ====== 最终手段：LLM 修复 ======
        print("🔧 所有本地修复均失败，尝试使用 LLM 修复 JSON...")
        llm_fixed = _llm_repair_json(json_str)
        llm_fixed = _sanitize_json_str(llm_fixed)
        try:
            data = json.loads(llm_fixed)
            print("✅ JSON 通过 LLM 修复成功解析")
            return TripPlan(**data)
        except Exception as e_llm:
            print(f"⚠️  LLM 修复后仍然解析失败: {e_llm}")
            raise ValueError(f"行程 JSON 解析失败: {str(last_error)}") from last_error

    except ValueError:
        raise
    except Exception as e:
        print(f"⚠️  解析响应失败: {str(e)}")
        raise ValueError(f"行程 JSON 解析失败: {str(e)}") from e


def _create_fallback_plan(request: TripRequest, state: Dict[str, Any] = None) -> TripPlan:
    from datetime import datetime, timedelta

    state = state or {}
    attractions_info = state.get("attractions_info", "")
    hotels_info = state.get("hotels_info", "")

    poi_names = _extract_poi_names(attractions_info) if attractions_info else []

    start_date = datetime.strptime(request.start_date[:10], "%Y-%m-%d")

    days = []
    for i in range(request.travel_days):
        current_date = start_date + timedelta(days=i)

        day_attractions = []
        if poi_names:
            day_pois = poi_names[i * 2:(i + 1) * 2]
            for j, poi in enumerate(day_pois):
                day_attractions.append(Attraction(
                    name=poi.get("name", f"{request.city}景点{j+1}"),
                    address=poi.get("address", f"{request.city}市"),
                    location=None,
                    visit_duration=120,
                    description="推荐景点（数据来源受限，建议自行确认详情）",
                    category="景点"
                ))
        if not day_attractions:
            day_attractions = [Attraction(
                name=f"{request.city}推荐景点",
                address=f"{request.city}市",
                location=None,
                visit_duration=120,
                description="请自行查询景点详情",
                category="景点"
            )]

        day_plan = DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i+1}天行程",
            transportation=request.transportation,
            accommodation=request.accommodation,
            attractions=day_attractions,
            meals=[
                Meal(type="breakfast", name="当地特色早餐", description="当地特色早餐", cuisine="本地菜", source="nearby"),
                Meal(type="lunch", name="午餐推荐", description="午餐推荐", cuisine="本地菜", source="nearby"),
                Meal(type="dinner", name="晚餐推荐", description="晚餐推荐", cuisine="本地菜", source="popular")
            ]
        )
        days.append(day_plan)

    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],
        overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程。由于部分数据获取受限，建议提前确认各景点的开放时间和详情。"
    )
