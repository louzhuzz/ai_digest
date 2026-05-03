from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .models import DigestItem
from .simhash_utils import compute_text_simhash, Simhash


class RecentDedupeFilter:
    """
    双轨去重过滤器（精确匹配 + 近似匹配）。

    精确轨道：基于 dedupe_key（URL 或内容指纹）精确去重。
    近似轨道：基于 64-bit simhash 指纹（标题+摘要），hamming 距离 ≤ 3 判定为重复。

    两轨独立运行，近似轨道在精确轨道之后执行。
    """

    # Simhash bucket 参数：取高 N_BUCKETS 位作为 bucket key
    # bucket 范围覆盖 2^(64-N_BUCKETS) 的 hamming 距离
    N_BUCKETS = 58  # 每个 bucket 覆盖 ~64 的 hamming 距离范围
    MAX_HAMMING = 3  # hamming 距离 ≤ 3 判定为相似

    def __init__(self, window_days: int = 7, state_store: Any | None = None) -> None:
        self.window = timedelta(days=window_days)
        self.state_store = state_store
        # 近似去重时的缓存：{bucket_key: list[{content_hash, dedupe_key, title}]}
        self._simhash_cache: dict[int, list[dict]] = {}

    def _load_simhash_cache(self, now: datetime) -> None:
        """从 state_store 加载 simhash bucket 数据到内存。"""
        if self.state_store is None:
            self._simhash_cache = {}
            return
        self._simhash_cache = self.state_store.load_recent_simhash_buckets(
            days=self.window.days, now=now
        )

    def _recent_keys(self, now: datetime) -> dict[str, datetime]:
        if self.state_store is None:
            return {}
        return self.state_store.load_recent_dedupe_keys(days=self.window.days, now=now)

    def _is_similar(
        self,
        content_hash: int,
        dedupe_key: str,
        title: str,
    ) -> tuple[bool, str | None]:
        """
        检查 content_hash 是否与缓存中的某个指纹相似。

        Returns:
            (is_similar, matched_dedupe_key)
        """
        # 只在同一 bucket 内比较
        bucket_key = content_hash >> (64 - self.N_BUCKETS)
        candidates = self._simhash_cache.get(bucket_key, [])

        for candidate in candidates:
            # 先比较 content_hash 是否真的相似（hamming ≤ MAX_HAMMING）
            hamming = Simhash.distance(content_hash, candidate["content_hash"])
            if hamming <= self.MAX_HAMMING:
                return True, candidate["dedupe_key"]

        return False, None

    def filter(self, items: Iterable[DigestItem], now: datetime | None = None) -> list[DigestItem]:
        current_time = now or datetime.now(timezone.utc)

        # 加载精确去重数据
        recent_keys = self._recent_keys(current_time)

        # 加载 simhash bucket 数据
        self._load_simhash_cache(current_time)

        seen_in_run: set[str] = set()
        filtered: list[DigestItem] = []

        for item in items:
            key = item.dedupe_key or item.url

            # 轨道1：运行内精确去重
            if key in seen_in_run:
                continue

            # 轨道1：跨运行精确去重（same key within window）
            last_seen = recent_keys.get(key)
            if last_seen is not None and last_seen.date() != current_time.date() and current_time - last_seen <= self.window:
                continue

            # 轨道2：近似去重（simhash）
            content_hash = item.content_hash
            if content_hash != 0:
                is_similar, matched_key = self._is_similar(content_hash, key, item.title)
                if is_similar and matched_key and matched_key not in seen_in_run:
                    continue

            seen_in_run.add(key)
            filtered.append(replace(item, dedupe_key=key))

        return filtered

    def persist(self, items: Iterable[DigestItem], now: datetime | None = None) -> None:
        if self.state_store is None:
            return

        current_time = now or datetime.now(timezone.utc)

        # 写入精确去重表
        self.state_store.upsert_items(
            [
                {
                    "dedupe_key": item.dedupe_key or item.url,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at,
                    "seen_at": current_time,
                    "content_hash": item.content_hash,
                }
                for item in items
            ]
        )

        # 写入 simhash bucket 表
        self.state_store.upsert_simhash_buckets(
            [
                {
                    "dedupe_key": item.dedupe_key or item.url,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at,
                    "seen_at": current_time,
                    "content_hash": item.content_hash,
                }
                for item in items
                if item.content_hash != 0
            ]
        )