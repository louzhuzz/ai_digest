from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

from ..http_client import open_url
from ..models import DigestItem

LINK_PATTERN = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
AI_TERMS = (
    "ai",
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "deepseek",
    "qwen",
    "minimax",
    "model",
    "agent",
)
PUBLIC_PLATFORM_SOURCES = {
    "机器之心",
    "新智元",
    "量子位",
    "CSDN AI",
}
PUBLIC_AI_TITLE_TERMS = (
    "ai",
    "大模型",
    "模型",
    "智能体",
    "agent",
    "claude",
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "qwen",
    "minimax",
    "llm",
    "rag",
    "多模态",
    "推理",
    "编程",
    "代码",
    "开源",
)
PUBLIC_COLUMN_TITLES = {
    "ai shortlist",
}
NAV_TITLES = {
    "skip to main content",
    "research",
    "business",
    "developers",
    "company",
    "foundation (opens in a new window)",
    "product",
    "safety",
    "engineering",
    "security",
    "global affairs",
    "ai adoption",
    "all",
    "research index",
    "research overview",
    "research residency",
    "openai for science",
    "economic research",
}


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _is_ai_news(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in AI_TERMS)


def _is_public_ai_hot_news(title: str) -> bool:
    lowered = title.lower()
    if lowered in PUBLIC_COLUMN_TITLES:
        return False
    return any(term in lowered for term in PUBLIC_AI_TITLE_TERMS)


class WebNewsIndexCollector:
    def __init__(
        self,
        source_name: str,
        category: str = "news",
        *,
        allowed_path_prefixes: tuple[str, ...] = (),
        http_client: object | None = None,
    ) -> None:
        self.source_name = source_name
        self.category = category
        self.allowed_path_prefixes = allowed_path_prefixes
        self.http_client = http_client

    def collect(self, page_url: str) -> list[DigestItem]:
        with open_url(page_url, http_client=self.http_client) as response:
            html = response.read().decode("utf-8", errors="replace")
        return self.parse_index(html, base_url=page_url)

    def parse_index(self, html: str, base_url: str) -> list[DigestItem]:
        published_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        items: list[DigestItem] = []
        seen: set[str] = set()
        for href, title_html in LINK_PATTERN.findall(html):
            title = _strip_tags(title_html)
            if not title:
                continue
            absolute_url = urljoin(base_url, href)
            if self._is_navigation_link(title, absolute_url, base_url):
                continue
            if not self._is_candidate_news(title, absolute_url):
                continue
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            items.append(
                DigestItem(
                    title=title,
                    url=absolute_url,
                    source=self.source_name,
                    published_at=published_at,
                    category=self.category,
                    summary="",
                    dedupe_key=absolute_url,
                    metadata={
                        "source_strength": 0.9,
                        "developer_relevance": 0.75,
                        "page_url": base_url,
                    },
                )
            )
        return items

    def _is_candidate_news(self, title: str, absolute_url: str) -> bool:
        if self.source_name in PUBLIC_PLATFORM_SOURCES:
            return _is_public_ai_hot_news(title)
        return _is_ai_news(f"{title} {absolute_url}")

    def _is_navigation_link(self, title: str, absolute_url: str, base_url: str) -> bool:
        lowered_title = title.lower()
        if lowered_title in NAV_TITLES:
            return True
        parsed = urlparse(absolute_url)
        base_parsed = urlparse(base_url)
        if parsed.fragment:
            return True
        if absolute_url.rstrip("/") == base_url.rstrip("/"):
            return True
        if self.allowed_path_prefixes:
            if not any(parsed.path.startswith(prefix) for prefix in self.allowed_path_prefixes):
                return True
        if parsed.netloc == base_parsed.netloc:
            base_path = base_parsed.path.rstrip("/")
            path = parsed.path.rstrip("/")
            if base_path and not (
                path.startswith(f"{base_path}/")
                or path.startswith("/index/")
            ):
                return True
        return False
