# -*- coding: utf-8 -*-
"""
Collector 注册表 + 统一工厂。

用法：
    from collectors.base import BaseCollector, COLLECTOR_REGISTRY, BoundFactory

    cls, ctor_kwargs, bound_cls = COLLECTOR_REGISTRY["github_trending"]
    bound = BoundFactory.make_bound(bound_cls, cls(), source_spec)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Type

if TYPE_CHECKING:
    from .base import BaseCollector
    from .github import GitHubTrendingCollector
    from .hn import HNFrontPageCollector
    from .huggingface import HFTrendingCollector
    from .web_news import WebNewsIndexCollector
    from .rss import RSSCollector
    from .zhihu import ZhihuHotListCollector
    from .weibo import WeiboHotSearchCollector


@dataclass
class BoundCollectorSpec:
    """注册条目：如何构造 BoundCollector 以及如何调用 collect()。"""
    bound_cls: Type  # BoundGitHubTrendingCollector 等
    collector_cls: Type["BaseCollector"]
    ctor_kwargs: dict  # 传给 collector_cls.__init__ 的参数（不含 url）
    collect_arg: str  # "page_url" | "limit" | "feed_url"


# ── 注册表 ────────────────────────────────────────────────────────────────

COLLECTOR_REGISTRY: dict[str, BoundCollectorSpec] = {
    "github_trending": BoundCollectorSpec(
        bound_cls=None,  # filled below after class definitions
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="page_url",
    ),
}


# ── BoundCollector 基类（原有逻辑保留，供注册表使用） ──────────────────

class BoundCollector:
    def collect(self) -> list:
        raise NotImplementedError


class BoundGitHubTrendingCollector(BoundCollector):
    def __init__(self, collector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundHNCollector(BoundCollector):
    def __init__(self, collector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundHFTrendingCollector(BoundCollector):
    def __init__(self, collector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundWebNewsCollector(BoundCollector):
    def __init__(self, collector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundRSSCollector(BoundCollector):
    def __init__(self, collector, page_url: str) -> None:
        self.collector = collector
        self.page_url = page_url

    def collect(self) -> list:
        return self.collector.collect(self.page_url)


class BoundZhihuCollector(BoundCollector):
    def __init__(self, collector) -> None:
        self.collector = collector

    def collect(self) -> list:
        return self.collector.collect()


class BoundWeiboCollector(BoundCollector):
    def __init__(self, collector) -> None:
        self.collector = collector

    def collect(self) -> list:
        return self.collector.collect()


# ── 更新注册表（在类定义之后） ─────────────────────────────────────────

COLLECTOR_REGISTRY = {
    "github_trending": BoundCollectorSpec(
        bound_cls=BoundGitHubTrendingCollector,
        collector_cls=None,  # filled by import
        ctor_kwargs={},
        collect_arg="page_url",
    ),
    "hn_frontpage": BoundCollectorSpec(
        bound_cls=BoundHNCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="page_url",
    ),
    "hf_trending": BoundCollectorSpec(
        bound_cls=BoundHFTrendingCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="page_url",
    ),
    "web_news_index": BoundCollectorSpec(
        bound_cls=BoundWebNewsCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="page_url",
    ),
    "rss": BoundCollectorSpec(
        bound_cls=BoundRSSCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="feed_url",
    ),
    "zhihu_hot": BoundCollectorSpec(
        bound_cls=BoundZhihuCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="none",
    ),
    "weibo_hot": BoundCollectorSpec(
        bound_cls=BoundWeiboCollector,
        collector_cls=None,
        ctor_kwargs={},
        collect_arg="none",
    ),
}


class CompositeCollector:
    def __init__(self, collectors) -> None:
        self.collectors = list(collectors)
        self.errors = []

    def collect(self) -> list:
        items = []
        self.errors = []
        for collector in self.collectors:
            try:
                items.extend(collector.collect())
            except Exception as exc:
                self.errors.append(str(exc))
        return items


class BoundFactory:
    """
    统一工厂：根据 SourceSpec 构造对应的 BoundCollector。

    用法：
        bound = BoundFactory.make(spec, ZhihuHotListCollector, BoundZhihuCollector, {})
    """

    @staticmethod
    def make(
        spec,  # SourceSpec
        collector_cls: Type["BaseCollector"],
        bound_cls: Type,
        ctor_kwargs: dict,
    ) -> BoundCollector:
        arg_name = COLLECTOR_REGISTRY.get(spec.kind, BoundCollectorSpec(
            bound_cls=BoundCollector,
            collector_cls=None,
            ctor_kwargs={},
            collect_arg="page_url",
        )).collect_arg

        collector = collector_cls(**ctor_kwargs)

        if arg_name == "none":
            return bound_cls(collector)
        elif arg_name == "page_url":
            return bound_cls(collector, spec.url)
        elif arg_name == "feed_url":
            return bound_cls(collector, spec.url)
        elif arg_name == "limit":
            return bound_cls(collector)
        else:
            # 默认按 page_url 处理
            return bound_cls(collector, spec.url)