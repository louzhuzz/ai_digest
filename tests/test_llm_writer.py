from __future__ import annotations

import json
import unittest

from ai_digest.llm_writer import ARKArticleWriter, SYSTEM_PROMPT
from ai_digest.outline_generator import Outline, SectionSpec


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


class FakeTransport:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status = status
        self.body = body
        self.last_headers: dict[str, str] = {}
        self.last_url = ""
        self.last_timeout = 0
        self.last_payload: dict[str, object] | None = None

    def __call__(self, req, timeout: int = 0):
        self.last_url = req.full_url
        self.last_headers = dict(req.header_items())
        self.last_timeout = timeout
        raw_body = req.data.decode("utf-8") if req.data else "{}"
        self.last_payload = json.loads(raw_body)
        return _Response(self.body)


class ARKArticleWriterTest(unittest.TestCase):
    def test_system_prompt_prioritizes_short_professional_brief_over_bullet_digest(self) -> None:
        self.assertIn("热点候选池", SYSTEM_PROMPT)
        self.assertIn("开发者专业简报", SYSTEM_PROMPT)
        self.assertIn("800 到 1200 字", SYSTEM_PROMPT)
        self.assertIn("先给当天整体判断", SYSTEM_PROMPT)
        self.assertIn("只展开 2 个主重点", SYSTEM_PROMPT)
        self.assertIn("2 到 3 条短条补充", SYSTEM_PROMPT)
        self.assertIn("不要平均照顾所有候选项", SYSTEM_PROMPT)
        self.assertIn("不允许编造", SYSTEM_PROMPT)
        self.assertIn("不允许照抄输入里的英文摘要", SYSTEM_PROMPT)
        self.assertNotIn("编号速览", SYSTEM_PROMPT)
        self.assertNotIn("AI 每日新闻速递", SYSTEM_PROMPT)
        self.assertNotIn("自然的公众号文章", SYSTEM_PROMPT)
        self.assertNotIn("输出必须以 # 一级标题开头", SYSTEM_PROMPT)

    def test_ark_writer_posts_chat_completion_request(self) -> None:
        transport = FakeTransport(
            status=200,
            body=(
                '{"choices":[{"message":{"content":"# GPT-5 发布后，开发者先看这三点\\n\\n今天先看两条变化。\\n\\n## 模型能力变化\\n\\nA\\n\\n## 工具链和落地\\n\\nB\\n\\n## 其他补充\\n\\nC"}}]}'
            ).encode("utf-8"),
        )
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )

        markdown = writer.write(
            {
                "date": "2026-04-10",
                "news_signals": [{"title": "News One"}],
                "project_signals": [{"title": "Repo One"}],
                "signal_pool_size": 2,
            }
        )

        self.assertIn("# GPT-5 发布后，开发者先看这三点", markdown)
        self.assertEqual(transport.last_headers["Authorization"], "Bearer ark-key")
        self.assertIn("/chat/completions", transport.last_url)
        self.assertEqual(transport.last_timeout, 30)
        self.assertEqual(transport.last_payload["model"], "ep-model")
        self.assertIn("news_signals", transport.last_payload["messages"][1]["content"])

    def test_ark_writer_raises_when_title_is_missing(self) -> None:
        transport = FakeTransport(
            status=200,
            body=b'{"choices":[{"message":{"content":"\xe5\x8f\xaa\xe6\x9c\x89\xe5\xaf\xbc\xe8\xaf\xad\xe3\x80\x82"}}]}',
        )
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )

        with self.assertRaisesRegex(RuntimeError, "LLM output missing title"):
            writer.write(
                {
                    "date": "2026-04-10",
                    "news_signals": [{"title": "News One"}],
                    "project_signals": [{"title": "Repo One"}],
                    "signal_pool_size": 2,
                }
            )

    def test_ark_writer_wraps_timeout_with_context(self) -> None:
        class TimeoutTransport:
            def __call__(self, req, timeout: int = 0):
                raise TimeoutError("The read operation timed out")

        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=TimeoutTransport(),
        )

        with self.assertRaisesRegex(RuntimeError, "ARK article generation failed"):
            writer.write(
                {
                    "date": "2026-04-10",
                    "news_signals": [{"title": "News One"}],
                    "project_signals": [{"title": "Repo One"}],
                    "signal_pool_size": 2,
                }
            )


class ARKArticleWriterRenderTest(unittest.TestCase):
    def test_render_system_prompt_is_also_short_professional_brief_style(self) -> None:
        self.assertIn("开发者专业简报", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("短版专业简报", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("800 到 1200 字", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("先给当天整体判断", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("只展开 2 个主重点", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("2 到 3 条短条补充", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("按大纲结构写作", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("key_points 提到的每条事实都要覆盖", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("不允许照抄输入里的英文摘要", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("不允许编造输入中不存在的事实、数字、链接和结论", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertNotIn("公众号文章", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertNotIn("自然的公众号文章", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("你只能使用以下 Markdown 子集", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("禁止使用以下格式", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("- 代码块", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("- 表格", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("- 引用块", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("- HTML 标签", ARKArticleWriter.RENDER_SYSTEM_PROMPT)
        self.assertIn("- 多层嵌套列表", ARKArticleWriter.RENDER_SYSTEM_PROMPT)

    def test_render_accepts_outline_and_article_input(self):
        # Valid UTF-8 bytes representing: # AI 每日热点\n\n今天有三条值得关注的动态。\n\n## 模型发布\n\nOpenAI 发布 GPT-5。
        body = (
            b'{"choices":[{"message":{"content":"# AI \xe7\x83\xad\xe7\x82\xb9\xe6\x97\xa5\xe6\x8a\xa5'
            b'\\n\\n\xe4\xbb\x8a\xe5\xa4\xa9\xe6\x9c\x89\xe4\xb8\x89\xe6\x9d\xa1\xe5\x80\xbc\xe5\xbe\x97'
            b'\xe5\x85\xb3\xe6\xb3\xa8\xe7\x9a\x84\xe5\x8a\xa8\xe6\x80\x81\xe3\x80\x82'
            b'\\n\\n## \xe6\xa8\xa1\xe5\x9e\x8b\xe5\x8f\x91\xe5\xb8\x83'
            b'\\n\\nOpenAI \xe5\x8f\x91\xe5\xb8\x83 GPT-5\xe3\x80\x82"}}]}'
        )
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI \u70ed\u70b9\u65e5\u62a5",
            lede="\u4eca\u5929\u6709\u4e09\u6761\u503c\u5f97\u5173\u6ce8\u7684\u52a8\u6001\u3002",
            sections=[
                SectionSpec(
                    heading="\u6a21\u578b\u53d1\u5e03",
                    key_points=["OpenAI \u53d1\u5e03 GPT-5"],
                    source_hints=["\u673a\u5668\u4e4b\u5fc3"],
                ),
            ],
        )
        markdown = writer.render(outline, {"date": "2026-04-14", "items": []})
        self.assertTrue(markdown.startswith("# "))
        self.assertIn(outline.title, markdown)
        self.assertIn(outline.lede, markdown)
        user_content = transport.last_payload["messages"][1]["content"]
        self.assertIn(outline.title, user_content)
        self.assertIn(outline.lede, user_content)
        self.assertIn("模型发布", user_content)
        self.assertIn("OpenAI 发布 GPT-5", user_content)
        self.assertIn("标题使用 outline.title", user_content)
        self.assertIn("首段承接 outline.lede", user_content)
        self.assertIn("章节标题使用各 sections[].heading", user_content)
        self.assertIn("覆盖全部 key_points", user_content)
        self.assertIn("不补充输入里没有的事实", user_content)

    def test_render_accepts_level_three_heading_when_it_matches_outline(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n### 模型发布\\n\\nOpenAI 发布 GPT-5。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        markdown = writer.render(outline, {"date": "2026-04-14", "items": []})

        self.assertIn("### 模型发布", markdown)

    def test_render_accepts_heading_and_body_in_same_markdown_block(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\nOpenAI 发布 GPT-5。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        markdown = writer.render(outline, {"date": "2026-04-14", "items": []})

        self.assertIn("## 模型发布", markdown)
        self.assertIn("OpenAI 发布 GPT-5", markdown)

    def test_render_accepts_adjacent_sections_without_blank_line_between_them(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\nOpenAI 发布 GPT-5。\\n## 其他补充\\nClaude Code 更新了工作流。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
                SectionSpec(
                    heading="其他补充",
                    key_points=["Claude Code 更新了工作流"],
                    source_hints=["Anthropic"],
                ),
            ],
        )

        markdown = writer.render(outline, {"date": "2026-04-14", "items": []})

        self.assertIn("## 模型发布", markdown)
        self.assertIn("## 其他补充", markdown)

    def test_render_rejects_title_that_diverges_from_outline(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报 - 开发者简报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\n\\nOpenAI 发布 GPT-5。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "missing title"):
            writer.render(outline, {"date": "2026-04-14", "items": []})

    def test_render_rejects_missing_outline_heading(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n这次重点讨论模型发布，但没有用标题形式。\\n\\nOpenAI 发布 GPT-5。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "missing heading"):
            writer.render(outline, {"date": "2026-04-14", "items": []})

    def test_render_rejects_missing_lede(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天先看两条变化。\\n\\n## 模型发布\\n\\nOpenAI 发布 GPT-5。\\n\\n今天有三条值得关注的动态。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "missing lede"):
            writer.render(outline, {"date": "2026-04-14", "items": []})

    def test_render_rejects_missing_key_point_coverage(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\n\\nOpenAI 发布了新模型，但没有写出具体型号。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "missing key point"):
            writer.render(outline, {"date": "2026-04-14", "items": []})

    def test_render_rejects_sections_that_break_outline_order(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 其他补充\\n\\nClaude Code 更新了工作流。\\n\\n## 模型发布\\n\\nOpenAI 发布 GPT-5。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
                SectionSpec(
                    heading="其他补充",
                    key_points=["Claude Code 更新了工作流"],
                    source_hints=["Anthropic"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "section order"):
            writer.render(outline, {"date": "2026-04-14", "items": []})

    def test_render_rejects_unexpected_extra_heading_outside_outline(self) -> None:
        body = (
            '{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\nOpenAI 发布 GPT-5。\\n\\n## 市场背景\\n行业还在继续消化。"}}]}'
        ).encode("utf-8")
        transport = FakeTransport(body=body)
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(
                    heading="模型发布",
                    key_points=["OpenAI 发布 GPT-5"],
                    source_hints=["机器之心"],
                ),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "unexpected headings"):
            writer.render(outline, {"date": "2026-04-14", "items": []})


if __name__ == "__main__":
    unittest.main()
