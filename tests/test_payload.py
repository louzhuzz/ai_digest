from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from ai_digest.event_clusterer import EventClusterer
from ai_digest.models import DigestItem
from ai_digest.summarizer import DigestPayloadBuilder
from ai_digest.section_picker import BriefingSelection


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

    def test_build_article_input_requires_briefing_selection(self) -> None:
        item = DigestItem(
            title="AI update",
            url="https://example.com/update",
            source="OpenAI Blog",
            published_at=datetime(2026, 4, 10, 12, 30, tzinfo=timezone.utc),
            category="news",
            summary="New capability",
            why_it_matters="Useful for developers",
            score=0.9,
            dedupe_key="news:update:a",
        )

        with self.assertRaisesRegex(ValueError, "briefing_selection is required for article input"):
            DigestPayloadBuilder().build_article_input([item], date="2026-04-10")

    def test_build_article_input_uses_briefing_selection_and_serializes_items(self) -> None:
        news_item_a = DigestItem(
            title="OpenAI launches new model",
            url="https://example.com/update",
            source="Hacker News AI",
            published_at=datetime(2026, 4, 10, 12, 30, tzinfo=timezone.utc),
            category="news",
            summary="New capability",
            why_it_matters="Useful for developers",
            metadata={"avatar_url": "https://img.example.com/openai.png"},
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
        selection = BriefingSelection(
            lead_items=[news_item_a, project_item],
            secondary_items=[news_item_b],
            briefing_angle="今天的主线偏产品更新与工程落地",
        )

        payload = DigestPayloadBuilder().build_article_input(
            [news_item_a, news_item_b, project_item],
            date="2026-04-10",
            briefing_selection=selection,
        )

        self.assertEqual(payload["signal_pool_size"], 3)
        self.assertEqual(payload["briefing_angle"], "今天的主线偏产品更新与工程落地")
        self.assertEqual(payload["lead_items"][0]["title"], "OpenAI launches new model")
        self.assertEqual(payload["lead_items"][0]["avatar_url"], "https://img.example.com/openai.png")
        self.assertEqual(
            payload["lead_items"][0]["published_at"],
            "2026-04-10T12:30:00+00:00",
        )
        self.assertEqual(
            payload["lead_items"][1]["published_at"],
            "2026-04-10T11:00:00+00:00",
        )
        self.assertEqual(
            payload["secondary_items"][0]["published_at"],
            "2026-04-10T12:00:00+00:00",
        )
        self.assertNotIn("top_event_clusters", payload)
        self.assertNotIn("top_project_clusters", payload)
        json.dumps(payload)

    def test_build_article_input_respects_summary_boundary_at_220_and_221_chars(self) -> None:
        item_220 = DigestItem(
            title="Exact boundary",
            url="https://example.com/exact",
            source="OpenAI Blog",
            published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
            category="news",
            summary="x" * 220,
            why_it_matters="Useful for developers",
            score=0.86,
            dedupe_key="news:exact-summary",
        )
        item_221 = DigestItem(
            title="Over boundary",
            url="https://example.com/over",
            source="OpenAI Blog",
            published_at=datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc),
            category="news",
            summary="x" * 221,
            why_it_matters="Useful for developers",
            score=0.85,
            dedupe_key="news:over-summary",
        )

        payload_220 = DigestPayloadBuilder().build_article_input(
            [item_220],
            date="2026-04-10",
            briefing_selection=BriefingSelection(
                lead_items=[item_220],
                secondary_items=[],
                briefing_angle="简报主线",
            ),
        )
        payload_221 = DigestPayloadBuilder().build_article_input(
            [item_221],
            date="2026-04-10",
            briefing_selection=BriefingSelection(
                lead_items=[item_221],
                secondary_items=[],
                briefing_angle="简报主线",
            ),
        )

        self.assertEqual(len(payload_220["lead_items"][0]["summary"]), 220)
        self.assertNotIn("...", payload_220["lead_items"][0]["summary"])
        self.assertEqual(len(payload_221["lead_items"][0]["summary"]), 220)
        self.assertTrue(payload_221["lead_items"][0]["summary"].endswith("..."))


if __name__ == "__main__":
    unittest.main()
