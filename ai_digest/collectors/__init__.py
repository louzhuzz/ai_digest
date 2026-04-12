from .github import GitHubTrendingCollector
from .hn import HNFrontPageCollector
from .huggingface import HFTrendingCollector
from .rss import RSSCollector
from .web_news import WebNewsIndexCollector

__all__ = [
    "GitHubTrendingCollector",
    "HNFrontPageCollector",
    "HFTrendingCollector",
    "RSSCollector",
    "WebNewsIndexCollector",
]
