# 微信草稿箱图片上传实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让微信草稿箱能正确显示外链图片——markdown 中 `![](url)` 的外部 URL 通过微信 uploadimg 接口替换为微信 CDN URL。

**Architecture:** 新增 `WeChatImageUploader` 类，注入到 `WeChatDraftPublisher`。`publish()` 调用时先用 uploader 替换 markdown 中的图片 URL，再走 `build_payload()` 渲染。

**Tech Stack:** Python stdlib `urllib.request`（下载图片 + 上传），微信 `media/upload` 接口，Python `re` 正则提取图片 URL。

---

## 文件结构

```
ai_digest/wechat_image_uploader.py   ← 新增：WeChatImageUploader 类
ai_digest/publishers/wechat.py       ← 修改：注入 uploader，publish() 中调用
tests/test_wechat_image_uploader.py   ← 新增：uploader 单元测试
```

---

## Task 1: WeChatImageUploader 类

**Files:**
- Create: `ai_digest/wechat_image_uploader.py`
- Test: `tests/test_wechat_image_uploader.py`

- [ ] **Step 1: 写失败测试**

```python
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
        if req.full_url == "https://api.weixin.qq.com/cgi-bin/media/upload":
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
            )
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
            )
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
        # 图片 URL 无法下载，原始 markdown 不变（降级）
        self.assertIn("https://bad.com/img.jpg", result)
        self.assertIn("正常段落", result)
```

- [ ] **Step 2: 运行测试确认失败**

```
py -3 -m unittest tests.test_wechat_image_uploader -v
```
预期：FAIL — 模块不存在

- [ ] **Step 3: 写最小实现**

```python
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

    def _download_image(self, url: str) -> bytes | None:
        try:
            req = request.Request(url)
            with (self._http or request.urlopen)(req, timeout=DEFAULT_TIMEOUT) as resp:
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
            with (self._http or request.urlopen)(req, timeout=DEFAULT_TIMEOUT) as resp:
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
```

- [ ] **Step 4: 运行测试确认通过**

```
py -3 -m unittest tests.test_wechat_image_uploader -v
```
预期：PASS

- [ ] **Step 5: 提交**

```bash
git add ai_digest/wechat_image_uploader.py tests/test_wechat_image_uploader.py
git commit -m "feat: add WeChatImageUploader for external image URL replacement"
```

---

## Task 2: 集成到 WeChatDraftPublisher

**Files:**
- Modify: `ai_digest/publishers/wechat.py` — `__init__` 增加 `image_uploader` 字段，`publish()` 中调用 `image_uploader.upload_all()`

- [ ] **Step 1: 先读现有 `publish()` 和 `__init__` 的完整代码**

确认 `__init__` 现有参数列表和 `publish()` 方法的完整实现。

- [ ] **Step 2: 修改 `__init__`，注入 image_uploader**

在 `__init__` 中添加：
```python
from ..wechat_image_uploader import WeChatImageUploader

image_uploader: WeChatImageUploader | None = None,
```
存储为 `self.image_uploader = image_uploader`

- [ ] **Step 3: 修改 `publish()` 在 `build_payload` 前调用 upload_all**

在 `markdown = self.build_payload(...)` 之前加：
```python
if self.image_uploader is not None:
    markdown = self.image_uploader.upload_all(markdown)
```

- [ ] **Step 4: 确认 dry_run 路径也走 uploader**

`publish()` 中 dry_run 分支也调用 `self.build_payload(title=title, markdown=markdown)`，uploader 逻辑在外层，`dry_run` 和非 `dry_run` 都会走到，无需特殊处理。

- [ ] **Step 5: 运行全量测试**

```
py -3 -m unittest tests.test_pipeline tests.test_wechat_renderer -v
```
预期：所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add ai_digest/publishers/wechat.py
git commit -m "feat: integrate WeChatImageUploader into WeChatDraftPublisher"
```

---

## Task 3: 端到端手动验证

- [ ] **Step 1: 重启 webapp**

```bash
taskkill //F //PID <当前webapp的PID>
py -3 -m ai_digest.webapp.app &
```

- [ ] **Step 2: 点"生成草稿"**

观察日志，确认：
1. `WeChatImageUploader.upload_all()` 被调用
2. 图片 URL 替换后 `build_payload` 正常
3. 草稿箱里图片能显示（不再被 strip）

---

## 自查清单

1. **Spec 覆盖**：图片上传、替换流程、错误处理降级均有对应任务 ✓
2. **占位符检查**：无 TBD/TODO/模糊描述 ✓
3. **类型一致性**：`upload_all()` 返回 `str`，参数 `markdown: str` ✓；`upload()` 返回 `str | None` ✓
4. **测试覆盖**：mock 测试覆盖成功/失败/多图场景 ✓
5. **提交粒度**：每个 task 独立提交，清晰可回滚 ✓
