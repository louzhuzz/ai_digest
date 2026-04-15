# ai_digest/wechat_image_uploader.py
from __future__ import annotations

import json
import re
from urllib import request
from typing import Any

IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
DEFAULT_TIMEOUT = 5


class WeChatImageUploader:
    def __init__(
        self,
        access_token: str,
        upload_url: str = "https://api.weixin.qq.com/cgi-bin/media/upload",
        http_client: Any | None = None,
    ) -> None:
        self.access_token = access_token
        self.upload_url = upload_url
        self._http = http_client

    def _call_urlopen(self, req, timeout=None):
        """Call urlopen on the injected http client, or default urllib client."""
        if self._http is not None:
            return self._http.urlopen(req, timeout=timeout)
        return request.urlopen(req, timeout=timeout)

    def _download_image(self, url: str) -> bytes | None:
        try:
            req = request.Request(url)
            with self._call_urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                return resp.read()
        except Exception:
            return None

    def _upload_to_wechat(self, image_bytes: bytes) -> str | None:
        boundary = "----WeChatUpload"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="image.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()
        url = f"{self.upload_url}?access_token={self.access_token}&type=image"
        req = request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with self._call_urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data.get("url")
        except Exception:
            return None

    def upload(self, image_url: str) -> str | None:
        """下载远程图片并上传到微信，返回微信CDN URL。失败返回None。"""
        image_bytes = self._download_image(image_url)
        if image_bytes is None:
            return None
        return self._upload_to_wechat(image_bytes)

    def upload_all(self, markdown: str) -> str:
        """替换markdown中所有![](url)为微信CDN URL后返回。"""
        def replace(match):
            alt, url = match.groups()
            new_url = self.upload(url)
            if new_url:
                return f"![{alt}]({new_url})"
            return match.group(0)
        return IMAGE_PATTERN.sub(replace, markdown)
