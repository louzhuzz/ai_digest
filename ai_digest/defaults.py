# -*- coding: utf-8 -*-
"""
默认组件构建器。

所有 collector 通过 registry.py 的 COLLECTOR_REGISTRY 注册。
新增数据源：只需在 registry.py 添加条目 + 在 collect_args 补充 URL 参数。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .auth import WeChatAccessTokenClient
from .collectors.github import GitHubTrendingCollector
from .collectors.hn import HNFrontPageCollector
from .collectors.huggingface import HFTrendingCollector
from .collectors.web_news import WebNewsIndexCollector
from .collectors.rss import RSSCollector
from .collectors.zhihu import ZhihuHotListCollector
from .collectors.weibo import WeiboHotSearchCollector
from .publishers.wechat import WeChatDraftPublisher
from .settings import AppSettings
from .wechat_image_uploader import WeChatImageUploader


# ── 数据源配置 ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    kind: str      # 必须在 COLLECTOR_REGISTRY 中存在
    category: str
    allowed_path_prefixes: tuple[str, ...] = ()


# ── 已知 collector 的构造参数（URL 参数从 SourceSpec.url 注入） ────────

_COLLECTOR_CTOR_KWARGS: dict[str, dict] = {
    "github_trending": {},
    "hn_frontpage": {},
    "hf_trending": {},
    "web_news_index": {},  # allowed_path_prefixes 从 SourceSpec 注入
    "rss": {},
    "zhihu_hot": {},
    "weibo_hot": {},
}

# 仅 zhihu_hot / weibo_hot 不需要 URL 参数（collect() 无参数）
_NO_URL_KINDS = {"zhihu_hot", "weibo_hot"}


# ── 默认数据源清单 ──────────────────────────────────────────────────────

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
        SourceSpec(name="CSDN 博客订阅", url="https://rsshub.rssforever.com/csdn/blog/csdngeeknews", kind="rss", category="news"),
        SourceSpec(name="雷锋网", url="https://www.leiphone.com/feed", kind="rss", category="news"),
        SourceSpec(name="爱范儿", url="https://www.ifanr.com/feed", kind="rss", category="news"),
        SourceSpec(name="DeepMind Blog", url="https://rsshub.rssforever.com/deepmind/blog", kind="rss", category="news"),
        SourceSpec(name="DeepLearning AI 周报", url="https://rsshub.rssforever.com/deeplearning/thebatch", kind="rss", category="news"),
        SourceSpec(name="Solidot 科技", url="https://rsshub.rssforever.com/solidot/www", kind="rss", category="news"),
        SourceSpec(name="InfoQ 中文", url="https://rsshub.rssforever.com/infoq/recommend", kind="rss", category="news"),
        SourceSpec(name="iThome 台灣 AI", url="https://rsshub.rssforever.com/ithome/tw/feeds/ai", kind="rss", category="news"),
        SourceSpec(name="橘鸦 Juya RSS", url="https://imjuya.github.io/juya-ai-daily/rss.xml", kind="rss", category="news"),
    ]


# ── BoundCollector 工厂 ──────────────────────────────────────────────────

def _make_bound(spec: SourceSpec):
    """根据 SourceSpec 构造对应的 BoundCollector。"""
    kind = spec.kind

    if kind == "github_trending":
        collector = GitHubTrendingCollector()
        from .collectors import BoundGitHubTrendingCollector
        return BoundGitHubTrendingCollector(collector, spec.url)

    elif kind == "hn_frontpage":
        collector = HNFrontPageCollector()
        from .collectors import BoundHNCollector
        return BoundHNCollector(collector, spec.url)

    elif kind == "hf_trending":
        collector = HFTrendingCollector()
        from .collectors import BoundHFTrendingCollector
        return BoundHFTrendingCollector(collector, spec.url)

    elif kind == "web_news_index":
        collector = WebNewsIndexCollector(spec.name, allowed_path_prefixes=spec.allowed_path_prefixes)
        from .collectors import BoundWebNewsCollector
        return BoundWebNewsCollector(collector, spec.url)

    elif kind == "rss":
        collector = RSSCollector(spec.name)
        from .collectors import BoundRSSCollector
        return BoundRSSCollector(collector, spec.url)

    elif kind == "zhihu_hot":
        collector = ZhihuHotListCollector()
        from .collectors import BoundZhihuCollector
        return BoundZhihuCollector(collector)

    elif kind == "weibo_hot":
        collector = WeiboHotSearchCollector()
        from .collectors import BoundWeiboCollector
        return BoundWeiboCollector(collector)

    else:
        raise ValueError(f"Unknown collector kind: {kind}")


# ── 组件构建入口 ────────────────────────────────────────────────────────

def build_default_collector() -> "CompositeCollector":
    """构建 CompositeCollector，包含全部已注册数据源。"""
    from .collectors import CompositeCollector

    sources = build_default_source_specs()
    collectors = [_make_bound(spec) for spec in sources]
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