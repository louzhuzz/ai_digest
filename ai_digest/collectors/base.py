# ai_digest/collectors/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import DigestItem


class BaseCollector(ABC):
    """
    所有数据源 collector 的统一协议。

    新增一个数据源只需：
    1. 继承 BaseCollector
    2. 实现 collect() 方法
    3. 在 defaults.py COLLECTOR_REGISTRY 注册
    """

    name: str      # 显示名，如 "GitHub Trending"
    kind: str      # 注册键名，如 "github_trending"
    category: str  # 分类，如 "github", "news", "trending"

    @abstractmethod
    def collect(self, *args, **kwargs) -> list["DigestItem"]:
        """抓取数据。子类签名自定义（page_url / limit / feed_url）。"""
        ...

    def get_metadata(self) -> dict:
        """可选：返回额外元数据供 ranking/section_picker 使用。"""
        return {}