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

    def _upload_permanent_image(self, image_path: str) -> str:
        """
        上传单张图片为永久素材，返回 media_id。

        使用 material/add_material 接口，type=image。
        """
        if not image_path:
            raise RuntimeError("Empty image path")
        
        # 读取图片文件
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        if not image_bytes:
            raise RuntimeError(f"Empty image file: {image_path}")
        
        # 根据文件扩展名确定 MIME 类型
        ext = image_path.lower().rsplit(".", 1)[-1] if "." in image_path else "jpeg"
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "bmp": "image/bmp",
        }
        content_type = mime_map.get(ext, "image/jpeg")
        filename = f"image.{ext}"
        
        # 构建 multipart/form-data 请求体
        boundary = f"----OpenClaw{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
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
            raise RuntimeError(f"WeChat image upload request failed: {exc}") from exc
        
        if decoded.get("errcode"):
            errmsg = decoded.get("errmsg", "unknown WeChat API error")
            raise RuntimeError(f"WeChat image upload failed: {errmsg}")
        
        media_id = str(decoded.get("media_id", ""))
        if not media_id:
            raise RuntimeError(f"WeChat image upload failed: {decoded}")
        return media_id

    def _build_newspic_payload(
        self,
        title: str,
        image_media_ids: list[str],
        digest: str = "",
        content: str = "",
    ) -> dict[str, Any]:
        """
        构建 newspic 类型的草稿 payload。

        参考微信公众号贴图 API：
        - article_type: "newspic"
        - image_info.image_list: 图片 media_id 列表（最多 20 张）
        - content: 纯文本（不支持 HTML）
        """
        article = {
            "title": title,
            "author": "",
            "digest": digest or title,
            "content": content,
            "article_type": "newspic",
            "image_info": {
                "image_list": [{"image_media_id": mid} for mid in image_media_ids]
            },
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        return {"articles": [article]}

    def publish_newspic(
        self,
        image_paths: list[str],
        title: str = "AI 每日新闻速递",
        digest: str = "",
        content: str = "",
    ) -> str:
        """
        发布贴图（newspic）类型的公众号文章。

        Args:
            image_paths: 图片文件路径列表（最多 20 张）
            title: 文章标题
            digest: 摘要（可选）
            content: 正文纯文本（可选，贴图正文不支持 HTML）

        Returns:
            草稿 media_id
        """
        # 验证图片数量
        if len(image_paths) > 20:
            raise ValueError(f"Too many images: {len(image_paths)} (max 20)")
        
        # dry_run 模式：不实际上传，不调用 draft/add
        if self.dry_run or not self.access_token:
            # 构建虚拟 media_id 列表用于 payload 预览
            fake_media_ids = [f"fake_media_{i}" for i in range(len(image_paths))]
            payload = self._build_newspic_payload(
                title=title,
                image_media_ids=fake_media_ids,
                digest=digest,
                content=content,
            )
            self.last_payload = payload
            return ""
        
        # 实际上传图片为永久素材
        image_media_ids = []
        for path in image_paths:
            media_id = self._upload_permanent_image(path)
            image_media_ids.append(media_id)
        
        # 构建 payload
        payload = self._build_newspic_payload(
            title=title,
            image_media_ids=image_media_ids,
            digest=digest,
            content=content,
        )
        self.last_payload = payload
        
        # 调用 draft/add 接口创建草稿
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
