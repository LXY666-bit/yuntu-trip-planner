"""小红书搜索服务 - 基于 Spider_XHS 原生签名引擎

使用本地 JS 签名 + 直连 edith.xiaohongshu.com API，
搜索真实游记并提纯景点信息。
"""

import json
import re
import logging
import requests
import httpx
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..config import get_settings

# Early check: XHS signing engine requires PyExecJS + Node.js
_XHS_SIGN_AVAILABLE = False
try:
    from .xhs_sign.sign_util import generate_request_params
    _XHS_SIGN_AVAILABLE = True
except Exception as e:
    print(f"❌ 小红书签名引擎加载失败: {e}")
    print(f"   请运行: pip install PyExecJS>=1.5.1 并确认 Node.js 已安装")

logger = logging.getLogger(__name__)


class XHSCookieExpiredError(Exception):
    """小红书 Cookie 过期致命异常"""
    pass


def normalize_xhs_cookie(cookie: str) -> str:
    """兼容 Cookie 请求头字符串和浏览器导出的 JSON Cookie 列表。"""
    normalized = cookie.strip()
    if not normalized:
        return normalized

    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()

    cookie_items = None
    if normalized.startswith("[") and normalized.endswith("]"):
        try:
            cookie_items = json.loads(normalized)
        except json.JSONDecodeError:
            cookie_items = None
    elif normalized.startswith("{") and '"name"' in normalized and '"value"' in normalized:
        try:
            cookie_items = json.loads(f"[{normalized}]")
        except json.JSONDecodeError:
            cookie_items = None

    if isinstance(cookie_items, list):
        pairs = []
        for item in cookie_items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            value = str(item.get("value", "")).strip()
            if name:
                pairs.append(f"{name}={value}")
        if pairs:
            print("已将 JSON 格式的小红书 Cookie 转换为请求头字符串格式。")
            return "; ".join(pairs)

    return normalized


class XhsNativeClient:
    """使用 Spider_XHS 签名引擎直连小红书 API 的原生客户端。"""
    BASE_URL = "https://edith.xiaohongshu.com"

    def __init__(self, cookies_str: str):
        self.cookies_str = cookies_str

    def search_notes(self, keyword: str, page: int = 1, sort_type: int = 0,
                     page_size: int = 20) -> dict:
        api = "/api/sns/web/v1/search/notes"
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": self._generate_traceid(21),
            "sort": "general",
            "note_type": 0,
            "ext_flags": [],
            "filters": [
                {"tags": ["general"], "type": "sort_type"},
                {"tags": ["不限"], "type": "filter_note_type"},
                {"tags": ["不限"], "type": "filter_note_time"},
                {"tags": ["不限"], "type": "filter_note_range"},
                {"tags": ["不限"], "type": "filter_pos_distance"},
            ],
            "geo": "",
            "image_formats": ["jpg", "webp", "avif"],
        }

        from .xhs_sign.sign_util import generate_request_params
        headers, cookies, serialized_data = generate_request_params(
            self.cookies_str, api, data, "POST"
        )
        response = requests.post(
            self.BASE_URL + api,
            headers=headers,
            data=serialized_data.encode("utf-8"),
            cookies=cookies,
            timeout=15,
        )
        res_json = response.json()

        if not res_json.get("success"):
            code = res_json.get("code", "")
            msg = res_json.get("msg", "")
            if code == 300011 or "异常" in msg:
                raise XHSCookieExpiredError(
                    f"小红书 Cookie 已被风控拦截 (code={code}): {msg}。请更换 Cookie 后重试。"
                )
            raise Exception(f"小红书搜索失败 (code={code}): {msg}")

        return res_json

    def get_note_detail(self, note_id: str, xsec_token: str = "",
                        xsec_source: str = "pc_search") -> dict:
        api = "/api/sns/web/v1/feed"
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }

        from .xhs_sign.sign_util import generate_request_params
        headers, cookies, serialized_data = generate_request_params(
            self.cookies_str, api, data, "POST"
        )
        response = requests.post(
            self.BASE_URL + api,
            headers=headers,
            data=serialized_data,
            cookies=cookies,
            timeout=15,
        )
        res_json = response.json()

        if not res_json.get("success"):
            code = res_json.get("code", "")
            msg = res_json.get("msg", "")
            if code == 300011 or "异常" in msg:
                raise XHSCookieExpiredError(
                    f"小红书 Cookie 已被风控拦截 (code={code}): {msg}"
                )

        return res_json

    @staticmethod
    def _generate_traceid(length: int = 16) -> str:
        import math, random
        chars = "abcdef0123456789"
        return "".join(chars[math.floor(16 * random.random())] for _ in range(length))


def get_xhs_client() -> XhsNativeClient:
    """初始化并返回原生小红书客户端"""
    settings = get_settings()
    xhs_cookie = getattr(settings, 'xhs_cookie', '') or ''
    if not xhs_cookie:
        raise XHSCookieExpiredError("小红书 Cookie 未配置，请先在 .env 中设置 XHS_COOKIE")
    cookie_str = normalize_xhs_cookie(xhs_cookie)
    return XhsNativeClient(cookie_str)


_xhs_cookie_validated = False
_xhs_cookie_is_valid = False


def is_xhs_available() -> bool:
    """检查小红书服务是否可用 (Cookie已配置 且 签名引擎已加载)"""
    if not _XHS_SIGN_AVAILABLE:
        return False
    settings = get_settings()
    return bool(getattr(settings, 'xhs_cookie', '') or '')


def validate_xhs_cookie():
    """启动时尝试验证 Cookie 有效性 (仅打印日志，不阻止使用)"""
    global _xhs_cookie_validated
    if _xhs_cookie_validated:
        return
    _xhs_cookie_validated = True
    if not is_xhs_available():
        return
    try:
        settings = get_settings()
        cookie = getattr(settings, 'xhs_cookie', '') or ''
        client = XhsNativeClient(normalize_xhs_cookie(cookie))
        res = client.search_notes(keyword="旅游", page_size=2)
        items = res.get("data", {}).get("items", [])
        if items:
            print(f"✅ [XHS] Cookie 有效，搜索测试返回 {len(items)} 条结果")
        else:
            print(f"⚠️ [XHS] Cookie 验证搜索返回空结果 — 如果实际搜索也失败，请重新获取 Cookie")
    except XHSCookieExpiredError:
        print(f"❌ [XHS] Cookie 已被风控拦截(300011)，请更换 Cookie")
    except Exception as e:
        print(f"⚠️ [XHS] Cookie 验证请求失败: {str(e)[:100]}")


def _geocode_amap_raw(address: str, city: str) -> dict:
    """高德 Web 服务地理编码（默认兜底）。"""
    settings = get_settings()
    amap_key = getattr(settings, 'vite_amap_web_key', '') or getattr(settings, 'amap_api_key', '')
    if not amap_key:
        return {"longitude": 116.397128, "latitude": 39.916527}

    url = f"https://restapi.amap.com/v3/place/text?keywords={address}&city={city}&offset=1&key={amap_key}"
    try:
        resp = httpx.get(url, timeout=5)
        data = resp.json()
        if data.get("status") == "1" and data.get("pois") and len(data["pois"]) > 0:
            location = data["pois"][0]["location"]
            lon, lat = location.split(",")
            return {"longitude": float(lon), "latitude": float(lat)}
    except Exception as e:
        print(f"高德地理编码查询失败 ({address}): {e}")

    return {"longitude": 116.397128, "latitude": 39.916527}


def _get_note_detail_ssr(note_id: str) -> dict:
    """通过网页抓取 SSR 状态提取笔记详情，作为原生 API 的降级备选"""
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=8)
        match = re.search(r'window\.__INITIAL_STATE__=({.*?})</script>', resp.text)
        if match:
            state_json = json.loads(match.group(1).replace('undefined', 'null'))
            return state_json.get("note", {}).get("noteDetailMap", {}).get(note_id, {}).get("note", {})
    except Exception as e:
        print(f"SSR详情提取失败 {note_id}: {e}")
    return {}


def search_xhs_attractions(city: str, keywords: str, language: str = "zh") -> str:
    """
    搜索小红书笔记，使用大模型极速提纯出结构化景点，
    并静默拼装经纬度，回传给Planner。

    Args:
        city: 城市名称
        keywords: 搜索关键词
        language: 目标输出语言 (zh/en/ja 等)
    """
    print(f"🔍 [XHS_SERVICE] 正在呼叫小红书 API 搜索: {city} {keywords}")
    if not _XHS_SIGN_AVAILABLE:
        print(f"⚠️ 小红书签名引擎不可用，跳过景点搜索: {city} {keywords}")
        return f"未在小红书检索到关于 {city} {keywords} 的内容。"

    client = get_xhs_client()
    query = f"{city} {keywords} 旅游 景点攻略"

    try:
        res_json = client.search_notes(keyword=query)
        all_items = res_json.get("data", {}).get("items", [])
        if not all_items:
            raw_keys = list(res_json.keys())
            data_keys = list(res_json.get("data", {}).keys()) if isinstance(res_json.get("data"), dict) else "non-dict"
            print(f"⚠️ [XHS_SERVICE] API 返回成功但 items 为空, query={query}")
            print(f"   response keys: {raw_keys}, data keys: {data_keys}, data type: {type(res_json.get('data')).__name__}")

        # 先过滤出笔记类型，再截取前4条（避免非笔记类型占位导致全部跳过）
        note_items = [item for item in all_items if item.get("model_type") == "note"]
        if not note_items:
            print(f"⚠️ [XHS_SERVICE] 所有 {len(all_items)} 条 items 均非笔记类型")

        items = note_items[:4]

        # 并行获取笔记详情
        MAX_NOTE_TEXT = 800  # 每条笔记最大字符数，控制 LLM prompt 大小
        combined_parts: List[tuple] = []  # (index, text)

        def _fetch_note_detail(idx_note):
            """获取单条笔记详情，返回 (index, note_text) 或 None"""
            idx, note = idx_note
            note_card = note.get("note_card", {})
            title = note_card.get("display_title", "")
            desc = ""
            try:
                note_id = note.get("id", "")
                xsec_token = note.get("xsec_token", "")
                if note_id:
                    detail_res = client.get_note_detail(note_id, xsec_token)
                    detail_items = detail_res.get("data", {}).get("items", [])
                    if detail_items:
                        note_data = detail_items[0].get("note_card", {})
                        desc = note_data.get("desc", "")
                    else:
                        print(f"⚠️ [XHS_SERVICE] get_note_detail 返回空 items, note_id={note_id}")
            except Exception as e:
                print(f"⚠️ [XHS_SERVICE] get_note_detail 失败 note_id={note.get('id','')}: {str(e)[:100]}")
                try:
                    note_id = note.get("id", "")
                    if note_id:
                        detail = _get_note_detail_ssr(note_id)
                        desc = detail.get("desc", "")
                        if desc:
                            print(f"✅ [XHS_SERVICE] SSR 降级成功 note_id={note_id}")
                except Exception as e2:
                    print(f"⚠️ [XHS_SERVICE] SSR 降级也失败: {str(e2)[:80]}")
                    desc = ""
            if not desc:
                print(f"⚠️ [XHS_SERVICE] 笔记 {idx+1} '{title}' 无正文内容")
            text = f"{title}\n{desc}"
            if len(text) > MAX_NOTE_TEXT:
                text = text[:MAX_NOTE_TEXT] + "..."
            return (idx, f"\n笔记{idx+1}:\n标题: {title}\n正文内容: {desc[:MAX_NOTE_TEXT]}\n")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_fetch_note_detail, (i, n)): i for i, n in enumerate(items)}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    combined_parts.append(result)

        combined_parts.sort(key=lambda x: x[0])
        combined_text = "".join(p[1] for p in combined_parts)

    except XHSCookieExpiredError:
        raise
    except Exception as e:
        print(f"❌ 小红书接口抓取失败: {e}")
        raise XHSCookieExpiredError(
            f"小红书访问超时或 Cookie 失效(风控拦截)，抓取失败。请更新 XHS_COOKIE"
        )

    if not combined_text:
        return f"未在小红书检索到关于 {city} {keywords} 的内容。"

    # LLM 提纯 — 使用快速 LLM 实例 (30s 超时, 4096 tokens)
    print(f"🧠 [XHS_SERVICE] 正在调用 LLM 提纯小红书游记...")
    from .llm_service import get_llm
    llm = get_llm()

    extract_prompt = f"""
请从以下真实的素人小红书打卡游记中，提纯出真实存在的【游玩景点】。
要求返回严格的 JSON 数组格式(哪怕只提取到了1个)，切勿返回除了JSON以外的任何冗余 markdown 文字！

数组中每个对象必须包含以下字段:
"name": 景点官方名称
"name_zh": 景点的中文简体名称
"name_en": 景点的英文名称
"reason": 小红书用户的真实评价/避坑指南
"duration": 游玩时长(数字, 分钟)
"reservation_required": 是否需要提前预约(布尔值 true/false)。请根据游记中提到的"需要预约"、"提前预约"、"抢票"、"约满"、"官方预约"等关键词判断，如果游记未提及则默认为 false
"reservation_tips": 预约相关提示(字符串)。如果需要预约，请提取预约渠道、提前天数等具体信息；如果不需要预约则填空字符串

游记杂文内容如下:
{combined_text}

JSON 返回示例:
[
  {{"name": "故宫博物院", "name_zh": "故宫博物院", "name_en": "The Palace Museum", "reason": "必去打卡，建议走中轴线。", "duration": 240, "reservation_required": true, "reservation_tips": "需要提前7天在故宫官网或微信小程序预约，每日限流8万人"}},
  {{"name": "老君山金顶", "name_zh": "老君山金顶", "name_en": "Laojun Mountain Golden Summit", "reason": "网红打卡点，夜景绝美，必须坐索道上山。", "duration": 180, "reservation_required": false, "reservation_tips": ""}}
]
"""
    try:
        response = llm.invoke(extract_prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
        else:
            json_str = content

        # JSON 多层修复 (TripStar 模式): 尝试多种修复策略, 逐个尝试直到成功
        from ..agents.langgraph_agent.utils.parsing import (
            _sanitize_json_str,
            _fix_unescaped_quotes,
            _repair_truncated_json,
        )

        candidates: List[tuple] = [
            ("基础清理",           _sanitize_json_str(json_str)),
            ("修复未转义引号",     _fix_unescaped_quotes(_sanitize_json_str(json_str))),
            ("截断修复",           _repair_truncated_json(_sanitize_json_str(json_str))),
            ("截断+引号修复",      _fix_unescaped_quotes(_repair_truncated_json(_sanitize_json_str(json_str)))),
        ]

        extracted = None
        last_error = None
        for label, candidate in candidates:
            try:
                extracted = json.loads(candidate)
                break
            except json.JSONDecodeError as e:
                last_error = e

        # 最后手段: 正则逐对象提取 — 匹配每个独立的 {...} 对象
        if extracted is None:
            print(f"  ⚠️ 多层修复均失败, 尝试正则逐对象提取...")
            obj_matches = re.findall(r'\{[^{}]*\}', json_str, re.DOTALL)
            if obj_matches:
                extracted = []
                for obj_str in obj_matches:
                    try:
                        obj = json.loads(_sanitize_json_str(obj_str))
                        if obj.get("name"):
                            extracted.append(obj)
                    except json.JSONDecodeError:
                        continue
                if extracted:
                    print(f"  ✅ 正则提取成功 {len(extracted)} 个对象")

        if extracted is None:
            raise last_error or ValueError("无法解析 LLM 返回的 JSON")

        # 并行地理编码所有提取的 POI
        final_result = f"这是小红书热门精选游记的提取结果，附带确切坐标（图片由前端单独搜索获取）：\n"
        valid_items = [(item, item.get("name", "")) for item in extracted if item.get("name")]

        def _geocode_item(item_and_name):
            item, name = item_and_name
            loc = _geocode_amap_raw(name, city)
            item["location"] = loc
            return item

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(_geocode_item, valid_items))

        for item in results:
            final_result += json.dumps(item, ensure_ascii=False) + "\n"

        print(f"✅ [XHS_SERVICE] 小红书数据挖掘完毕，已装载进上下文。")
        return final_result

    except Exception as e:
        print(f"❌ 大模型提纯小红书数据异常: {e}")
        return "尝试提取小红书结构化数据失败，降级回常规处理。"


def get_xhs_photo_sync(keyword: str) -> str:
    """根据关键词从小红书搜索一张首图URL"""
    if not _XHS_SIGN_AVAILABLE:
        print(f"⚠️ 小红书签名引擎不可用，跳过图片搜索: {keyword}")
        return ""
    try:
        client = get_xhs_client()
        res_json = client.search_notes(keyword=keyword, sort_type=0)
        items = res_json.get("data", {}).get("items", [])

        target_note_id = None
        target_xsec_token = ""
        for note in items:
            if note.get("model_type") == "note":
                target_note_id = note.get("id")
                target_xsec_token = note.get("xsec_token", "")
                break

        if not target_note_id:
            return ""

        # 原生 API 获取图片
        try:
            detail_res = client.get_note_detail(target_note_id, target_xsec_token)
            detail_items = detail_res.get("data", {}).get("items", [])
            if detail_items:
                note_card = detail_items[0].get("note_card", {})
                image_list = note_card.get("image_list", [])
                if image_list:
                    first_img = image_list[0]
                    info_list = first_img.get("info_list", [])
                    if len(info_list) > 1:
                        return info_list[1].get("url", "")
                    elif info_list:
                        return info_list[0].get("url", "")
                    return (
                        first_img.get("url_default", "")
                        or first_img.get("url_pre", "")
                        or first_img.get("url", "")
                    )
        except Exception:
            pass

        # SSR 降级
        url = f"https://www.xiaohongshu.com/explore/{target_note_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = httpx.get(url, headers=headers, timeout=10)
        match = re.search(r'window\.__INITIAL_STATE__=({.*?})</script>', resp.text)
        if match:
            state_json_str = match.group(1).replace("undefined", "null")
            state_json = json.loads(state_json_str)
            note_data = (
                state_json.get("note", {})
                .get("noteDetailMap", {})
                .get(target_note_id, {})
                .get("note", {})
            )
            img_list = note_data.get("imageList", [])
            if img_list:
                first_img = (
                    img_list[0].get("urlDefault")
                    or img_list[0].get("urlPattern")
                    or img_list[0].get("url")
                )
                if first_img:
                    return first_img

    except Exception as e:
        print(f"小红书单图抓取失败 ({keyword}): {e}")
    return ""


async def get_photo_from_xhs(keyword: str) -> str:
    """供异步环境调用的小红书图片搜索API"""
    import asyncio
    return await asyncio.to_thread(get_xhs_photo_sync, keyword)
