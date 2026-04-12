from __future__ import annotations

import unittest

from ai_digest.collectors.hn import HNFrontPageCollector


class HNCollectorTest(unittest.TestCase):
    def test_hn_collector_extracts_ai_news_items(self) -> None:
        html = """
        <tr class="athing">
          <span class="titleline"><a href="https://example.com/openai-update">OpenAI launches new model</a></span>
        </tr>
        <tr>
          <span class="score">120 points</span>
        </tr>
        """

        items = HNFrontPageCollector().parse_frontpage(html, page_url="https://news.ycombinator.com/")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, "news")
        self.assertEqual(items[0].metadata["community_heat"], 120)

    def test_hn_collector_ignores_non_ai_titles_with_incidental_ai_letters(self) -> None:
        html = """
        <tr class="athing">
          <span class="titleline"><a href="https://example.com/italo">Italo Calvino: A traveller in a world of uncertainty</a></span>
        </tr>
        <tr>
          <span class="score">88 points</span>
        </tr>
        """

        items = HNFrontPageCollector().parse_frontpage(html, page_url="https://news.ycombinator.com/")

        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
