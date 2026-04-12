from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from ..http_client import open_url
from ..models import DigestItem

ARTICLE_PATTERN = re.compile(r"<article\b[^>]*>(.*?)</article>", re.I | re.S)
LINK_PATTERN = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
TEXT_BLOCK_PATTERN = re.compile(r"<div\b[^>]*>(.*?)</div>", re.I | re.S)
AI_TERMS = (
    "ai",
    "llm",
    "agent",
    "multimodal",
    "reasoning",
    "embedding",
    "transformer",
    "model",
    "diffusion",
    "vision",
    "audio",
)


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _is_ai_entry(title: str, description: str) -> bool:
    lowered = f" {title.lower()} {description.lower()} "
    return any(term in lowered for term in AI_TERMS)


def _clean_title(href: str, title: str) -> str:
    repo = href.strip("/")
    return repo or title


class HFTrendingCollector:
    def __init__(self, source_name: str = "Hugging Face Trending", category: str = "project", http_client: object | None = None) -> None:
        self.source_name = source_name
        self.category = category
        self.http_client = http_client

    def collect(self, page_url: str = "https://huggingface.co/models?sort=trending") -> list[DigestItem]:
        with open_url(page_url, http_client=self.http_client) as response:
            html = response.read().decode("utf-8", errors="replace")
        return self.parse_trending(html, page_url=page_url)

    def parse_trending(self, html: str, page_url: str) -> list[DigestItem]:
        published_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        items: list[DigestItem] = []
        for article in ARTICLE_PATTERN.findall(html):
            link_match = LINK_PATTERN.search(article)
            if not link_match:
                continue
            href, title_html = link_match.groups()
            raw_title = _strip_tags(title_html)
            text_match = TEXT_BLOCK_PATTERN.search(article)
            description = _strip_tags(text_match.group(1)) if text_match else ""
            title = _clean_title(href, raw_title)
            if not _is_ai_entry(title, description):
                continue
            url = urljoin(page_url, href)
            dedupe_key = f"hf:{href.strip('/')}" if href.startswith("/") else url
            items.append(
                DigestItem(
                    title=title,
                    url=url,
                    source=self.source_name,
                    published_at=published_at,
                    category=self.category,
                    summary=description,
                    dedupe_key=dedupe_key,
                    metadata={
                        "community_heat": 90,
                        "source_strength": 0.85,
                        "developer_relevance": 0.9,
                        "page_url": page_url,
                    },
                )
            )
        return items
