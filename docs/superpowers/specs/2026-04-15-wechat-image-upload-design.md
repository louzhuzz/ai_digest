# 微信草稿箱图片上传支持 — 设计文档

## Context

微信草稿箱 `draft.add` 接口对 HTML 内容有两层过滤：
1. **外链图片被过滤**：`![](url)` 中的外部 URL 会被微信移除，图片无法显示
2. **`<a>` 标签被过滤**：正文中的链接标签会被 strip，无法保留可点击链接

本次只解决**图片外链问题**。链接问题作为已知限制记录，不在本次范围内。

## 解决方案

在 `render_wechat_html` 之前，增加一个**图片 URL 替换步骤**：
- 提取 markdown 中所有 `![](url)` 的外部 URL
- 通过微信 `cgi-bin/media/upload?type=image` 接口上传每个图片
- 微信返回素材的 CDN URL（`url` 字段）
- 用微信 CDN URL 替换 markdown 中的原始外部 URL
- 替换后的 markdown 进入 `render_wechat_html` 渲染

## 架构

### 新增组件

**`WeChatImageUploader`**

位置：`ai_digest/wechat_image_uploader.py`

```python
class WeChatImageUploader:
    def __init__(self, access_token: str, http_client: Any | None = None) -> None:
        ...

    def upload(self, image_url: str) -> str | None:
        """下载远程图片并上传到微信素材库，返回微信CDN URL。失败返回None。"""

    def upload_all(self, markdown: str) -> str:
        """替换markdown中所有![](url)为微信CDN URL后返回。"""
```

### 修改组件

**`ai_digest/publishers/wechat.py`**

在 `WeChatDraftPublisher` 中注入 `WeChatImageUploader`，在 `publish()` 或 `build_payload()` 之前调用 `upload_all()` 替换图片 URL。

### 微信 API

- 上传接口：`POST https://api.weixin.qq.com/cgi-bin/media/upload?access_token=TOKEN&type=image`
- 请求：`multipart/form-data`，字段名 `"media"`
- 响应：`{"url": "https://mmbiz.qpic.cn/...", "media_id": "..."}`
- 外部 URL 直接作为图片源下载（`urllib.request.urlopen`）

## 流程

```
markdown (含![](https://外部url/图.jpg))
    ↓
WeChatImageUploader.upload_all()
    ↓ 1. 正则提取所有 ![...](url)
    ↓ 2. 下载每个 url 的图片bytes
    ↓ 3. 调用微信 upload 接口
    ↓ 4. 用返回的 url 替换原文中的 url
    ↓
markdown (含![](https://mmbiz.qpic.cn/...))  ← 微信CDN地址
    ↓
render_wechat_html()
    ↓
HTML (<img src="https://mmbiz.qpic.cn/..."/>)  ← 微信支持
    ↓
build_payload()
    ↓
draft.add() → 草稿箱
```

## 错误处理

- 单张图片上传失败：跳过该图片，在日志中记录警告，继续处理其余图片
- 所有图片都失败：整体降级为原始 markdown（不阻塞发布）
- 图片下载超时：5 秒超时，失败则跳过

## 链接处理（已知限制，不在本次范围）

微信会 strip `<a>` 标签，正文无法保留可点击链接。当前方案：
- `content_source_url` 字段放第一个主要 URL（"阅读原文"）
- 其余 URL 以纯文本形式展示

## 验证

1. `py -3 -m unittest tests.test_wechat_renderer` 现有测试全通过
2. 新增测试：`test_renders_image_as_img_tag` 已存在
3. 新增测试：`WeChatImageUploader` 的 mock 测试（模拟 uploadimg 返回）
4. 手动测试：生成一篇含 `![](url)` 的草稿，检查草稿箱图片是否正常显示
