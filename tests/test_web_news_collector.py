from __future__ import annotations

import unittest

from ai_digest.collectors.web_news import WebNewsIndexCollector


class WebNewsCollectorTest(unittest.TestCase):
    def test_web_news_index_collector_extracts_links(self) -> None:
        html = """
        <a href="/news/ai-adoption/">AI Adoption</a>
        <a href="/news/new-update">New Update</a>
        """

        items = WebNewsIndexCollector("OpenAI News").parse_index(
            html,
            base_url="https://openai.com/news",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "OpenAI News")
        self.assertEqual(items[0].url, "https://openai.com/news/new-update")

    def test_web_news_index_collector_respects_allowed_path_prefixes(self) -> None:
        html = """
        <a href="/news/ai-product/">AI Product</a>
        <a href="/blog/general-update/">General Update</a>
        """

        items = WebNewsIndexCollector(
            "Anthropic News",
            allowed_path_prefixes=("/news/",),
        ).parse_index(
            html,
            base_url="https://www.anthropic.com/news",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://www.anthropic.com/news/ai-product/")

    def test_public_platform_requires_ai_signal_in_title_not_domain(self) -> None:
        html = """
        <a href="/2026/04/car-news">奔驰崩了，在华销量大跌27%</a>
        <a href="/2026/04/ai-news">Claude 神之 bug：给自己下指令，还诬赖用户？</a>
        """

        items = WebNewsIndexCollector(
            "量子位",
            allowed_path_prefixes=("/202",),
        ).parse_index(
            html,
            base_url="https://www.qbitai.com/",
        )

        self.assertEqual(len(items), 1)
        self.assertIn("Claude", items[0].title)

    def test_public_platform_filters_known_column_pages(self) -> None:
        html = """
        <a href="/ai_shortlist">AI Shortlist</a>
        <a href="/reference/abc">空间智能视角下，Agent 要补足哪些缺失来完成 Action？</a>
        """

        items = WebNewsIndexCollector(
            "机器之心",
            allowed_path_prefixes=("/ai_shortlist", "/reference/"),
        ).parse_index(
            html,
            base_url="https://www.jiqizhixin.com/",
        )

        self.assertEqual(len(items), 1)
        self.assertIn("Agent", items[0].title)


if __name__ == "__main__":
    unittest.main()
