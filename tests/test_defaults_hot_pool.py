from __future__ import annotations

import unittest

from ai_digest.defaults import build_default_source_specs


class DefaultHotPoolSpecsTest(unittest.TestCase):
    def test_default_sources_cover_hot_ai_pool(self) -> None:
        specs = build_default_source_specs()
        names = [spec.name for spec in specs]

        self.assertIn("GitHub Trending", names)
        self.assertIn("Hacker News AI", names)
        self.assertIn("Hugging Face Trending", names)
        self.assertIn("OpenAI News", names)
        self.assertIn("Anthropic News", names)
        self.assertIn("Google AI / Gemini", names)
        self.assertIn("机器之心", names)
        self.assertIn("新智元", names)
        self.assertIn("量子位", names)
        self.assertIn("CSDN AI", names)
        self.assertNotIn("arXiv cs.AI", names)


if __name__ == "__main__":
    unittest.main()
