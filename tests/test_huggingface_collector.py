from __future__ import annotations

import unittest

from ai_digest.collectors.huggingface import HFTrendingCollector


class HFTrendingCollectorTest(unittest.TestCase):
    def test_hf_collector_extracts_trending_models(self) -> None:
        html = """
        <article>
          <a href="/org/model-x">Model X</a>
          <div>Multimodal reasoning model for agents</div>
        </article>
        """

        items = HFTrendingCollector().parse_trending(
            html,
            page_url="https://huggingface.co/models?sort=trending",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, "project")
        self.assertEqual(items[0].title, "org/model-x")


if __name__ == "__main__":
    unittest.main()
