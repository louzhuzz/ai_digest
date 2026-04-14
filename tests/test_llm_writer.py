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
    def test_system_prompt_prioritizes_natural_wechat_article_over_rigid_template(self) -> None:
        self.assertIn("热点候选池", SYSTEM_PROMPT)
        self.assertIn("自然的公众号文章", SYSTEM_PROMPT)
        self.assertIn("推荐结构", SYSTEM_PROMPT)
        self.assertIn("导语", SYSTEM_PROMPT)
        self.assertIn("编号速览", SYSTEM_PROMPT)
        self.assertIn("正文展开", SYSTEM_PROMPT)
        self.assertIn("不允许编造", SYSTEM_PROMPT)
        self.assertIn("不允许照抄输入里的英文摘要", SYSTEM_PROMPT)
        self.assertNotIn("至少保留 2 处加粗", SYSTEM_PROMPT)
        self.assertNotIn("输出必须以 # 一级标题开头", SYSTEM_PROMPT)

    def test_ark_writer_posts_chat_completion_request(self) -> None:
        transport = FakeTransport(
            status=200,
            body=b'{"choices":[{"message":{"content":"# AI \xe6\xaf\x8f\xe6\x97\xa5\xe6\x96\xb0\xe9\x97\xbb\xe9\x80\x9f\xe9\x80\x92\\n\\n\xe4\xbb\x8a\xe5\xa4\xa9\xe5\x85\x88\xe7\x9c\x8b\xe4\xb8\x89\xe6\x9d\xa1\xe3\x80\x82\\n\\n## \xe4\xbb\x8a\xe6\x97\xa5\xe9\x87\x8d\xe7\x82\xb9\\n\\nA\\n\\n## GitHub \xe6\x96\xb0\xe9\xa1\xb9\xe7\x9b\xae / \xe7\x83\xad\xe9\xa1\xb9\xe7\x9b\xae\\n\\nB\\n\\n## AI \xe6\x8a\x80\xe6\x9c\xaf\xe8\xbf\x9b\xe5\xb1\x95\\n\\nC"}}]}',
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

        self.assertIn("# AI 每日新闻速递", markdown)
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
    def test_render_accepts_outline_and_article_input(self):
        # Valid UTF-8 bytes representing: # AI 每日热点\n\n今天有三条值得关注的动态。\n\n## 模型发布\n\nOpenAI 发布 GPT-5。
        body = (
            b'{"choices":[{"message":{"content":"# AI \xe6\xaf\x8f\xe6\x97\xa5\xe7\x83\xad\xe7\x82\xb9'
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
        self.assertTrue("\u6a21\u578b\u53d1\u5e03" in markdown or "GPT" in markdown)


if __name__ == "__main__":
    unittest.main()
