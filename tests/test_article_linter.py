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

    def test_accepts_article_with_single_h2_when_other_publish_rules_match(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "今天更值得看的，是几条已经开始发酵的 AI 动态，我先帮你筛出最该跟的方向。\n\n"
            "1. OpenAI 的新动作更值得先看。[详情](https://example.com/a)\n"
            "2. 开源项目这边也有一条值得跟进。[详情](https://example.com/b)\n\n"
            "## 今天最值得跟的几条\n\n"
            "先看行业动态，再看项目。这里补一个 [链接三](https://example.com/c)，"
            "并补足足够长度，确保这是一篇完整正文，而不是只有骨架的半成品文章。\n"
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

    def test_accepts_article_without_h2_headings(self) -> None:
        markdown = (
            "# AI 每日新闻速递\n\n"
            "今天这篇更像一封写给开发者的日报，我先把最重要的判断放前面。\n\n"
            "1. 先看最重要的一条。[详情](https://example.com/a)\n"
            "2. 第二条是开源项目变化。[详情](https://example.com/b)\n\n"
            "这里有 [链接一](https://example.com/1)、[链接二](https://example.com/2)、"
            "[链接三](https://example.com/3)，并补足篇幅，让正文满足发布时的最小长度要求。\n"
        )

        self.assertIsNone(self.linter.lint(markdown))

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
