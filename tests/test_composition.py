from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.composition import DigestComposer
from ai_digest.models import DigestItem


class DigestComposerTest(unittest.TestCase):
    def test_renders_required_sections_and_links(self) -> None:
        composer = DigestComposer()
        items = [
            DigestItem(
                title="Hot GitHub repo",
                url="https://github.com/example/hot",
                source="GitHub",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="github",
                summary="A fast-growing repo for agent workflows.",
                why_it_matters="Useful for developers building agent tooling.",
                score=0.91,
                dedupe_key="github:example/hot",
            ),
            DigestItem(
                title="AI model update",
                url="https://example.com/ai-update",
                source="OpenAI Blog",
                published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                category="news",
                summary="A new capability lands in the platform.",
                why_it_matters="May affect product design decisions.",
                score=0.82,
                dedupe_key="news:ai-update",
            ),
        ]

        rendered = composer.compose(items, date="2026-04-10")

        self.assertIn("# AI 每日新闻速递", rendered)
        self.assertIn("今天的重点比较均衡", rendered)
        self.assertIn("### 先看结论", rendered)
        self.assertIn("## 今日重点", rendered)
        self.assertIn("## GitHub 新项目 / 热项目", rendered)
        self.assertIn("## AI 技术进展 / 工具更新", rendered)
        self.assertIn("**[Hot GitHub repo](https://github.com/example/hot)**", rendered)
        self.assertIn("A fast-growing repo for agent workflows.", rendered)
        self.assertIn("数据时间：2026-04-10", rendered)
        self.assertNotIn("摘要：", rendered)
        self.assertNotIn("价值：", rendered)
        self.assertIn("**看点**", rendered)
        self.assertIn("**为什么值得跟**", rendered)
        self.assertIn("**", rendered)

    def test_limits_each_section_to_five_items(self) -> None:
        composer = DigestComposer()
        items = []
        for idx in range(8):
            items.append(
                DigestItem(
                    title=f"GitHub {idx}",
                    url=f"https://github.com/example/repo-{idx}",
                    source="GitHub",
                    published_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                    category="github",
                    summary=f"Summary {idx}",
                    why_it_matters=f"Reason {idx}",
                    score=1.0 - idx * 0.01,
                    dedupe_key=f"github:repo-{idx}",
                )
            )

        rendered = composer.compose(items, date="2026-04-10")

        self.assertEqual(rendered.count("- **[GitHub"), 10)


if __name__ == "__main__":
    unittest.main()
