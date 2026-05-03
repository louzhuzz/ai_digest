from __future__ import annotations
# -*- coding: utf-8 -*-

import json
import re
from datetime import datetime, timezone
from urllib import parse, request

from ..http_client import DEFAULT_TIMEOUT_SECONDS
from ..models import DigestItem

# ── 知乎热榜 API ──────────────────────────────────────────

_ZHIHU_HOT_API = "https://api.zhihu.com/topstory/hot-list"

_ZHIHU_MOBILE_UA = (
    "osee2unifiedRelease/4318 osee2unifiedReleaseVersion/7.7.0 "
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)


def _parse_hot_value(detail_text: str) -> int:
    """从 '4523万 热度' 或 '1234 热度' 中提取数值。"""
    nums = re.sub(r"[^\d]", "", detail_text.split()[0] if detail_text else "")
    if not nums:
        return 0
    value = int(nums)
    if "万" in detail_text:
        value *= 10_000
    elif "亿" in detail_text:
        value *= 100_000_000
    return value


class ZhihuHotListCollector:
    """知乎热榜数据收集器。"""

    def __init__(self, category: str = "trending", cookie: str | None = None) -> None:
        self.category = category
        self.cookie = cookie

    def collect(self, limit: int = 50) -> list[DigestItem]:
        params = parse.urlencode({"limit": limit, "reverse_order": 0})
        url = f"{_ZHIHU_HOT_API}?{params}"

        headers = {
            "User-Agent": _ZHIHU_MOBILE_UA,
            "Host": "api.zhihu.com",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        req = request.Request(url, headers=headers)
        try:
            with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Zhihu hot list request failed: {exc}") from exc

        return self._parse_response(payload)

    def _parse_response(self, payload: dict) -> list[DigestItem]:
        now = datetime.now(timezone.utc)
        items: list[DigestItem] = []

        for idx, entry in enumerate(payload.get("data", []), 1):
            target = entry.get("target", {})
            title = target.get("title", "")
            if not title:
                continue

            # 知乎 URL 格式转换：api.zhihu.com/questions → zhihu.com/question
            raw_url = target.get("url", "")
            url = raw_url.replace("api.zhihu.com/questions", "zhihu.com/question")
            if not url.startswith("http"):
                qid = target.get("question_id") or target.get("id", "")
                url = f"https://www.zhihu.com/question/{qid}" if qid else ""

            excerpt = target.get("excerpt", "")
            detail_text = entry.get("detail_text", "")
            hot_value = _parse_hot_value(detail_text)

            items.append(
                DigestItem(
                    title=title,
                    url=url,
                    source="知乎热榜",
                    published_at=now,
                    category=self.category,
                    summary=excerpt,
                    dedupe_key=f"zhihu:{target.get('question_id') or target.get('id', '')}",
                    metadata={
                        "rank": idx,
                        "hot_value": hot_value,
                        "detail_text": detail_text,
                        "answer_count": target.get("answer_count", 0),
                        "follower_count": target.get("follower_count", 0),
                    },
                )
            )
        return items
