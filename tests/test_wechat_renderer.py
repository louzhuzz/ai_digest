# tests/test_wechat_renderer.py
from __future__ import annotations
import unittest
from ai_digest.wechat_renderer import render_wechat_html

class WeChatRendererTest(unittest.TestCase):
    def test_renders_h1_as_styled_paragraph(self):
        html = render_wechat_html("# AI 热点\n\n正文内容")
        assert "<h1" not in html
        assert "font-size:20px" in html
        assert "font-weight:bold" in html
        assert "AI 热点" in html

    def test_renders_h2_as_styled_paragraph(self):
        html = render_wechat_html("## 模型发布\n\n内容")
        assert "<h2" not in html
        assert "<strong>模型发布</strong>" in html
        assert "font-size:22px" in html
        assert "font-weight:700" in html

    def test_renders_h3_as_styled_paragraph(self):
        html = render_wechat_html("### 小标题\n\n内容")
        assert "<h3" not in html
        assert "<strong>小标题</strong>" in html
        assert "font-size:18px" in html

    def test_renders_paragraph(self):
        html = render_wechat_html("这是一段正文。")
        assert "font-size:16px" in html
        assert "line-height:1.8" in html
        assert "color:#333" in html
        assert "这是一段正文" in html

    def test_renders_ordered_list_without_ol_tags(self):
        html = render_wechat_html("1. 第一条\n2. 第二条")
        assert "<ol>" not in html
        assert "1. 第一条" in html

    def test_renders_bold_text(self):
        html = render_wechat_html("这是**加粗文字**。")
        assert "<strong" in html
        assert "加粗文字" in html

    def test_renders_link(self):
        html = render_wechat_html("[链接文字](https://example.com)")
        assert "<a href=" in html
        assert "color:#1a73e8" in html
        assert "链接文字" in html