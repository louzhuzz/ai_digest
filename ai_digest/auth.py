from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib import parse, request

from .http_client import DEFAULT_TIMEOUT_SECONDS


# ── access_token 缓存 ──────────────────────────────────────

_token_cache: dict[str, dict[str, float]] = {}
_cache_lock = threading.Lock()


def _get_cached_token(appid: str) -> Optional[str]:
    """从内存缓存获取 access_token，未命中或已过期返回 None。"""
    with _cache_lock:
        entry = _token_cache.get(appid)
        if entry and time.time() < entry["expire_time"]:
            return entry["access_token"]
        if entry:
            del _token_cache[appid]
    return None


def _cache_token(appid: str, access_token: str, expires_in: int) -> None:
    """将 access_token 缓存到内存，提前 5 分钟过期以保证安全边际。"""
    with _cache_lock:
        _token_cache[appid] = {
            "access_token": access_token,
            "expire_time": time.time() + expires_in - 300,  # 提前 5 分钟过期
        }


def clear_token_cache(appid: str | None = None) -> None:
    """清除 access_token 缓存。appid=None 时清除全部。"""
    with _cache_lock:
        if appid:
            _token_cache.pop(appid, None)
        else:
            _token_cache.clear()


# ── access_token 客户端 ──────────────────────────────────────

@dataclass
class WeChatAccessTokenClient:
    appid: str
    appsecret: str
    http_client: object | None = None
    token_url: str = "https://api.weixin.qq.com/cgi-bin/token"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        获取 access_token，自动使用内存缓存。

        Args:
            force_refresh: 强制刷新 token，忽略缓存

        Returns:
            access_token 字符串

        Raises:
            RuntimeError: 请求失败时抛出
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cached = _get_cached_token(self.appid)
            if cached:
                return cached

        # 2. 调用微信 API 获取新 token
        query = parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.appsecret,
            }
        )
        url = f"{self.token_url}?{query}"
        opener = self.http_client or request.urlopen
        try:
            with opener(url, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"WeChat access token request failed: {exc}") from exc

        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"Failed to fetch access token: {payload}")

        # 3. 缓存 token（expires_in 默认 7200 秒）
        expires_in = payload.get("expires_in", 7200)
        _cache_token(self.appid, str(token), int(expires_in))

        return str(token)
