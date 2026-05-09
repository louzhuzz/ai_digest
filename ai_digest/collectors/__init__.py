from __future__ import annotations

from .github import GitHubTrendingCollector
from .hn import HNFrontPageCollector
from .huggingface import HFTrendingCollector
from .rss import RSSCollector
from .web_news import WebNewsIndexCollector
from .base import BaseCollector
from .registry import CompositeCollector, BoundFactory, BoundGitHubTrendingCollector, BoundHNCollector, BoundHFTrendingCollector, BoundWebNewsCollector, BoundRSSCollector
from .keywords import filter_by_keywords

__all__ = [
    "GitHubTrendingCollector",
    "HNFrontPageCollector",
    "HFTrendingCollector",
    "RSSCollector",
    "WebNewsIndexCollector",
    "BaseCollector",
    "CompositeCollector",
    "BoundFactory",
    "BoundGitHubTrendingCollector",
    "BoundHNCollector",
    "BoundHFTrendingCollector",
    "BoundWebNewsCollector",
    "BoundRSSCollector",
    "filter_by_keywords",
]
