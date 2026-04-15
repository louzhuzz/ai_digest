# tests/test_wechat_image_uploader.py
from __future__ import annotations

import unittest
from ai_digest.wechat_image_uploader import WeChatImageUploader


class MockResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeHttpClient:
    def __init__(self, upload_response: dict, download_responses: list[bytes]):
        self._upload_response = upload_response
        self._download_responses = download_responses
        self._download_idx = 0

    def urlopen(self, req, timeout=None):
        if req.full_url.startswith("https://api.weixin.qq.com"):
            import json

            return MockResponse(json.dumps(self._upload_response).encode())
        else:
            data = self._download_responses[self._download_idx]
            self._download_idx += 1
            return MockResponse(data)


class WeChatImageUploaderTest(unittest.TestCase):
    def test_upload_replaces_external_url(self):
        uploader = WeChatImageUploader(
            access_token="fake_token",
            http_client=FakeHttpClient(
                upload_response={"url": "https://mmbiz.qpic.cn/mmbiz/xxx/0"},
                download_responses=[b"\x89PNG\r\n\x1a\n"],
            ),
        )
        md = "这是图片：![](https://example.com/photo.jpg) 结束"
        result = uploader.upload_all(md)
        self.assertEqual(result, "这是图片：![](https://mmbiz.qpic.cn/mmbiz/xxx/0) 结束")

    def test_multiple_images_all_replaced(self):
        uploader = WeChatImageUploader(
            access_token="fake_token",
            http_client=FakeHttpClient(
                upload_response={"url": "https://mmbiz.qpic.cn/mmbiz/yyy/0"},
                download_responses=[b"\x89PNG", b"\x89PNG"],
            ),
        )
        md = "![](https://a.com/1.jpg)\n![](https://b.com/2.jpg)"
        result = uploader.upload_all(md)
        self.assertIn("https://mmbiz.qpic.cn/mmbiz/yyy/0", result)
        self.assertNotIn("https://a.com/1.jpg", result)
        self.assertNotIn("https://b.com/2.jpg", result)

    def test_download_failure_skips_image(self):
        class FailClient:
            def urlopen(self, req, timeout=None):
                if req.full_url.startswith("https://api.weixin.qq.com"):
                    import json

                    return MockResponse(json.dumps({"url": "https://mmbiz.qpic.cn/ok"}).encode())
                raise RuntimeError("download failed")

        uploader = WeChatImageUploader(access_token="fake", http_client=FailClient())
        md = "正常段落\n![](https://bad.com/img.jpg)\n下一段"
        result = uploader.upload_all(md)
        # 图片URL无法下载，原始markdown不变（降级）
        self.assertIn("https://bad.com/img.jpg", result)
        self.assertIn("正常段落", result)

    def test_no_images_unchanged(self):
        uploader = WeChatImageUploader(access_token="fake_token")
        md = "# 标题\n这是一段正文，没有图片。"
        result = uploader.upload_all(md)
        self.assertEqual(result, md)
