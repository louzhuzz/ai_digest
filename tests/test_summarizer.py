from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.models import DigestItem
from ai_digest.summarizer import RuleBasedSummarizer


class RuleBasedSummarizerTest(unittest.TestCase):
    def test_fills_missing_summary_and_why_it_matters(self) -> None:
        item = DigestItem(
            title="Hot repo",
            url="https://github.com/example/hot",
            source="GitHub Trending",
            published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            category="github",
            metadata={"stars_growth": 123, "description": "Agentic research tool."},
        )

        enriched = RuleBasedSummarizer().summarize([item])[0]

        self.assertEqual(enriched.summary, "Agentic research tool.")
        self.assertIn("123", enriched.why_it_matters)
        self.assertIn("GitHub 热门项目", enriched.why_it_matters)


if __name__ == "__main__":
    unittest.main()
