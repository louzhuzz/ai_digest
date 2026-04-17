from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape

from ..http_client import open_url
from ..models import DigestItem


ARTICLE_PATTERN = re.compile(r"<article\b[^>]*class=\"[^\"]*Box-row[^\"]*\"[^>]*>(.*?)</article>", re.S)
REPO_LINK_PATTERN = re.compile(r"<h2\b[^>]*>.*?<a\b[^>]*\shref=\"(/[^\"?#]+/[^\"?#]+)\"[^>]*>(.*?)</a>", re.S)
AVATAR_BASE = "https://avatars.githubusercontent.com/u/"
STARS_PATTERN = re.compile(r"([0-9][0-9,]*)\s+stars?\s+today", re.I)
DESCRIPTION_PATTERN = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
STAR_NOISE_PATTERN = re.compile(r"^Star\s+[^ ]+\s*/\s*[^ ]+\s+", re.I)
AI_INCLUDE_TERMS = (
    " ai ",
    " llm",
    "llm ",
    "agent",
    "rag",
    "transformer",
    "embedding",
    "inference",
    "prompt",
    "multimodal",
    "diffusion",
    "fine-tuning",
    "fine tuning",
    "model",
    "machine learning",
    "deep learning",
)
AI_EXCLUDE_TERMS = (
    "markdown",
    "file converter",
    "document converter",
    "dotfiles",
    "terminal",
    "shell",
    "pdf",
)


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _clean_description(text: str) -> str:
    return STAR_NOISE_PATTERN.sub("", text).strip()


def _is_repo_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    if len(parts) != 2:
        return False
    return all(parts)


def _is_ai_project(title: str, description: str) -> bool:
    text = f" {title.lower()} {description.lower()} "
    if any(term in text for term in AI_INCLUDE_TERMS):
        return True
    if any(term in text for term in AI_EXCLUDE_TERMS):
        return False
    return False


class GitHubTrendingCollector:
    def __init__(self, category: str = "github", http_client: object | None = None) -> None:
        self.category = category
        self.http_client = http_client

    def collect(self, page_url: str = "https://github.com/trending") -> list[DigestItem]:
        with open_url(page_url, http_client=self.http_client) as response:
            html = response.read().decode("utf-8", errors="replace")
        return self.parse_trending(html, page_url=page_url)

    def parse_trending(self, html: str, page_url: str) -> list[DigestItem]:
        items: list[DigestItem] = []
        published_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        for article in ARTICLE_PATTERN.findall(html):
            link_match = REPO_LINK_PATTERN.search(article)
            if not link_match:
                continue
            href, title_html = link_match.groups()
            if not _is_repo_path(href):
                continue
            title = _strip_tags(title_html)
            description_match = DESCRIPTION_PATTERN.search(article)
            description = _clean_description(_strip_tags(description_match.group(1))) if description_match else ""
            if not _is_ai_project(title, description):
                continue
            stars_match = STARS_PATTERN.search(article)
            stars_growth = int(stars_match.group(1).replace(",", "")) if stars_match else 0
            owner_repo = href.strip("/")
            owner = owner_repo.split("/")[0]
            avatar_url = f"{AVATAR_BASE}{owner}?s=40&v=4"
            items.append(
                DigestItem(
                    title=title,
                    url=f"https://github.com/{owner_repo}",
                    source="GitHub Trending",
                    published_at=published_at,
                    category=self.category,
                    summary=description,
                    dedupe_key=f"github:{owner_repo}",
                    metadata={"stars_growth": stars_growth, "page_url": page_url, "avatar_url": avatar_url},
                )
            )
        return items
