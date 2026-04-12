from __future__ import annotations

import unittest

from ai_digest.article_linter import ArticleLinter


class ArticleLinterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.linter = ArticleLinter(min_body_chars=120)

    def test_accepts_article_that_matches_publish_rules(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "今天先看 3 条最值得跟的动态，整体节奏偏技术进展。\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "这一段包含 [链接一](https://example.com/1) 和 [链接二](https://example.com/2)。\n\n"
            "## AI 技术进展\n\n"
            "这里再补一个 [链接三](https://example.com/3)，用于满足发布检查。\n"
        )

        self.assertIsNone(self.linter.lint(markdown))

    def test_rejects_article_without_h1_title(self) -> None:
        markdown = (
            "## 今日重点\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## AI 技术进展\n\n"
            "这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)。\n"
        )

        with self.assertRaisesRegex(RuntimeError, "必须以 # 一级标题开头"):
            self.linter.lint(markdown)

    def test_rejects_article_with_fewer_than_two_h2_headings(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)。\n"
        )

        with self.assertRaisesRegex(RuntimeError, "至少需要 2 个 ## 二级标题"):
            self.linter.lint(markdown)

    def test_rejects_article_without_numbered_quick_overview(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "今天先看重点内容。\n\n"
            "## 今日重点\n\n"
            "这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)。\n\n"
            "## AI 技术进展\n\n"
            "补充一段正文，确保长度足够。\n"
        )

        with self.assertRaisesRegex(RuntimeError, "至少需要 1 个编号速览列表"):
            self.linter.lint(markdown)

    def test_rejects_article_with_fewer_than_three_inline_links(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "这里有 [链接一](https://example.com/1)。\n\n"
            "## AI 技术进展\n\n"
            "补充一段正文，确保长度足够。\n"
        )

        with self.assertRaisesRegex(RuntimeError, "至少需要 3 个 Markdown 行内链接"):
            self.linter.lint(markdown)

    def test_rejects_forbidden_phrases(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "摘要：这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)。\n\n"
            "## AI 技术进展\n\n"
            "补充一段正文，确保长度足够。\n"
        )

        with self.assertRaisesRegex(RuntimeError, "禁止出现"):
            self.linter.lint(markdown)

    def test_rejects_code_blocks(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n\n"
            "## 今日重点\n\n"
            "这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)。\n\n"
            "## AI 技术进展\n\n"
            "```python\nprint('hi')\n```\n"
        )

        with self.assertRaisesRegex(RuntimeError, "禁止包含代码块"):
            self.linter.lint(markdown)

    def test_rejects_articles_that_are_too_short(self) -> None:
        linter = ArticleLinter(min_body_chars=500)
        markdown = "# AI 每日新闻速递\n\n1. 先看最重要的一条。[详情](https://example.com/a)\n\n## 今日重点\n\n短文。\n\n## AI 技术进展\n\n短文。\n"

        with self.assertRaisesRegex(RuntimeError, "正文长度不足"):
            linter.lint(markdown)


if __name__ == "__main__":
    unittest.main()
