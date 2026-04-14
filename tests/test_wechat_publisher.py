from __future__ import annotations

import unittest
from unittest.mock import Mock

from ai_digest.publishers.wechat import WeChatDraftPublisher


class WeChatDraftPublisherTest(unittest.TestCase):
    def test_build_payload_converts_markdown_to_html(self) -> None:
        publisher = WeChatDraftPublisher()
        payload = publisher.build_payload(
            title="AI 每日新闻速递",
            markdown="# AI 每日新闻速递\n\n- [OpenAI](https://openai.com)",
        )

        self.assertEqual(payload["articles"][0]["title"], "AI 每日新闻速递")
        content = payload["articles"][0]["content"]
        # 新渲染器不使用 <h1> 标签，而是用 inline style
        self.assertNotIn("<h1>", content)
        self.assertIn('href="https://openai.com"', content)
        self.assertIn("OpenAI</a>", content)

    def test_build_payload_supports_heading_numbered_list_and_bold(self) -> None:
        publisher = WeChatDraftPublisher()
        payload = publisher.build_payload(
            title="AI 每日新闻速递",
            markdown="# AI 每日新闻速递\n\n### 今天先看什么\n\n1. **先看模型**\n2. 再看工具",
        )

        content = payload["articles"][0]["content"]
        self.assertIn("font-size:18px", content)
        self.assertIn("今天先看什么", content)
        # 新渲染器使用 <p> 标签而不是 <ol>/<li>
        self.assertNotIn("<ol>", content)
        self.assertNotIn("<li>", content)

    def test_build_payload_renders_h2_as_wechat_friendly_section_heading(self) -> None:
        publisher = WeChatDraftPublisher()
        payload = publisher.build_payload(
            title="AI 每日新闻速递",
            markdown="# AI 每日新闻速递\n\n## 今日重点\n\n正文",
        )

        content = payload["articles"][0]["content"]
        self.assertNotIn("<h2>", content)
        self.assertIn("font-size:22px", content)
        self.assertIn("今日重点", content)

    def test_publish_in_dry_run_mode_does_not_call_api(self) -> None:
        http_client = Mock()
        publisher = WeChatDraftPublisher(dry_run=True, http_client=http_client)

        draft_id = publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

        self.assertEqual(draft_id, "")
        self.assertIsNotNone(publisher.last_payload)
        http_client.assert_not_called()

    def test_publish_uses_timeout_when_calling_wechat_api(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"media_id":"draft-123"}'
        http_client = Mock(return_value=response)
        publisher = WeChatDraftPublisher(
            access_token="token-123",
            cover_media_id="thumb-123",
            dry_run=False,
            http_client=http_client,
        )

        draft_id = publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

        self.assertEqual(draft_id, "draft-123")
        self.assertEqual(http_client.call_args.kwargs["timeout"], 15)

    def test_publish_raises_when_cover_upload_fails(self) -> None:
        upload_response = Mock()
        upload_response.__enter__ = Mock(return_value=upload_response)
        upload_response.__exit__ = Mock(return_value=False)
        upload_response.read.return_value = b'{"errcode":40007,"errmsg":"invalid media_id"}'
        http_client = Mock(return_value=upload_response)
        publisher = WeChatDraftPublisher(
            access_token="token-123",
            dry_run=False,
            http_client=http_client,
            cover_image_provider=Mock(return_value=b"jpeg-bytes"),
        )

        with self.assertRaisesRegex(RuntimeError, "WeChat thumb upload failed: invalid media_id"):
            publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

    def test_publish_raises_wechat_api_error(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"errcode":40007,"errmsg":"invalid media_id"}'
        http_client = Mock(return_value=response)
        publisher = WeChatDraftPublisher(
            access_token="token-123",
            dry_run=False,
            http_client=http_client,
            cover_media_id="thumb-123",
        )

        with self.assertRaisesRegex(RuntimeError, "invalid media_id"):
            publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

    def test_publish_generates_and_uploads_cover_when_media_id_missing(self) -> None:
        upload_response = Mock()
        upload_response.__enter__ = Mock(return_value=upload_response)
        upload_response.__exit__ = Mock(return_value=False)
        upload_response.read.return_value = b'{"type":"thumb","media_id":"thumb-123"}'

        draft_response = Mock()
        draft_response.__enter__ = Mock(return_value=draft_response)
        draft_response.__exit__ = Mock(return_value=False)
        draft_response.read.return_value = b'{"media_id":"draft-123"}'

        http_client = Mock(side_effect=[upload_response, draft_response])
        cover_image_provider = Mock(return_value=b"jpeg-bytes")
        publisher = WeChatDraftPublisher(
            access_token="token-123",
            dry_run=False,
            http_client=http_client,
            cover_image_provider=cover_image_provider,
        )

        draft_id = publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

        self.assertEqual(draft_id, "draft-123")
        cover_image_provider.assert_called_once_with("AI 每日新闻速递")
        first_request = http_client.call_args_list[0].args[0]
        second_request = http_client.call_args_list[1].args[0]
        self.assertIn("type=thumb", first_request.full_url)
        self.assertIn("draft/add", second_request.full_url)

    def test_publish_wraps_draft_timeout_with_context(self) -> None:
        http_client = Mock(side_effect=TimeoutError("The read operation timed out"))
        publisher = WeChatDraftPublisher(
            access_token="token-123",
            cover_media_id="thumb-123",
            dry_run=False,
            http_client=http_client,
        )

        with self.assertRaisesRegex(RuntimeError, "WeChat draft add request failed"):
            publisher.publish("# AI 每日新闻速递\n", title="AI 每日新闻速递")

    def test_build_payload_uses_wechat_renderer(self) -> None:
        from ai_digest.publishers.wechat import WeChatDraftPublisher

        publisher = WeChatDraftPublisher(dry_run=True)
        publisher.publish(markdown="# 标题\n\n正文", title="Test")
        html = publisher.last_payload["articles"][0]["content"]
        # 确认用的是新渲染器（微信样式，不是 <h1>/<h2> 标签）
        assert "<h1" not in html
        assert "<h2" not in html
        assert "font-size:20px" in html


if __name__ == "__main__":
    unittest.main()
