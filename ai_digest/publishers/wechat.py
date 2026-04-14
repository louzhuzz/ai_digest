from __future__ import annotations

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


LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
ORDERED_LIST_PATTERN = re.compile(r"\d+\.\s+(.*)")

WECHAT_H2_STYLE = (
    "margin:1.4em 0 0.55em;"
    "font-size:22px;"
    "font-weight:700;"
    "line-height:1.45;"
    "color:#1f2937;"
)
WECHAT_H3_STYLE = (
    "margin:1em 0 0.45em;"
    "font-size:18px;"
    "font-weight:700;"
    "line-height:1.5;"
    "color:#334155;"
)


def _render_inline(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in LINK_PATTERN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        label, url = match.groups()
        parts.append(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    rendered = "".join(parts)
    return BOLD_PATTERN.sub(lambda match: f"<strong>{html.escape(match.group(1))}</strong>", rendered)


def markdown_to_html(markdown: str) -> str:
    parts: list[str] = []
    in_unordered_list = False
    in_ordered_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            if in_ordered_list:
                parts.append("</ol>")
                in_ordered_list = False
            continue

        if line.startswith("# "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            if in_ordered_list:
                parts.append("</ol>")
                in_ordered_list = False
            parts.append(f"<h1>{_render_inline(line[2:].strip())}</h1>")
            continue

        if line.startswith("## "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            if in_ordered_list:
                parts.append("</ol>")
                in_ordered_list = False
            parts.append(
                f'<p style="{WECHAT_H2_STYLE}"><strong>{_render_inline(line[3:].strip())}</strong></p>'
            )
            continue

        if line.startswith("### "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            if in_ordered_list:
                parts.append("</ol>")
                in_ordered_list = False
            parts.append(
                f'<p style="{WECHAT_H3_STYLE}"><strong>{_render_inline(line[4:].strip())}</strong></p>'
            )
            continue

        if line.startswith("- "):
            if in_ordered_list:
                parts.append("</ol>")
                in_ordered_list = False
            if not in_unordered_list:
                parts.append("<ul>")
                in_unordered_list = True
            parts.append(f"<li>{_render_inline(line[2:].strip())}</li>")
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(line.strip())
        if ordered_match:
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            if not in_ordered_list:
                parts.append("<ol>")
                in_ordered_list = True
            parts.append(f"<li>{_render_inline(ordered_match.group(1).strip())}</li>")
            continue

        if in_unordered_list:
            parts.append("</ul>")
            in_unordered_list = False
        if in_ordered_list:
            parts.append("</ol>")
            in_ordered_list = False
        parts.append(f"<p>{_render_inline(line)}</p>")

    if in_unordered_list:
        parts.append("</ul>")
    if in_ordered_list:
        parts.append("</ol>")

    return "".join(parts)


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
            "content": markdown_to_html(markdown),
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
