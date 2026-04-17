from __future__ import annotations

import unittest
from datetime import datetime, timezone

from unittest.mock import patch

from ai_digest.models import DigestItem
from ai_digest.runner import DigestJobRunner


class FailingCollector:
    def collect(self):
        raise RuntimeError("boom")


class DigestJobRunnerTest(unittest.TestCase):
    def test_returns_failed_result_and_sends_alert_on_exception(self) -> None:
        alerts: list[str] = []

        runner = DigestJobRunner(
            collector_factory=lambda: FailingCollector(),
            alert_callback=alerts.append,
        )

        result = runner.run()

        self.assertEqual(result.status, "failed")
        self.assertIn("boom", result.error or "")
        self.assertEqual(alerts, ["boom"])


    def test_passes_deduper_to_pipeline(self) -> None:
        class Collector:
            def collect(self):
                return []

        fake_pipeline_calls = {}

        class FakeDigestPipeline:
            def __init__(self, **kwargs):
                fake_pipeline_calls['kwargs'] = kwargs

            def run(self, now=None):
                fake_pipeline_calls['now'] = now
                return type('Result', (), {
                    'status': 'skipped',
                    'reason': '候选池不足',
                    'items_count': 0,
                    'publisher_draft_id': None,
                    'markdown': None,
                    'clusters': None,
                })()

        deduper = object()
        with patch('ai_digest.runner.DigestPipeline', FakeDigestPipeline):
            runner = DigestJobRunner(
                collector_factory=lambda: Collector(),
                deduper=deduper,
            )
            result = runner.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

        self.assertEqual(result.status, 'skipped')
        self.assertIs(fake_pipeline_calls['kwargs']['deduper'], deduper)
        self.assertIsInstance(fake_pipeline_calls['kwargs']['collector'], Collector)

    def test_uses_explicit_publish_mode_even_when_writer_is_missing(self) -> None:
        class Collector:
            def collect(self):
                return [
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

        class FakePublisher:
            def publish(self, markdown):
                return "draft_123"

        runner = DigestJobRunner(
            collector_factory=lambda: Collector(),
            publisher=FakePublisher(),
            writer=None,
            dry_run=False,
        )

        result = runner.run()

        self.assertEqual(result.status, "published")
        self.assertIsNotNone(result.markdown)


if __name__ == "__main__":
    unittest.main()
