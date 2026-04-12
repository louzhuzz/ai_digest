from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_digest.defaults import CompositeCollector, build_default_collector, build_default_source_specs
from ai_digest.settings import AppSettings


class DefaultSourceSpecsTest(unittest.TestCase):
    def test_default_sources_cover_news_and_github(self) -> None:
        specs = build_default_source_specs()

        self.assertEqual(
            [spec.name for spec in specs],
            [
                "GitHub Trending",
                "Hacker News AI",
                "Hugging Face Trending",
                "OpenAI News",
                "Anthropic News",
                "Google AI / Gemini",
                "机器之心",
                "新智元",
                "量子位",
                "CSDN AI",
            ],
        )
        self.assertEqual(specs[0].url, "https://github.com/trending")
        self.assertEqual(specs[1].url, "https://news.ycombinator.com/")
        self.assertEqual(specs[2].url, "https://huggingface.co/models?sort=trending")
        self.assertEqual(specs[3].url, "https://openai.com/news")


    def test_build_default_runner_wires_state_store_and_dedupe_filter(self) -> None:
        settings = AppSettings(
            wechat=None,
            ark=None,
            dry_run=True,
            draft_mode=False,
            state_db_path=Path('/tmp/openclaw-state.db'),
        )

        fake_runner = object()
        fake_store = MagicMock()
        fake_deduper = object()

        with patch('ai_digest.defaults.SqliteStateStore', return_value=fake_store) as store_cls, \
            patch('ai_digest.defaults.RecentDedupeFilter', return_value=fake_deduper) as dedupe_cls, \
            patch('ai_digest.defaults.DigestJobRunner', return_value=fake_runner) as runner_cls:
            from ai_digest.defaults import build_default_runner

            runner = build_default_runner(settings=settings)

        self.assertIs(runner, fake_runner)
        store_cls.assert_called_once_with(settings.state_db_path)
        fake_store.initialize.assert_called_once()
        dedupe_cls.assert_called_once_with(state_store=fake_store)
        runner_cls.assert_called_once()
        self.assertIs(runner_cls.call_args.kwargs['deduper'], fake_deduper)
        self.assertEqual(runner_cls.call_args.kwargs['dry_run'], settings.dry_run)

    def test_default_collector_is_composite(self) -> None:
        collector = build_default_collector()

        items = collector.collectors
        self.assertEqual(len(items), 10)

    def test_composite_collector_continues_when_one_source_fails(self) -> None:
        class GoodCollector:
            def __init__(self, payload):
                self.payload = payload

            def collect(self):
                return self.payload

        class BadCollector:
            def collect(self):
                raise TimeoutError("source timeout")

        collector = CompositeCollector(
            [
                GoodCollector(["a"]),
                BadCollector(),
                GoodCollector(["b"]),
            ]
        )

        items = collector.collect()

        self.assertEqual(items, ["a", "b"])
        self.assertEqual(len(collector.errors), 1)
        self.assertIn("source timeout", collector.errors[0])


if __name__ == "__main__":
    unittest.main()
