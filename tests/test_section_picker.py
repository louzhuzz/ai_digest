from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.models import DigestItem
from ai_digest.section_picker import BriefingSelection, SectionPicker


def _item(title: str, category: str, score: float, dedupe_key: str, source: str = "Test Source") -> DigestItem:
    return DigestItem(
        title=title,
        url=f"https://example.com/{dedupe_key}",
        source=source,
        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        category=category,
        score=score,
        dedupe_key=dedupe_key,
    )


class SectionPickerTest(unittest.TestCase):
    def test_pick_briefing_allows_secondary_items_to_degrade_when_candidates_are_insufficient(self) -> None:
        picker = SectionPicker()
        briefing = picker.pick_briefing(
            [
                _item("News One", "news", 0.99, "news:one", source="News A"),
            ]
        )

        self.assertEqual(1, len(briefing.lead_items))
        self.assertEqual(0, len(briefing.secondary_items))

    def test_pick_briefing_prefers_news_or_tool_for_lead_items(self) -> None:
        picker = SectionPicker()
        briefing = picker.pick_briefing(
            [
                _item("News One", "news", 0.99, "news:one", source="News A"),
                _item("GitHub One", "github", 0.98, "github:one", source="GitHub A"),
                _item("Tool One", "tool", 0.97, "tool:one", source="Tool A"),
                _item("Project One", "project", 0.96, "project:one", source="Project A"),
                _item("News Two", "news", 0.95, "news:two", source="News B"),
                _item("GitHub Two", "github", 0.94, "github:two", source="GitHub B"),
            ]
        )

        self.assertIsInstance(briefing, BriefingSelection)
        self.assertEqual(2, len(briefing.lead_items))
        self.assertGreaterEqual(len(briefing.secondary_items), 2)
        self.assertLessEqual(len(briefing.secondary_items), 3)
        self.assertIn(briefing.lead_items[0].category, {"news", "tool"})
        self.assertTrue({item.dedupe_key for item in briefing.lead_items}.isdisjoint(
            {item.dedupe_key for item in briefing.secondary_items}
        ))

    def test_section_picker_treats_project_as_project_class_content_in_pick_path(self) -> None:
        picker = SectionPicker()
        sections = picker.pick(
            [
                _item("Project One", "project", 0.99, "project:one", source="Project A"),
                _item("News One", "news", 0.98, "news:one", source="News A"),
                _item("Tool One", "tool", 0.97, "tool:one", source="Tool A"),
                _item("Project Two", "project", 0.96, "project:two", source="Project B"),
            ]
        )

        self.assertTrue(any(item.category == "project" for item in sections.top_items + sections.github_items))

    def test_pick_briefing_infers_angle_from_selected_items(self) -> None:
        picker = SectionPicker()
        briefing = picker.pick_briefing(
            [
                _item("GitHub One", "github", 0.99, "github:one", source="GitHub A"),
                _item("Project One", "project", 0.98, "project:one", source="Project A"),
                _item("GitHub Two", "github", 0.97, "github:two", source="GitHub B"),
                _item("News One", "news", 0.96, "news:one", source="News A"),
                _item("Project Two", "project", 0.95, "project:two", source="Project B"),
                _item("Project Three", "project", 0.94, "project:three", source="Project C"),
            ]
        )

        self.assertEqual("今天的主线偏开源项目和工程落地", briefing.briefing_angle)

    def test_section_picker_mixes_news_and_github_in_top_items_when_both_exist(self) -> None:
        picker = SectionPicker()
        sections = picker.pick(
            [
                _item("Repo One", "github", 0.99, "github:one", source="GitHub A"),
                _item("Repo Two", "github", 0.98, "github:two", source="GitHub B"),
                _item("Repo Three", "github", 0.97, "github:three", source="GitHub C"),
                _item("News One", "news", 0.80, "news:one", source="News A"),
                _item("Tool One", "tool", 0.79, "tool:one", source="Tool A"),
            ]
        )

        categories = {item.category for item in sections.top_items}
        self.assertIn("github", categories)
        self.assertTrue("news" in categories or "tool" in categories)

    def test_section_picker_returns_disjoint_sections(self) -> None:
        picker = SectionPicker()
        sections = picker.pick(
            [
                _item("Repo One", "github", 0.98, "github:one", source="GitHub A"),
                _item("News One", "news", 0.95, "news:one", source="News A"),
                _item("Tool One", "tool", 0.94, "tool:one", source="Tool A"),
                _item("Repo Two", "github", 0.93, "github:two", source="GitHub B"),
                _item("News Two", "news", 0.92, "news:two", source="News B"),
                _item("Tool Two", "tool", 0.91, "tool:two", source="Tool B"),
            ]
        )

        focus_keys = {item.dedupe_key for item in sections.top_items}
        github_keys = {item.dedupe_key for item in sections.github_items}
        progress_keys = {item.dedupe_key for item in sections.progress_items}

        self.assertTrue(focus_keys)
        self.assertTrue(github_keys)
        self.assertTrue(progress_keys)
        self.assertTrue(focus_keys.isdisjoint(github_keys))
        self.assertTrue(focus_keys.isdisjoint(progress_keys))
        self.assertTrue(github_keys.isdisjoint(progress_keys))

    def test_section_picker_keeps_github_items_when_available(self) -> None:
        picker = SectionPicker()
        sections = picker.pick(
            [
                _item("Repo One", "github", 0.98, "github:one", source="GitHub A"),
                _item("Repo Two", "github", 0.97, "github:two", source="GitHub B"),
                _item("News One", "news", 0.96, "news:one", source="News A"),
                _item("Tool One", "tool", 0.95, "tool:one", source="Tool A"),
            ]
        )

        self.assertGreaterEqual(len(sections.github_items), 1)

    def test_section_picker_applies_source_quota_across_all_sections(self) -> None:
        picker = SectionPicker(per_source_limit=2)
        sections = picker.pick(
            [
                DigestItem(
                    title=f"QbitAI {idx}",
                    url=f"https://qbitai.com/{idx}",
                    source="量子位",
                    published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                    category="news",
                    score=1.0 - idx * 0.01,
                    dedupe_key=f"qbitai:{idx}",
                )
                for idx in range(4)
            ]
            + [
                _item("Repo One", "github", 0.9, "github:one"),
                _item("News One", "news", 0.8, "news:one"),
            ]
        )

        selected_sources = [item.source for item in sections.top_items + sections.github_items + sections.progress_items]
        self.assertLessEqual(selected_sources.count("量子位"), 2)


if __name__ == "__main__":
    unittest.main()
