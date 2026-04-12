from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.models import DigestItem
from ai_digest.ranking import ItemRanker


class ItemRankerTest(unittest.TestCase):
    def test_ranks_recent_popular_github_item_above_old_item(self) -> None:
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        items = [
            DigestItem(
                title="Old repo",
                url="https://github.com/example/old",
                source="GitHub",
                published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
                category="github",
                metadata={"stars": 30, "stars_growth": 1, "author_reputation": 0.2},
            ),
            DigestItem(
                title="Hot repo",
                url="https://github.com/example/hot",
                source="GitHub",
                published_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
                category="github",
                metadata={"stars": 420, "stars_growth": 60, "author_reputation": 0.9},
            ),
        ]

        ranked = ItemRanker().rank(items, now=now)

        self.assertEqual([item.title for item in ranked], ["Hot repo", "Old repo"])
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_ranks_hot_community_signal_above_plain_recent_item(self) -> None:
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        hot_item = DigestItem(
            title="Hot AI launch",
            url="https://example.com/hot",
            source="Hacker News AI",
            published_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
            category="news",
            metadata={"source_strength": 0.8, "community_heat": 200, "developer_relevance": 0.9},
        )
        plain_item = DigestItem(
            title="Minor update",
            url="https://example.com/plain",
            source="OpenAI News",
            published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            category="news",
            metadata={"source_strength": 0.2, "community_heat": 0, "developer_relevance": 0.3},
        )

        ranked = ItemRanker().rank([plain_item, hot_item], now=now)

        self.assertEqual(ranked[0].title, hot_item.title)


if __name__ == "__main__":
    unittest.main()
