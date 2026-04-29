from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .auth import WeChatAccessTokenClient
from .collectors.github import GitHubTrendingCollector
from .collectors.hn import HNFrontPageCollector
from .collectors.huggingface import HFTrendingCollector
from .collectors.web_news import WebNewsIndexCollector
from .collectors.rss import RSSCollector
from .publishers.wechat import WeChatDraftPublisher
from .settings import AppSettings
from .wechat_image_uploader import WeChatImageUploader


@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    kind: str
    category: str
    allowed_path_prefixes: tuple[str, ...] = ()


class BoundCollector:
    def collect(self) -> list:
        raise NotImplementedError


class BoundGitHubTrendingCollector(BoundCollector):
    def __init__(self, collector: GitHubTrendingCollector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundHNCollector(BoundCollector):
    def __init__(self, collector: HNFrontPageCollector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundHFTrendingCollector(BoundCollector):
    def __init__(self, collector: HFTrendingCollector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundWebNewsCollector(BoundCollector):
    def __init__(self, collector: WebNewsIndexCollector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundRSSCollector(BoundCollector):
    def __init__(self, collector: RSSCollector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class CompositeCollector:
    def __init__(self, collectors: Iterable[BoundCollector]) -> None:
        self.collectors = list(collectors)
        self.errors: list[str] = []

    def collect(self) -> list:
        items = []
        self.errors = []
        for collector in self.collectors:
            try:
                items.extend(collector.collect())
            except Exception as exc:
                self.errors.append(str(exc))
        return items


def build_default_source_specs() -> list[SourceSpec]:
    return [
        SourceSpec(name="GitHub Trending", url="https://github.com/trending", kind="github_trending", category="github"),
        SourceSpec(name="Hacker News AI", url="https://news.ycombinator.com/", kind="hn_frontpage", category="news"),
        SourceSpec(name="Hugging Face Trending", url="https://huggingface.co/models?sort=trending", kind="hf_trending", category="project"),
        SourceSpec(name="OpenAI News", url="https://openai.com/news", kind="web_news_index", category="news", allowed_path_prefixes=("/index/", "/news/")),
        SourceSpec(name="Anthropic News", url="https://www.anthropic.com/news", kind="web_news_index", category="news", allowed_path_prefixes=("/news/",)),
        SourceSpec(name="Google AI / Gemini", url="https://blog.google/innovation-and-ai/technology/ai/", kind="web_news_index", category="news", allowed_path_prefixes=("/innovation-and-ai/technology/ai/", "/technology/ai/", "/products/gemini/")),
        SourceSpec(name="机器之心", url="https://www.jiqizhixin.com/", kind="web_news_index", category="news", allowed_path_prefixes=("/pro/", "/ai_shortlist", "/aihaohaoyong", "/reference/")),
        SourceSpec(name="新智元", url="https://www.aiera.com.cn/", kind="web_news_index", category="news", allowed_path_prefixes=("/article/", "/news/", "/post/")),
        SourceSpec(name="量子位", url="https://www.qbitai.com/", kind="web_news_index", category="news", allowed_path_prefixes=("/article/", "/post/", "/news/", "/202")),
        SourceSpec(name="CSDN AI", url="https://aillm.csdn.net/", kind="web_news_index", category="news", allowed_path_prefixes=("/article/details/", "/p/", "/news/", "/article/")),
        SourceSpec(name="大黑AI速报", url="https://news.daheyai.com/rss.php", kind="rss", category="news"),
    ]


def build_default_collector() -> CompositeCollector:
    sources = build_default_source_specs()
    collectors: list[BoundCollector] = []
    for source in sources:
        if source.kind == "github_trending":
            collectors.append(BoundGitHubTrendingCollector(GitHubTrendingCollector(), source.url))
        elif source.kind == "hn_frontpage":
            collectors.append(BoundHNCollector(HNFrontPageCollector(), source.url))
        elif source.kind == "hf_trending":
            collectors.append(BoundHFTrendingCollector(HFTrendingCollector(), source.url))
        elif source.kind == "web_news_index":
            collectors.append(BoundWebNewsCollector(WebNewsIndexCollector(source.name, allowed_path_prefixes=source.allowed_path_prefixes), source.url))
        elif source.kind == "rss":
            collectors.append(BoundRSSCollector(RSSCollector(source.name), source.url))
    return CompositeCollector(collectors)


def build_default_publisher(settings: AppSettings | None = None) -> WeChatDraftPublisher:
    if settings and settings.wechat:
        if settings.dry_run:
            return WeChatDraftPublisher(cover_media_id=settings.wechat.thumb_media_id, dry_run=True)
        token_client = WeChatAccessTokenClient(appid=settings.wechat.appid, appsecret=settings.wechat.appsecret)
        access_token = token_client.get_access_token()
        image_uploader = WeChatImageUploader(access_token=access_token) if access_token else None
        return WeChatDraftPublisher(access_token=access_token, cover_media_id=settings.wechat.thumb_media_id, dry_run=settings.dry_run, image_uploader=image_uploader)
    return WeChatDraftPublisher(dry_run=True)
