# ai_digest/wechat_image_uploader.py
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request
from typing import Any

IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
DEFAULT_TIMEOUT = 5
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
MAX_CONCURRENT_UPLOADS = 4  # WeChat API rate limit


class WeChatImageUploader:
    def __init__(
        self,
        access_token: str,
        upload_url: str = "https://api.weixin.qq.com/cgi-bin/media/upload",
        http_client: Any | None = None,
        max_workers: int = MAX_CONCURRENT_UPLOADS,
    ) -> None:
        self.access_token = access_token
        self.upload_url = upload_url
        self._http = http_client
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

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

    def _upload_with_retry(self, image_bytes: bytes) -> str | None:
        """Upload with exponential backoff retry."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            result = self._upload_to_wechat(image_bytes)
            if result is not None:
                return result
            last_error = None
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
        return None

    def upload(self, image_url: str) -> str | None:
        """Download remote image and upload to WeChat CDN. Returns CDN URL or None on failure."""
        image_bytes = self._download_image(image_url)
        if image_bytes is None:
            return None
        return self._upload_with_retry(image_bytes)

    def _upload_single(self, url: str) -> tuple[str, str | None]:
        """Upload single image, return (original_url, cdn_url_or_none)."""
        cdn_url = self.upload(url)
        return (url, cdn_url)

    def upload_all(self, markdown: str) -> str:
        """Replace all ![](url) with WeChat CDN URLs using concurrent uploads."""
        matches = [(m.group(0), m.group(2)) for m in IMAGE_PATTERN.finditer(markdown)]
        if not matches:
            return markdown

        # Collect all original URLs for concurrent processing
        url_to_match = {url: match for match, url in matches}
        urls = list(url_to_match.keys())

        # Submit all uploads concurrently
        future_to_url = {
            self._executor.submit(self._upload_single, url): url
            for url in urls
        }

        # Collect results
        url_to_cdn: dict[str, str | None] = {}
        for future in as_completed(future_to_url):
            original_url, cdn_url = future.result()
            url_to_cdn[original_url] = cdn_url

        # Build result with fallback to original on failure
        def replace(match):
            alt, url = match.groups()
            cdn = url_to_cdn.get(url)
            if cdn:
                return f"![{alt}]({cdn})"
            return match.group(0)

        return IMAGE_PATTERN.sub(replace, markdown)
