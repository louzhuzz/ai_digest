from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from ai_digest.event_clusterer import EventClusterer
from ai_digest.models import DigestItem
from ai_digest.summarizer import DigestPayloadBuilder


class DigestPayloadBuilderTest(unittest.TestCase):
    def test_builds_structure_with_date_and_items(self) -> None:
        item = DigestItem(
            title="AI update",
            url="https://example.com/update",
            source="OpenAI Blog",
            published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            category="news",
            summary="New capability",
            why_it_matters="Useful for developers",
            score=0.8,
            dedupe_key="news:update",
        )

        payload = DigestPayloadBuilder().build([item], date="2026-04-10")

        self.assertEqual(payload["date"], "2026-04-10")
        self.assertEqual(payload["items"][0]["title"], "AI update")
        self.assertEqual(payload["items"][0]["dedupe_key"], "news:update")
        self.assertEqual(payload["items"][0]["published_at"], "2026-04-10T00:00:00+00:00")
        json.dumps(payload)

    def test_build_uses_metadata_description_when_summary_missing(self) -> None:
        item = DigestItem(
            title="AI update",
            url="https://example.com/update",
            source="OpenAI Blog",
            published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            category="news",
            summary="",
            metadata={"description": "Description from metadata"},
            dedupe_key="news:update",
        )

        payload = DigestPayloadBuilder().build([item], date="2026-04-10")

        self.assertEqual(payload["items"][0]["summary"], "Description from metadata")

    def test_build_article_input_groups_clusters_and_serializes_nested_datetime_fields(self) -> None:
        news_item_a = DigestItem(
            title="OpenAI launches new model",
            url="https://example.com/update",
            source="Hacker News AI",
            published_at=datetime(2026, 4, 10, 12, 30, tzinfo=timezone.utc),
            category="news",
            summary="New capability",
            why_it_matters="Useful for developers",
            score=0.9,
            dedupe_key="news:update:a",
        )
        news_item_b = DigestItem(
            title="OpenAI launches new model today",
            url="https://another.example.com/update",
            source="OpenAI News",
            published_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            category="news",
            summary="Second source",
            why_it_matters="Useful for developers",
            score=0.83,
            dedupe_key="news:update:b",
        )
        project_item = DigestItem(
            title="Agent framework",
            url="https://github.com/example/agent",
            source="GitHub Trending",
            published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
            category="github",
            summary="Agent tooling",
            why_it_matters="Useful for developers",
            score=0.85,
            dedupe_key="github:example/agent",
        )

        payload = DigestPayloadBuilder().build_article_input(
            [news_item_a, news_item_b, project_item],
            date="2026-04-10",
        )

        self.assertEqual(payload["signal_pool_size"], 3)
        self.assertNotIn("news_signals", payload)
        self.assertNotIn("project_signals", payload)
        self.assertEqual(payload["top_event_clusters"][0]["canonical_title"], "OpenAI launches new model")
        self.assertEqual(
            payload["top_event_clusters"][0]["items"][0]["published_at"],
            "2026-04-10T12:30:00+00:00",
        )
        self.assertEqual(
            payload["top_project_clusters"][0]["items"][0]["published_at"],
            "2026-04-10T11:00:00+00:00",
        )
        self.assertEqual(
            payload["top_event_clusters"][0]["sources"],
            ["Hacker News AI", "OpenAI News"],
        )

    def test_build_article_input_accepts_precomputed_clusters(self) -> None:
        item = DigestItem(
            title="Archon",
            url="https://github.com/example/archon",
            source="GitHub Trending",
            published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
            category="github",
            summary="Agent tooling",
            why_it_matters="Useful for developers",
            score=0.85,
            dedupe_key="github:example/archon",
        )
        clusters = EventClusterer().cluster([item])

        payload = DigestPayloadBuilder().build_article_input(
            [item],
            date="2026-04-10",
            clusters=clusters,
        )

        self.assertEqual(len(payload["top_project_clusters"]), 1)
        self.assertEqual(payload["top_project_clusters"][0]["canonical_url"], "https://github.com/example/archon")

    def test_serialize_cluster_includes_topic_tag(self) -> None:
        from ai_digest.summarizer import DigestPayloadBuilder
        from ai_digest.models import DigestItem, EventCluster
        from datetime import datetime, timezone
        item = DigestItem(
            title="Test", url="https://x.com", source="X",
            published_at=datetime(2026, 4, 14, tzinfo=timezone.utc),
            category="news", score=0.5, dedupe_key="x"
        )
        cluster = EventCluster(
            canonical_title="Test", canonical_url="https://x.com",
            sources=["X"], items=[item], score=0.5, category="event",
            topic_tag="模型发布"
        )
        builder = DigestPayloadBuilder()
        serialized = builder._serialize_cluster(cluster)
        self.assertEqual(serialized["topic_tag"], "模型发布")


if __name__ == "__main__":
    unittest.main()
