from __future__ import annotations

from .github import GitHubTrendingCollector
from .hn import HNFrontPageCollector
from .huggingface import HFTrendingCollector
from .rss import RSSCollector
from .web_news import WebNewsIndexCollector
from .zhihu import ZhihuHotListCollector
from .weibo import WeiboHotSearchCollector
from .base import BaseCollector
from .registry import CompositeCollector, BoundFactory, BoundGitHubTrendingCollector, BoundHNCollector, BoundHFTrendingCollector, BoundWebNewsCollector, BoundRSSCollector, BoundZhihuCollector, BoundWeiboCollector
from .keywords import filter_by_keywords

__all__ = [
    "GitHubTrendingCollector",
    "HNFrontPageCollector",
    "HFTrendingCollector",
    "RSSCollector",
    "WebNewsIndexCollector",
    "ZhihuHotListCollector",
    "WeiboHotSearchCollector",
    "BaseCollector",
    "CompositeCollector",
    "filter_by_keywords",
]