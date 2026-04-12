from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.event_clusterer import EventClusterer
from ai_digest.models import DigestItem


class EventClustererTest(unittest.TestCase):
    def test_keeps_best_canonical_after_cluster_grows(self) -> None:
        items = [
            DigestItem(
                title="OpenAI ships GPT 5 API today",
                url="https://source-b.example.com/openai-gpt5-api",
                source="News B",
                published_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
                category="news",
                score=0.91,
                dedupe_key="news:b",
            ),
            DigestItem(
                title="OpenAI ships GPT-5 API",
                url="https://source-a.example.com/openai-gpt5-api",
                source="News A",
                published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
                category="news",
                score=0.89,
                dedupe_key="news:a",
            ),
            DigestItem(
                title="OpenAI ships GPT 5 API overview",
                url="https://source-c.example.com/openai-gpt5-api",
                source="News C",
                published_at=datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc),
                category="news",
                score=0.95,
                dedupe_key="news:c",
            ),
        ]

        cluster = EventClusterer().cluster(items)[0]

        self.assertEqual(cluster.canonical_title, "OpenAI ships GPT 5 API overview")
        self.assertEqual(cluster.canonical_url, "https://source-c.example.com/openai-gpt5-api")

    def test_clusters_multi_source_event_items_and_boosts_cluster_score(self) -> None:
        items = [
            DigestItem(
                title="OpenAI ships GPT-5 API",
                url="https://news.example.com/openai-gpt5-api",
                source="News A",
                published_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
                category="news",
                summary="Launch coverage",
                score=0.90,
                dedupe_key="news:a",
            ),
            DigestItem(
                title="OpenAI ships GPT 5 API",
                url="https://another.example.com/openai-gpt-5-api",
                source="News B",
                published_at=datetime(2026, 4, 10, 12, 30, tzinfo=timezone.utc),
                category="news",
                summary="Same launch from another source",
                score=0.86,
                dedupe_key="news:b",
            ),
            DigestItem(
                title="Anthropic updates Claude tooling",
                url="https://example.com/claude-tooling",
                source="News C",
                published_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
                category="news",
                summary="Separate event",
                score=0.92,
                dedupe_key="news:c",
            ),
        ]

        clusters = EventClusterer().cluster(items)

        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].canonical_title, "OpenAI ships GPT-5 API")
        self.assertEqual(clusters[0].canonical_url, "https://news.example.com/openai-gpt5-api")
        self.assertEqual(clusters[0].sources, ["News A", "News B"])
        self.assertEqual(clusters[0].category, "event")
        self.assertEqual(len(clusters[0].items), 2)
        self.assertAlmostEqual(clusters[0].score, 0.95)
        self.assertGreater(clusters[0].score, clusters[1].score)

    def test_keeps_project_clusters_separate_from_event_clusters(self) -> None:
        items = [
            DigestItem(
                title="Archon",
                url="https://github.com/example/archon",
                source="GitHub Trending",
                published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
                category="github",
                score=0.88,
                dedupe_key="github:archon",
            ),
            DigestItem(
                title="Archon framework",
                url="https://github.com/example/archon?ref=weekly",
                source="Weekly OSS",
                published_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
                category="project",
                score=0.82,
                dedupe_key="project:archon",
            ),
            DigestItem(
                title="OpenAI API update",
                url="https://example.com/openai-api",
                source="News A",
                published_at=datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc),
                category="news",
                score=0.80,
                dedupe_key="news:openai-api",
            ),
        ]

        clusters = EventClusterer().cluster(items)

        self.assertEqual([cluster.category for cluster in clusters], ["project", "event"])
        self.assertEqual(clusters[0].sources, ["GitHub Trending", "Weekly OSS"])
        self.assertEqual(len(clusters[0].items), 2)

    def test_does_not_cluster_different_companies_with_generic_api_titles(self) -> None:
        items = [
            DigestItem(
                title="OpenAI launches new API",
                url="https://example.com/openai-api",
                source="News A",
                published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
                category="news",
                score=0.90,
                dedupe_key="news:openai-api",
            ),
            DigestItem(
                title="Anthropic launches new API",
                url="https://example.com/anthropic-api",
                source="News B",
                published_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
                category="news",
                score=0.88,
                dedupe_key="news:anthropic-api",
            ),
        ]

        clusters = EventClusterer().cluster(items)

        self.assertEqual(len(clusters), 2)
        self.assertEqual({cluster.canonical_title for cluster in clusters}, {"OpenAI launches new API", "Anthropic launches new API"})


if __name__ == "__main__":
    unittest.main()
