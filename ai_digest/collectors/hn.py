from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from ..http_client import open_url
from ..models import DigestItem

TITLE_PATTERN = re.compile(r'<span\b[^>]*class="[^"]*titleline[^"]*"[^>]*>\s*<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SCORE_PATTERN = re.compile(r'<span\b[^>]*class="[^"]*score[^"]*"[^>]*>(\d+)\s+points?</span>', re.I | re.S)
AI_PATTERNS = (
    re.compile(r"\bopenai\b", re.I),
    re.compile(r"\banthropic\b", re.I),
    re.compile(r"\bclaude\b", re.I),
    re.compile(r"\bgemini\b", re.I),
    re.compile(r"\bdeepseek\b", re.I),
    re.compile(r"\bqwen\b", re.I),
    re.compile(r"\bminimax\b", re.I),
    re.compile(r"\bllm\b", re.I),
    re.compile(r"\bai\b", re.I),
    re.compile(r"\bagent(s)?\b", re.I),
    re.compile(r"\bmodel(s)?\b", re.I),
    re.compile(r"\binference\b", re.I),
    re.compile(r"\bmultimodal\b", re.I),
    re.compile(r"\brag\b", re.I),
)


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _is_ai_title(title: str) -> bool:
    return any(pattern.search(title) for pattern in AI_PATTERNS)


class HNFrontPageCollector:
    def __init__(self, source_name: str = "Hacker News AI", category: str = "news", http_client: object | None = None) -> None:
        self.source_name = source_name
        self.category = category
        self.http_client = http_client

    def collect(self, page_url: str = "https://news.ycombinator.com/") -> list[DigestItem]:
        with open_url(page_url, http_client=self.http_client) as response:
            html = response.read().decode("utf-8", errors="replace")
        return self.parse_frontpage(html, page_url=page_url)

    def parse_frontpage(self, html: str, page_url: str) -> list[DigestItem]:
        published_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        title_matches = list(TITLE_PATTERN.finditer(html))
        score_values = [int(value) for value in SCORE_PATTERN.findall(html)]
        items: list[DigestItem] = []

        for index, match in enumerate(title_matches):
            href, title_html = match.groups()
            title = _strip_tags(title_html)
            if not title or not _is_ai_title(title):
                continue
            score = score_values[index] if index < len(score_values) else 0
            url = urljoin(page_url, href)
            items.append(
                DigestItem(
                    title=title,
                    url=url,
                    source=self.source_name,
                    published_at=published_at,
                    category=self.category,
                    summary="",
                    dedupe_key=url,
                    metadata={
                        "community_heat": score,
                        "source_strength": 0.7,
                        "developer_relevance": 0.8,
                        "page_url": page_url,
                    },
                )
            )
        return items
