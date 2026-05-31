"""Open-Meteo weather integration.

Open-Meteo does not require an API key for the public forecast endpoints.  We
use it as a medium-range weather fallback when AMap cannot cover the requested
trip dates.

Supports two modes:
1. 如果调用方提供了 lat/lon，直接使用坐标查询天气（推荐，跳过地理编码）
2. 如果只有城市名，先通过 Open-Meteo 地理编码 API 查坐标再查天气（对中文支持差）
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from ..models.schemas import WeatherInfo


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# 调用间隔控制（避免触发限流）
_MIN_CALL_INTERVAL: float = 0.3

WEATHER_CODE_TEXT = {
    0: "晴",
    1: "晴",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾",
    51: "小雨",
    53: "小雨",
    55: "中雨",
    56: "冻雨",
    57: "冻雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "阵雪",
    80: "阵雨",
    81: "阵雨",
    82: "暴雨",
    85: "阵雪",
    86: "大雪",
    95: "雷阵雨",
    96: "雷阵雨",
    99: "雷阵雨",
}


def _weather_text(code: Any) -> str:
    try:
        return WEATHER_CODE_TEXT.get(int(code), "多云")
    except (TypeError, ValueError):
        return "多云"


def _wind_direction(degrees: Any) -> str:
    try:
        deg = float(degrees) % 360
    except (TypeError, ValueError):
        return ""
    directions = [
        "北风",
        "东北风",
        "东风",
        "东南风",
        "南风",
        "西南风",
        "西风",
        "西北风",
    ]
    index = int((deg + 22.5) // 45) % 8
    return directions[index]


def _wind_power(speed: Any) -> str:
    try:
        return f"{round(float(speed))}km/h"
    except (TypeError, ValueError):
        return ""


class OpenMeteoWeatherService:
    async def _geocode_city(self, city: str, client: httpx.AsyncClient) -> Optional[tuple[float, float]]:
        names = [city]
        if city.endswith("市"):
            names.append(city[:-1])

        for name in names:
            resp = await client.get(
                GEOCODING_URL,
                params={
                    "name": name,
                    "count": 1,
                    "language": "zh",
                    "format": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if results:
                first = results[0]
                lat = first.get("latitude")
                lon = first.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        return None

    async def fetch_daily_weather(
        self,
        city: str,
        start_date: str,
        end_date: str,
        *,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> list[WeatherInfo]:
        """获取逐日天气预报。

        如果提供了 lat/lon 则直接查询天气预报（推荐方式，对中文城市友好）；
        否则先通过 Open-Meteo 地理编码 API 查坐标再查询天气。
        内置重试机制（最多 2 次，间隔 1s/2s）。
        """
        last_error: Optional[str] = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    latitude: float
                    longitude: float

                    if lat is not None and lon is not None:
                        latitude, longitude = lat, lon
                        print(f"[Open-Meteo] 使用传入坐标 ({lat:.4f}, {lon:.4f}) 查询 {city} 天气")
                    else:
                        coords = await self._geocode_city(city, client)
                        if not coords:
                            print(f"⚠️ Open-Meteo 未找到城市坐标: {city}")
                            return []
                        latitude, longitude = coords

                    resp = await client.get(
                        FORECAST_URL,
                        params={
                            "latitude": latitude,
                            "longitude": longitude,
                            "daily": ",".join([
                                "weather_code",
                                "temperature_2m_max",
                                "temperature_2m_min",
                                "wind_speed_10m_max",
                                "wind_direction_10m_dominant",
                            ]),
                            "timezone": "Asia/Shanghai",
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                    )
                    resp.raise_for_status()
                    result = _parse_daily_forecast(resp.json())
                    if result:
                        print(f"[Open-Meteo] 返回 {len(result)} 天天气: {[w.date for w in result]}")
                    else:
                        print(f"[Open-Meteo] 返回空结果: {city} {start_date}~{end_date}")
                    return result

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = f"网络错误(尝试{attempt+1}/3): {e}"
                print(f"  [Retry] {last_error}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}(尝试{attempt+1}/3): {e}"
                print(f"  [Retry] {last_error}")
                if attempt < 2 and e.response.status_code >= 500:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    break  # 4xx 不重试
            except Exception as e:
                last_error = f"未知错误(尝试{attempt+1}/3): {e}"
                print(f"  [Retry] {last_error}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))

        print(f"[Open-Meteo] 查询失败(已重试3次): {last_error}")
        return []


def _parse_daily_forecast(data: dict[str, Any]) -> list[WeatherInfo]:
    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    max_temps = daily.get("temperature_2m_max") or []
    min_temps = daily.get("temperature_2m_min") or []
    wind_speeds = daily.get("wind_speed_10m_max") or []
    wind_degrees = daily.get("wind_direction_10m_dominant") or []

    weather: list[WeatherInfo] = []
    for idx, date in enumerate(dates):
        text = _weather_text(codes[idx] if idx < len(codes) else None)
        weather.append(WeatherInfo(
            date=str(date),
            day_weather=text,
            night_weather=text,
            day_temp=round(float(max_temps[idx])) if idx < len(max_temps) and max_temps[idx] is not None else 0,
            night_temp=round(float(min_temps[idx])) if idx < len(min_temps) and min_temps[idx] is not None else 0,
            wind_direction=_wind_direction(wind_degrees[idx] if idx < len(wind_degrees) else None),
            wind_power=_wind_power(wind_speeds[idx] if idx < len(wind_speeds) else None),
        ))
    return weather


async def fetch_open_meteo_weather(
    city: str,
    start_date: str,
    end_date: str,
    *,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> list[WeatherInfo]:
    """获取 Open-Meteo 天气预报（便捷函数）。

    Args:
        city: 城市名（日志用）
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        lat: 纬度（可选，传入则跳过地理编码）
        lon: 经度（可选，传入则跳过地理编码）
    """
    service = OpenMeteoWeatherService()
    return await service.fetch_daily_weather(city, start_date, end_date, lat=lat, lon=lon)
