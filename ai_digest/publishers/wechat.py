from __future__ import annotations
# -*- coding: utf-8 -*-

import html
import json
import re
import uuid
from dataclasses import dataclass
from typing import Callable
from typing import Any
from urllib import parse, request

from ..cover_image import generate_cover_image
from ..http_client import DEFAULT_TIMEOUT_SECONDS
from ..wechat_image_uploader import WeChatImageUploader


# ── Markdown → 微信公众号 HTML 渲染 ─────────────────────

_WX_PARAGRAPH_STYLE = 'font-size:16px; line-height:1.8; color:#333; margin:1em 0;'
_WX_H1_STYLE = 'font-size:20px; font-weight:bold; color:#1a1a1a; margin:1.2em 0 0.6em;'
_WX_H2_STYLE = 'margin:1.4em 0 0.55em; font-size:22px; font-weight:700; line-height:1.45; color:#1f2937;'
_WX_H3_STYLE = 'margin:1em 0 0.45em; font-size:18px; font-weight:700; line-height:1.5; color:#334155;'
_WX_LINK_STYLE = 'color:#1a73e8; text-decoration:underline;'
_WX_IMAGE_STYLE = 'max-width:100%; height:auto; margin:1em 0; display:block;'

_WX_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_WX_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_WX_BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
_WX_ORDERED_LIST = re.compile(r"\d+\.\s+(.*)")


def _wx_render_inline(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in _WX_LINK_PATTERN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        label, url = match.groups()
        parts.append(f'<a href="{html.escape(url, quote=True)}" style="{_WX_LINK_STYLE}">{html.escape(label)}</a>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    rendered = "".join(parts)
    return _WX_BOLD_PATTERN.sub(lambda m: f"<strong>{html.escape(m.group(1))}</strong>", rendered)


def _wx_render_image_line(line: str) -> str:
    match = _WX_IMAGE_PATTERN.search(line)
    if not match:
        return ""
    alt, url = match.groups()
    return f'<p><img src="{html.escape(url, quote=True)}" alt="{html.escape(alt)}" style="{_WX_IMAGE_STYLE}"/></p>'


def render_wechat_html(markdown: str) -> str:
    """将 Markdown 转换为微信公众号兼容的 HTML（内联样式）。"""
    parts: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue
        if line.startswith("![](") or _WX_IMAGE_PATTERN.match(line.strip()):
            if in_list:
                parts.append("</ul>")
                in_list = False
            img = _wx_render_image_line(line.strip())
            if img:
                parts.append(img)
            continue
        if line.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f'<p style="{_WX_H1_STYLE}"><strong>{_wx_render_inline(line[2:].strip())}</strong></p>')
            continue
        if line.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f'<p style="{_WX_H2_STYLE}"><strong>{_wx_render_inline(line[3:].strip())}</strong></p>')
            continue
        if line.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f'<p style="{_WX_H3_STYLE}"><strong>{_wx_render_inline(line[4:].strip())}</strong></p>')
            continue
        if line.startswith("- "):
            if not in_list:
                parts.append('<ul style="margin:1em 0; padding-left:1.5em;">')
                in_list = True
            parts.append(f'<li style="margin-bottom:0.3em;">{_wx_render_inline(line[2:].strip())}</li>')
            continue
        if _WX_ORDERED_LIST.match(line.strip()):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f'<p style="{_WX_PARAGRAPH_STYLE}">{_wx_render_inline(line.strip())}</p>')
            continue
        if in_list:
            parts.append("</ul>")
            in_list = False
        parts.append(f'<p style="{_WX_PARAGRAPH_STYLE}">{_wx_render_inline(line)}</p>')
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def markdown_to_html(markdown: str) -> str:
    return render_wechat_html(markdown)


@dataclass
class WeChatDraftPublisher:
    access_token: str | None = None
    cover_media_id: str = ""
    dry_run: bool = True
    http_client: Any | None = None
    api_url: str = "https://api.weixin.qq.com/cgi-bin/draft/add"
    upload_api_url: str = "https://api.weixin.qq.com/cgi-bin/material/add_material"
    cover_image_provider: Callable[[str], bytes] = generate_cover_image
    last_payload: dict[str, Any] | None = None
    image_uploader: WeChatImageUploader | None = None

    def build_payload(
        self,
        *,
        title: str,
        markdown: str,
        author: str = "",
        digest: str = "",
        cover_media_id: str = "",
        content_source_url: str = "",
    ) -> dict[str, Any]:
        article = {
            "title": title,
            "author": author,
            "digest": digest or title,
            "content": render_wechat_html(markdown),
            "content_source_url": content_source_url,
            "thumb_media_id": cover_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        return {"articles": [article]}

    def publish(self, markdown: str, title: str = "AI 每日新闻速递") -> str:
        if self.dry_run or not self.access_token:
            payload = self.build_payload(title=title, markdown=markdown)
            self.last_payload = payload
            return ""
        if self.image_uploader is not None:
            markdown = self.image_uploader.upload_all(markdown)

        cover_media_id = self.cover_media_id
        if not cover_media_id:
            cover_media_id = self._upload_cover_image(self.cover_image_provider(title))

        payload = self.build_payload(title=title, markdown=markdown, cover_media_id=cover_media_id)
        self.last_payload = payload

        url = f"{self.api_url}?access_token={parse.quote(self.access_token)}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        opener = self.http_client or request.urlopen
        try:
            with opener(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"WeChat draft add request failed: {exc}") from exc
        if decoded.get("errcode"):
            errmsg = decoded.get("errmsg", "unknown WeChat API error")
            raise RuntimeError(f"WeChat draft add failed: {errmsg}")
        media_id = str(decoded.get("media_id", ""))
        if not media_id:
            raise RuntimeError(f"WeChat draft add failed: {decoded}")
        return media_id

    def _upload_cover_image(self, image_bytes: bytes) -> str:
        if not image_bytes:
            raise RuntimeError("Generated empty cover image")

        boundary = f"----OpenClaw{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = f"{self.upload_api_url}?access_token={parse.quote(self.access_token or '')}&type=thumb"
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        opener = self.http_client or request.urlopen
        try:
            with opener(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"WeChat thumb upload request failed: {exc}") from exc

        if decoded.get("errcode"):
            errmsg = decoded.get("errmsg", "unknown WeChat API error")
            raise RuntimeError(f"WeChat thumb upload failed: {errmsg}")

        media_id = str(decoded.get("media_id", ""))
        if not media_id:
            raise RuntimeError(f"WeChat thumb upload failed: {decoded}")
        return media_id
