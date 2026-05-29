"""Unsplash图片服务"""

import time
import requests
from typing import List, Optional, Dict
from ..config import get_settings

# 进程内缓存: query → (photo_url, timestamp)
_cache: Dict[str, tuple] = {}
_CACHE_TTL = 3600  # 1小时

class UnsplashService:
    """Unsplash图片服务类"""

    def __init__(self):
        """初始化服务"""
        settings = get_settings()
        self.access_key = settings.unsplash_access_key
        self.base_url = "https://api.unsplash.com"

    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        """
        搜索图片

        Args:
            query: 搜索关键词
            per_page: 每页数量

        Returns:
            图片列表
        """
        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "per_page": per_page,
                "client_id": self.access_key
            }

            response = requests.get(url, params=params, timeout=10)

            # 处理限流
            if response.status_code == 403 and "Rate Limit Exceeded" in response.text:
                print(f"⚠️ Unsplash 免费额度耗尽 (50次/小时)")
                return []
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            # 提取图片URL
            photos = []
            for photo in results:
                photos.append({
                    "id": photo.get("id"),
                    "url": photo.get("urls", {}).get("regular"),
                    "thumb": photo.get("urls", {}).get("thumb"),
                    "description": photo.get("description") or photo.get("alt_description"),
                    "photographer": photo.get("user", {}).get("name")
                })

            return photos

        except Exception as e:
            print(f"❌ Unsplash搜索失败: {str(e)[:100]}")
            return []

    def get_photo_url(self, query: str) -> Optional[str]:
        """
        获取单张图片URL (带缓存)

        Args:
            query: 搜索关键词

        Returns:
            图片URL
        """
        global _cache
        now = time.time()
        # 清理过期缓存
        _cache = {k: v for k, v in _cache.items() if now - v[1] < _CACHE_TTL}

        if query in _cache:
            return _cache[query][0]

        # 先精确搜索
        photos = self.search_photos(query, per_page=1)
        if photos:
            url = photos[0].get("url")
            if url:
                _cache[query] = (url, now)
                return url

        # 降级: 只用景点名搜索(去掉城市)
        parts = query.split()
        if len(parts) > 1:
            short_query = parts[0]
            if short_query not in _cache:
                photos = self.search_photos(short_query, per_page=1)
                if photos:
                    url = photos[0].get("url")
                    if url:
                        _cache[short_query] = (url, now)
                        return url

        return None


# 全局服务实例
_unsplash_service = None


def get_unsplash_service() -> UnsplashService:
    """获取Unsplash服务实例(单例模式)"""
    global _unsplash_service
    
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    
    return _unsplash_service

