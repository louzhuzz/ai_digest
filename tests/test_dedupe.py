from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.models import DigestItem


class FakeStateStore:
    def __init__(self, recent_keys: dict[str, datetime] | None = None) -> None:
        self.recent_keys = recent_keys or {}
        self.loaded_days: int | None = None
        self.loaded_now: datetime | None = None
        self.upserted_items: list[dict[str, object]] = []

    def load_recent_dedupe_keys(self, days: int, now: datetime) -> dict[str, datetime]:
        self.loaded_days = days
        self.loaded_now = now
        return dict(self.recent_keys)

    def upsert_items(self, items: list[dict[str, object]]) -> None:
        self.upserted_items.extend(items)


class RecentDedupeFilterTest(unittest.TestCase):
    def test_filters_same_dedupe_key_within_seven_days(self) -> None:
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        items = [
            DigestItem(
                title="OpenAI releases new model",
                url="https://example.com/openai-new-model",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-model",
            ),
            DigestItem(
                title="OpenAI releases new model again",
                url="https://mirror.example.com/openai-new-model",
                source="Mirror",
                published_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-model",
            ),
        ]

        deduper = RecentDedupeFilter(window_days=7)
        filtered = deduper.filter(items, now=now)

        self.assertEqual([item.title for item in filtered], ["OpenAI releases new model"])

    def test_filters_items_already_seen_in_state_store(self) -> None:
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        state_store = FakeStateStore(recent_keys={"openai:new-model": datetime(2026, 4, 6, tzinfo=timezone.utc)})
        items = [
            DigestItem(
                title="OpenAI releases new model",
                url="https://example.com/openai-new-model",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-model",
            ),
            DigestItem(
                title="New item",
                url="https://example.com/new",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-item",
            ),
        ]

        deduper = RecentDedupeFilter(window_days=7, state_store=state_store)
        filtered = deduper.filter(items, now=now)

        self.assertEqual([item.title for item in filtered], ["New item"])
        self.assertEqual(state_store.loaded_days, 7)
        self.assertEqual(state_store.loaded_now, now)

    def test_allows_items_seen_earlier_on_same_day(self) -> None:
        now = datetime(2026, 4, 10, 12, tzinfo=timezone.utc)
        state_store = FakeStateStore(recent_keys={"openai:new-model": datetime(2026, 4, 10, 8, tzinfo=timezone.utc)})
        items = [
            DigestItem(
                title="OpenAI releases new model",
                url="https://example.com/openai-new-model",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-model",
            ),
        ]

        deduper = RecentDedupeFilter(window_days=7, state_store=state_store)
        filtered = deduper.filter(items, now=now)

        self.assertEqual([item.title for item in filtered], ["OpenAI releases new model"])

    def test_persist_writes_accepted_items_to_state_store(self) -> None:
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        state_store = FakeStateStore()
        items = [
            DigestItem(
                title="OpenAI releases new model",
                url="https://example.com/openai-new-model",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-model",
            ),
            DigestItem(
                title="New item",
                url="https://example.com/new",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                dedupe_key="openai:new-item",
            ),
        ]

        deduper = RecentDedupeFilter(window_days=7, state_store=state_store)

        deduper.persist(items, now=now)

        self.assertEqual(len(state_store.upserted_items), 2)
        self.assertEqual(state_store.upserted_items[0]["dedupe_key"], "openai:new-model")
        self.assertEqual(state_store.upserted_items[0]["seen_at"], now)
        self.assertEqual(state_store.upserted_items[1]["dedupe_key"], "openai:new-item")


if __name__ == "__main__":
    unittest.main()
