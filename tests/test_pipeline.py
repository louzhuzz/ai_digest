from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.models import DigestItem
from ai_digest.outline_generator import Outline, SectionSpec
from ai_digest.pipeline import DigestPipeline


class FakeCollector:
    def __init__(self, items: list[DigestItem]) -> None:
        self._items = items

    def collect(self) -> list[DigestItem]:
        return list(self._items)


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def publish(self, markdown: str) -> str:
        self.calls.append(markdown)
        return "draft-123"


class FakeWriter:
    def __init__(self, markdown: str = "# AI 每日新闻速递\n\n## 今日重点\n\nA\n\n## GitHub 新项目 / 热项目\n\nB\n\n## AI 技术进展\n\nC\n") -> None:
        self.markdown = markdown
        self.calls: list[dict[str, object]] = []

    def write(self, article_input: dict[str, object]) -> str:
        self.calls.append(article_input)
        return self.markdown


class TwoPhaseWriter(FakeWriter):
    def __init__(self, markdown: str = "# 两阶段标题\n\n1. 结论\n\n[链接A](https://example.com/a)\n[链接B](https://example.com/b)\n[链接C](https://example.com/c)\n") -> None:
        super().__init__(markdown=markdown)
        self.render_calls: list[tuple[Outline, dict[str, object]]] = []

    def render(self, outline: Outline, article_input: dict[str, object]) -> str:
        self.render_calls.append((outline, article_input))
        return self.markdown


class FakeOutlineGenerator:
    def __init__(self, outline: Outline | None) -> None:
        self.outline = outline
        self.calls: list[dict[str, object]] = []

    def generate(self, article_input: dict[str, object]) -> Outline | None:
        self.calls.append(article_input)
        return self.outline


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


class FailingPersistStateStore(FakeStateStore):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def upsert_items(self, items: list[dict[str, object]]) -> None:
        raise self.error


class RecordingLinter:
    def __init__(self, side_effect: Exception | None = None) -> None:
        self.side_effect = side_effect
        self.calls: list[str] = []

    def lint(self, markdown: str) -> None:
        self.calls.append(markdown)
        if self.side_effect is not None:
            raise self.side_effect


class ExplodingLinter:
    def __init__(self) -> None:
        self.calls = 0

    def lint(self, markdown: str) -> None:
        self.calls += 1
        raise AssertionError("lint should not be called in dry-run mode")


class NoOpLinter:
    def lint(self, markdown: str) -> None:
        pass


class DigestPipelineTest(unittest.TestCase):
    def test_publish_mode_uses_outline_generator_when_available(self) -> None:
        writer = TwoPhaseWriter()
        outline = Outline(
            title="两阶段标题",
            lede="今天重点看模型和项目。",
            sections=[SectionSpec(heading="今日重点", key_points=["OpenAI 更新"], source_hints=["OpenAI News"])],
        )
        outline_generator = FakeOutlineGenerator(outline)
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=None,
            article_linter=NoOpLinter(),
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            outline_generator=outline_generator,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertEqual(len(outline_generator.calls), 1)
        self.assertIn("briefing_angle", outline_generator.calls[0])
        self.assertIn("lead_items", outline_generator.calls[0])
        self.assertIn("secondary_items", outline_generator.calls[0])
        self.assertEqual(len(writer.render_calls), 1)
        self.assertIn("briefing_angle", writer.render_calls[0][1])
        self.assertIn("lead_items", writer.render_calls[0][1])
        self.assertIn("secondary_items", writer.render_calls[0][1])
        self.assertEqual(len(writer.calls), 0)

    def test_dry_run_with_writer_stays_on_compose_path(self) -> None:
        writer = TwoPhaseWriter()
        linter = RecordingLinter()
        publisher = FakePublisher()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=True,
            writer=writer,
            outline_generator=FakeOutlineGenerator(Outline(
                title="不应触发",
                lede="不应触发",
                sections=[],
            )),
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertEqual(writer.calls, [])
        self.assertEqual(writer.render_calls, [])
        self.assertEqual(linter.calls, [])
        self.assertEqual(publisher.calls, [])

    def test_dry_run_applies_cluster_tagger_before_returning_clusters(self) -> None:
        from unittest.mock import MagicMock
        from ai_digest.cluster_tagger import ClusterTagger
        from ai_digest.models import EventCluster

        item = DigestItem(
            title="OpenAI GPT-5",
            url="https://example.com/openai-gpt5",
            source="OpenAI News",
            published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            category="news",
            score=0.93,
            dedupe_key="news:openai-gpt5",
        )
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [item]
        mock_cluster_tagger = MagicMock(spec=ClusterTagger)
        mock_cluster_tagger.tag_clusters.return_value = [
            EventCluster(
                canonical_title="OpenAI GPT-5",
                canonical_url="https://example.com/openai-gpt5",
                sources=["OpenAI News"],
                items=[item],
                score=0.93,
                category="event",
                topic_tag="模型发布",
            )
        ]
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=mock_collector,
            publisher=None,
            article_linter=NoOpLinter(),
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=True,
            writer=None,
            cluster_tagger=mock_cluster_tagger,
            min_items=1,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        mock_cluster_tagger.tag_clusters.assert_called_once()
        self.assertIsNotNone(result.clusters)
        self.assertEqual(result.clusters[0].topic_tag, "模型发布")

    def test_publish_mode_falls_back_to_single_phase_when_outline_missing(self) -> None:
        writer = FakeWriter()
        outline_generator = FakeOutlineGenerator(None)
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=None,
            article_linter=NoOpLinter(),
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            outline_generator=outline_generator,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertEqual(len(outline_generator.calls), 1)
        self.assertEqual(len(writer.calls), 1)
        self.assertIn("briefing_angle", writer.calls[0])
        self.assertIn("lead_items", writer.calls[0])
        self.assertIn("secondary_items", writer.calls[0])

    def test_skips_publish_when_candidates_are_insufficient(self) -> None:
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Only item",
                        url="https://example.com/only",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.8,
                        dedupe_key="only-item",
                    )
                ]
            ),
            publisher=FakePublisher(),
            deduper=RecentDedupeFilter(state_store=state_store),
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "候选池不足")
        self.assertEqual(result.items_count, 1)
        self.assertEqual(result.publisher_draft_id, None)
        self.assertEqual(state_store.upserted_items, [])

    def test_composes_and_publishes_when_candidates_are_sufficient(self) -> None:
        publisher = FakePublisher()
        writer = FakeWriter()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            deduper=RecentDedupeFilter(state_store=state_store),
            writer=writer,
            article_linter=NoOpLinter(),
            dry_run=False,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "published")
        self.assertEqual(result.publisher_draft_id, "draft-123")
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(publisher.calls[0], writer.markdown)
        self.assertEqual(len(writer.calls), 1)
        self.assertEqual(len(state_store.upserted_items), 3)
        self.assertEqual(
            {item["dedupe_key"] for item in state_store.upserted_items},
            {"github:example/hot", "news:update", "tool:release"},
        )

    def test_publish_mode_lints_even_when_publisher_is_missing(self) -> None:
        linter = RecordingLinter()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=None,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=FakeWriter(),
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertEqual(result.publisher_draft_id, None)
        self.assertEqual(len(linter.calls), 1)
        self.assertEqual(len(state_store.upserted_items), 3)

    def test_publish_mode_skips_when_source_quota_reduces_items_below_minimum(self) -> None:
        linter = ExplodingLinter()
        publisher = FakePublisher()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title=f"QbitAI {idx}",
                        url=f"https://qbitai.com/{idx}",
                        source="量子位",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        summary="News item",
                        score=1.0 - idx * 0.01,
                        dedupe_key=f"qbitai:{idx}",
                    )
                    for idx in range(3)
                ]
            ),
            publisher=publisher,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=FakeWriter(),
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "候选池配额后不足")
        self.assertEqual(result.items_count, 2)
        self.assertEqual(linter.calls, 0)
        self.assertEqual(publisher.calls, [])
        self.assertEqual(state_store.upserted_items, [])

    def test_publish_mode_preserves_draft_id_when_persist_fails_after_publish(self) -> None:
        linter = RecordingLinter()
        publisher = FakePublisher()
        state_store = FailingPersistStateStore(RuntimeError("db write failed"))
        writer = FakeWriter(
            "# AI 每日新闻速递\n\n"
            "1. 先看重点。[a](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "这里有 [b](https://example.com/b) 和 [c](https://example.com/c)。\n\n"
            "## AI 技术进展\n\n"
            "还有 [d](https://example.com/d) 与更多背景说明。\n"
        )
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "Persist failed: db write failed")
        self.assertEqual(result.publisher_draft_id, "draft-123")
        self.assertEqual(linter.calls, [writer.markdown])
        self.assertEqual(publisher.calls, [writer.markdown])
        self.assertEqual(result.markdown, writer.markdown)
        self.assertEqual(state_store.upserted_items, [])

    def test_publish_mode_fails_when_article_lint_fails_and_skips_publisher(self) -> None:
        publisher = FakePublisher()
        linter = RecordingLinter(side_effect=RuntimeError("broken formatting"))
        state_store = FakeStateStore()
        writer = FakeWriter(
            "# AI 每日新闻速递\n\n"
            "1. 先看重点。[a](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "[b](https://example.com/b)\n\n"
            "## AI 技术进展\n\n"
            "[c](https://example.com/c)\n"
        )
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "Article lint failed: broken formatting")
        self.assertEqual(linter.calls, [writer.markdown])
        self.assertEqual(publisher.calls, [])
        self.assertEqual(state_store.upserted_items, [])

    def test_publish_mode_fails_when_ark_writer_is_missing(self) -> None:
        publisher = FakePublisher()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=None,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "writer is required for publish mode")
        self.assertIsNone(result.markdown)
        self.assertEqual(result.publisher_draft_id, None)
        self.assertEqual(publisher.calls, [])

    def test_dry_run_does_not_publish_even_when_publisher_exists(self) -> None:
        publisher = FakePublisher()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=publisher,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=True,
            writer=FakeWriter(),
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertIsNone(result.publisher_draft_id)
        self.assertEqual(publisher.calls, [])

    def test_publish_mode_builds_clustered_article_input(self) -> None:
        writer = FakeWriter()
        linter = RecordingLinter()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="OpenAI ships new API",
                        url="https://example.com/openai-api",
                        source="Hacker News AI",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        summary="API launch",
                        score=0.93,
                        dedupe_key="news:openai-api:a",
                    ),
                    DigestItem(
                        title="OpenAI ships new API today",
                        url="https://another.example.com/openai-api",
                        source="OpenAI News",
                        published_at=datetime(2026, 4, 10, 1, 0, tzinfo=timezone.utc),
                        category="news",
                        summary="Second source",
                        score=0.88,
                        dedupe_key="news:openai-api:b",
                    ),
                    DigestItem(
                        title="Archon",
                        url="https://github.com/example/archon",
                        source="GitHub Trending",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        summary="Agent framework",
                        score=0.89,
                        dedupe_key="github:example/archon",
                    ),
                    DigestItem(
                        title="Claude tooling update",
                        url="https://example.com/claude-tooling",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        summary="Tooling release",
                        score=0.84,
                        dedupe_key="news:claude-tooling",
                    ),
                ]
            ),
            publisher=FakePublisher(),
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "published")
        self.assertEqual(len(writer.calls), 1)
        self.assertEqual(len(linter.calls), 1)
        self.assertIn("briefing_angle", writer.calls[0])
        self.assertIn("lead_items", writer.calls[0])
        self.assertIn("secondary_items", writer.calls[0])
        self.assertEqual(len(writer.calls[0]["lead_items"]), 2)
        self.assertEqual(len(writer.calls[0]["secondary_items"]), 2)
        all_sources = {
            item["source"]
            for item in writer.calls[0]["lead_items"] + writer.calls[0]["secondary_items"]
        }
        self.assertEqual(all_sources, {"Hacker News AI", "OpenAI News", "GitHub Trending", "Tool Blog"})
        self.assertEqual(len(state_store.upserted_items), 4)

    def test_dry_run_does_not_force_article_lint(self) -> None:
        linter = ExplodingLinter()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title="Hot repo",
                        url="https://github.com/example/hot",
                        source="GitHub",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="github",
                        score=0.91,
                        dedupe_key="github:example/hot",
                    ),
                    DigestItem(
                        title="AI update",
                        url="https://example.com/update",
                        source="OpenAI Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        score=0.82,
                        dedupe_key="news:update",
                    ),
                    DigestItem(
                        title="Tool release",
                        url="https://example.com/tool",
                        source="Tool Blog",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="tool",
                        score=0.81,
                        dedupe_key="tool:release",
                    ),
                ]
            ),
            publisher=None,
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=True,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "composed")
        self.assertEqual(linter.calls, 0)
        self.assertEqual(len(state_store.upserted_items), 3)

    def test_publish_mode_caps_items_per_source_before_writing(self) -> None:
        writer = FakeWriter()
        linter = RecordingLinter()
        state_store = FakeStateStore()
        pipeline = DigestPipeline(
            collector=FakeCollector(
                [
                    DigestItem(
                        title=f"QbitAI {idx}",
                        url=f"https://qbitai.com/{idx}",
                        source="量子位",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        summary="News item",
                        score=1.0 - idx * 0.01,
                        dedupe_key=f"qbitai:{idx}",
                    )
                    for idx in range(4)
                ]
                + [
                    DigestItem(
                        title="Anthropic update",
                        url="https://example.com/anthropic",
                        source="Anthropic News",
                        published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                        category="news",
                        summary="Another news item",
                        score=0.96,
                        dedupe_key="anthropic:update",
                    )
                ]
            ),
            publisher=FakePublisher(),
            article_linter=linter,
            deduper=RecentDedupeFilter(state_store=state_store),
            dry_run=False,
            writer=writer,
            min_items=3,
        )

        result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, "published")
        self.assertEqual(len(linter.calls), 1)
        payload = writer.calls[0]
        clustered_sources = [
            item["source"]
            for item in payload["lead_items"] + payload["secondary_items"]
        ]
        self.assertLessEqual(clustered_sources.count("量子位"), 2)
        self.assertEqual(len(state_store.upserted_items), len(result.items))


class PipelineTest(unittest.TestCase):
    def test_pipeline_calls_cluster_tagger_when_injected(self):
        from unittest.mock import MagicMock, call
        from ai_digest.pipeline import DigestPipeline
        from ai_digest.cluster_tagger import ClusterTagger
        from ai_digest.models import DigestItem, EventCluster
        from datetime import datetime, timezone

        item = DigestItem(
            title="OpenAI GPT-5", url="https://a.com", source="A",
            published_at=datetime(2026,4,14,tzinfo=timezone.utc),
            category="news", score=0.9, dedupe_key="a"
        )
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [item]

        mock_cluster_tagger = MagicMock(spec=ClusterTagger)
        mock_cluster_tagger.tag_clusters.return_value = [
            EventCluster(
                canonical_title="OpenAI GPT-5", canonical_url="https://a.com",
                sources=["A"], items=[item], score=0.9, category="event", topic_tag="模型发布"
            )
        ]

        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = "draft_id_123"

        fake_writer = MagicMock()
        fake_writer.write.return_value = (
            "# AI 每日新闻速递\n\n"
            "1. 先看重点。[a](https://a.com)\n\n"
            "## 今日重点\n\n"
            "[OpenAI GPT-5](https://a.com)\n\n"
            "## AI 技术进展\n\n"
            "还有更多内容。\n"
        )

        # dry_run=False to reach the code path, writer required in non-dry-run mode
        pipeline = DigestPipeline(
            collector=mock_collector,
            publisher=mock_publisher,
            cluster_tagger=mock_cluster_tagger,
            writer=fake_writer,
            article_linter=NoOpLinter(),
            dry_run=False,
            min_items=1,
        )
        result = pipeline.run(now=datetime(2026,4,14,tzinfo=timezone.utc))

        assert result.status == "published"
        mock_cluster_tagger.tag_clusters.assert_called_once()


if __name__ == "__main__":
    unittest.main()
