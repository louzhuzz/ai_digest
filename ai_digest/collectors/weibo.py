from __future__ import annotations
# -*- coding: utf-8 -*-

import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib import parse, request

from ..http_client import DEFAULT_TIMEOUT_SECONDS
from ..models import DigestItem

# ── 微博热搜 API ──────────────────────────────────────────

_WEIBO_HOT_API = "https://weibo.com/ajax/side/hotSearch"
_WEIBO_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)


class WeiboHotSearchCollector:
    """微博热搜数据收集器。"""

    def __init__(self, category: str = "trending", cookie: str | None = None) -> None:
        self.category = category
        self.cookie = cookie

    def collect(self, limit: int = 50) -> list[DigestItem]:
        headers = {
            "User-Agent": _WEIBO_MOBILE_UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://weibo.com/",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        req = request.Request(_WEIBO_HOT_API, headers=headers)
        try:
            with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Weibo hot search request failed: {exc}") from exc

        return self._parse_response(payload, limit)

    def _parse_response(self, payload: dict, limit: int) -> list[DigestItem]:
        now = datetime.now(timezone.utc)
        items: list[DigestItem] = []

        realtime = payload.get("data", {}).get("realtime", [])
        for idx, entry in enumerate(realtime[:limit], 1):
            word = entry.get("word", "")
            if not word:
                continue

            hot_num = entry.get("num", 0)
            raw_url = entry.get("url", "")
            url = raw_url if raw_url.startswith("http") else f"https://s.weibo.com/weibo?q={parse.quote(word)}"

            label_name = entry.get("label_name", "")
            icon_desc = entry.get("icon_desc", "")
            tag = label_name or icon_desc or ""

            items.append(
                DigestItem(
                    title=word,
                    url=url,
                    source="微博热搜",
                    published_at=now,
                    category=self.category,
                    summary=f"热搜 #{idx}  热度: {hot_num:,}",
                    dedupe_key=f"weibo:{word}",
                    metadata={
                        "rank": idx,
                        "hot_value": hot_num,
                        "tag": tag,
                        "category": entry.get("category", ""),
                    },
                )
            )
        return items
