from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .models import DigestItem


class RecentDedupeFilter:
    def __init__(self, window_days: int = 7, state_store: Any | None = None) -> None:
        self.window = timedelta(days=window_days)
        self.state_store = state_store

    def _recent_keys(self, now: datetime) -> dict[str, datetime]:
        if self.state_store is None:
            return {}
        return self.state_store.load_recent_dedupe_keys(days=self.window.days, now=now)

    def filter(self, items: Iterable[DigestItem], now: datetime | None = None) -> list[DigestItem]:
        current_time = now or datetime.now(timezone.utc)
        seen_in_run: set[str] = set()
        recent_keys = self._recent_keys(current_time)
        filtered: list[DigestItem] = []

        for item in items:
            key = item.dedupe_key or item.url
            if key in seen_in_run:
                continue

            last_seen = recent_keys.get(key)
            if last_seen is not None and last_seen.date() != current_time.date() and current_time - last_seen <= self.window:
                continue

            seen_in_run.add(key)
            filtered.append(replace(item, dedupe_key=key))

        return filtered

    def persist(self, items: Iterable[DigestItem], now: datetime | None = None) -> None:
        if self.state_store is None:
            return

        current_time = now or datetime.now(timezone.utc)
        self.state_store.upsert_items(
            [
                {
                    "dedupe_key": item.dedupe_key or item.url,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at,
                    "seen_at": current_time,
                }
                for item in items
            ]
        )
