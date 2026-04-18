# LLM Two-Phase + WeChat HTML Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 LLM 写稿改为"先出 Outline JSON、再渲染正文"两阶段；新建微信专用 HTML 渲染器替代现有 markdown_to_html

**Architecture:**
- LLM 两阶段：`OutlineGenerator` 调用 ARK 产出 Outline，ARKArticleWriter.render() 接收 Outline + article_input 渲染正文；pipeline 在 dry_run=False 时走两阶段，否则降级单阶段
- 微信渲染器：新建 `wechat_renderer.py`，每种 Markdown 元素走专门 WeChat 样式模板函数

**Tech Stack:** Python 3.11+, ARK API, dataclasses

---

## File Structure

```
ai_digest/
├── outline_generator.py              # 新建：OutlineGenerator 两阶段
├── llm_writer.py                    # 修改：新增 render() 方法
├── pipeline.py                      # 修改：两阶段调用
├── wechat_renderer.py               # 新建：微信专用 HTML 渲染器
├── publishers/wechat.py             # 修改：引入 wechat_renderer
```

---

## Task 7: Outline 数据结构 + OutlineGenerator

**Files:**
- Create: `ai_digest/outline_generator.py`
- Test: `tests/test_outline_generator.py`（新建）

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_outline_generator.py
from __future__ import annotations
import unittest, json
from ai_digest.outline_generator import OutlineGenerator, Outline, SectionSpec

class FakeTransport:
    def __init__(self, content: str):
        self.content = content
    def __call__(self, req, timeout=0):
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"choices": [{"message": {"content": self.content}}]}).encode()
        return R()

class OutlineGeneratorTest(unittest.TestCase):
    def test_generate_returns_outline_with_title_lede_sections(self):
        transport = FakeTransport(json.dumps({
            "title": "AI 热点日报",
            "lede": "今天有三条值得关注的动态。",
            "sections": [
                {"heading": "模型发布", "key_points": ["OpenAI 发布 GPT-5"], "source_hints": ["机器之心"]},
                {"heading": "开源项目", "key_points": ["Archon 框架更新"], "source_hints": ["GitHub"]},
            ]
        }))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is not None
        assert outline.title == "AI 热点日报"
        assert outline.lede == "今天有三条值得关注的动态。"
        assert len(outline.sections) == 2
        assert outline.sections[0].heading == "模型发布"

    def test_generate_returns_none_on_invalid_json(self):
        transport = FakeTransport("not json at all")
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None

    def test_generate_returns_none_on_missing_fields(self):
        transport = FakeTransport(json.dumps({"title": "Only Title"}))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None

    def test_generate_returns_none_on_empty_sections(self):
        transport = FakeTransport(json.dumps({"title": "T", "lede": "L", "sections": []}))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_outline_generator -v`
Expected: FAIL - module not found

- [ ] **Step 3: 创建 outline_generator.py**

```python
# ai_digest/outline_generator.py
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request


OUTLINE_SYSTEM_PROMPT = """你是 AI 热点日报编辑。请根据以下候选池，输出一份文章大纲。

要求：
- title：公众号标题，10-20 字，有吸引力
- lede：导语 2-3 句，交代今日整体基调
- sections：按话题重要性排序，每节含 heading（章节标题）、key_points（本节要写到的核心事实）、source_hints（参考来源标题，供编辑核实）

输出必须为有效 JSON，格式如下：
{"title": "...", "lede": "...", "sections": [{"heading": "...", "key_points": [...], "source_hints": [...]}]}

只输出 JSON，不要额外解释。"""


@dataclass
class SectionSpec:
    heading: str
    key_points: list[str]
    source_hints: list[str]


@dataclass
class Outline:
    title: str
    lede: str
    sections: list[SectionSpec]


class OutlineGenerator:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 30,
        transport=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or request.urlopen

    def generate(self, article_input: dict[str, object]) -> Outline | None:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(article_input, ensure_ascii=False)},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.transport(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"ARK outline generation failed: {exc}") from exc

        choices = decoded.get("choices") or []
        if not choices:
            raise RuntimeError(f"ARK response missing choices: {decoded}")
        raw = str(choices[0].get("message", {}).get("content", "")).strip()

        return self._parse_outline(raw)

    def _parse_outline(self, raw: str) -> Outline | None:
        try:
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                raw_clean = "\n".join(line for line in lines if not line.strip().startswith("```"))
            parsed = json.loads(raw_clean)
            if not isinstance(parsed, dict):
                return None
            title = parsed.get("title", "")
            lede = parsed.get("lede", "")
            sections_raw = parsed.get("sections", [])
            if not title or not lede or not isinstance(sections_raw, list) or len(sections_raw) == 0:
                return None
            sections = []
            for s in sections_raw:
                if not isinstance(s, dict):
                    continue
                heading = str(s.get("heading", ""))
                key_points = s.get("key_points", [])
                source_hints = s.get("source_hints", [])
                if heading:
                    sections.append(SectionSpec(
                        heading=heading,
                        key_points=key_points if isinstance(key_points, list) else [],
                        source_hints=source_hints if isinstance(source_hints, list) else [],
                    ))
            if not sections:
                return None
            return Outline(title=title, lede=lede, sections=sections)
        except Exception:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_outline_generator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/outline_generator.py tests/test_outline_generator.py
git commit -m "feat: add OutlineGenerator for two-phase LLM writing"
```

---

## Task 8: ARKArticleWriter.render() 方法

**Files:**
- Modify: `ai_digest/llm_writer.py`
- Test: `tests/test_llm_writer.py`（新增测试）

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_llm_writer.py 新增测试类
class ARKArticleWriterRenderTest(unittest.TestCase):
    def test_render_accepts_outline_and_article_input(self):
        transport = FakeTransport(
            body=b'{"choices":[{"message":{"content":"# AI 热点日报\\n\\n今天有三条值得关注的动态。\\n\\n## 模型发布\\n\\nOpenAI 发布 GPT-5。"}}]}',
        )
        writer = ARKArticleWriter(
            api_key="ark-key",
            base_url="https://ark.example.com/api/v3",
            model="ep-model",
            timeout_seconds=30,
            transport=transport,
        )
        outline = Outline(
            title="AI 热点日报",
            lede="今天有三条值得关注的动态。",
            sections=[
                SectionSpec(heading="模型发布", key_points=["OpenAI 发布 GPT-5"], source_hints=["机器之心"]),
            ],
        )
        markdown = writer.render(outline, {"date": "2026-04-14", "items": []})
        assert markdown.startswith("# ")
        assert "模型发布" in markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_llm_writer.ARKArticleWriterRenderTest -v`
Expected: FAIL - render() method does not exist

- [ ] **Step 3: 修改 llm_writer.py，新增 render() 方法**

在 `ARKArticleWriter` 类末尾（`_validate_markdown` 方法之后）加：

```python
RENDER_SYSTEM_PROMPT = """你是一个 AI 热点日报编辑。请根据以下大纲和原始素材，写成一篇公众号文章。

要求：
- 按大纲结构写作
- key_points 提到的每条事实都要覆盖
- 写得像公众号，有判断和取舍
- 最终输出为 Markdown 格式，只使用 # ## ### 段落 列表 加粗 链接
"""

    def render(self, outline: Outline, article_input: dict[str, object]) -> str:
        outline_json = json.dumps(
            {
                "title": outline.title,
                "lede": outline.lede,
                "sections": [
                    {
                        "heading": s.heading,
                        "key_points": s.key_points,
                        "source_hints": s.source_hints,
                    }
                    for s in outline.sections
                ],
            },
            ensure_ascii=False,
        )
        user_content = f"""大纲：
{outline_json}

原始素材：
{json.dumps(article_input, ensure_ascii=False)}

要求：
- 按大纲结构写作
- key_points 提到的每条事实都要覆盖
- 写得像公众号
- 最终输出为 Markdown 格式"""

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": RENDER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        opener = self.transport or request.urlopen
        try:
            with opener(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"ARK article render failed: {exc}") from exc

        choices = decoded.get("choices") or []
        if not choices:
            raise RuntimeError(f"ARK response missing choices: {decoded}")
        markdown = str(choices[0].get("message", {}).get("content", "")).strip()
        if not markdown:
            raise RuntimeError(f"ARK response missing content: {decoded}")
        self._validate_markdown(markdown)
        return markdown
```

注意：文件顶部需要 import `Outline` 和 `SectionSpec`：
在 `llm_writer.py` 顶部加：
```python
from .outline_generator import Outline, SectionSpec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_llm_writer.ARKArticleWriterRenderTest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/llm_writer.py tests/test_llm_writer.py
git commit -m "feat: add render() method to ARKArticleWriter for two-phase writing"
```

---

## Task 9: Pipeline 集成两阶段 LLM

**Files:**
- Modify: `ai_digest/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_pipeline.py 新增
def test_pipeline_two_phase_calls_outline_then_render(self):
    from unittest.mock import MagicMock, call
    from ai_digest.pipeline import DigestPipeline
    from ai_digest.outline_generator import OutlineGenerator, Outline, SectionSpec

    mock_collector = MagicMock()
    mock_collector.collect.return_value = [
        DigestItem(title="OpenAI GPT-5", url="https://a.com", source="A", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.9, dedupe_key="a"),
    ]

    mock_outline_gen = MagicMock(spec=OutlineGenerator)
    mock_outline_gen.generate.return_value = Outline(
        title="AI 热点日报",
        lede="今天有三条。",
        sections=[SectionSpec(heading="模型发布", key_points=["OpenAI GPT-5"], source_hints=["A"])],
    )

    mock_writer = MagicMock()
    mock_writer.render.return_value = "# AI 热点日报\n\n今天有三条。\n\n## 模型发布\n\nOpenAI GPT-5"

    # dry_run=False, 走两阶段
    pipeline = DigestPipeline(
        collector=mock_collector,
        writer=mock_writer,
        outline_generator=mock_outline_gen,
        dry_run=False,
        min_items=1,
    )
    result = pipeline.run(now=datetime(2026,4,14,tzinfo=timezone.utc))

    assert result.status == "published"
    mock_outline_gen.generate.assert_called_once()
    mock_writer.render.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline.PipelineTest.test_pipeline_two_phase_calls_outline_then_render -v`
Expected: FAIL - pipeline doesn't accept outline_generator

- [ ] **Step 3: 修改 pipeline.py**

改动一：文件顶部 import（在 `from .llm_writer import ARKArticleWriter` 附近）：
```python
from .outline_generator import OutlineGenerator, Outline, SectionSpec
```

改动二：`DigestPipeline.__init__` 签名加参数：
```python
outline_generator: OutlineGenerator | None = None,
```

改动三：`DigestPipeline.__init__` 体内加：
```python
self.outline_generator = outline_generator
```

改动四：`run()` 方法里，当 `not self.dry_run` 时（现有的 `self.writer is None` 检查附近），找到：
```python
markdown = self.writer.write(article_input)
```
在这行**之前**加两阶段逻辑：

```python
        if self.outline_generator is not None and self.writer is not None:
            outline = self.outline_generator.generate(article_input)
            if outline is not None:
                markdown = self.writer.render(outline, article_input)
            else:
                # outline 生成失败，降级单阶段
                markdown = self.writer.write(article_input)
        elif self.writer is not None:
            markdown = self.writer.write(article_input)
        else:
            markdown = self.composer.compose(quota_items, date=str(payload["date"]))
```

原来的 else 分支是报错"ARK writer is required for publish mode"，所以两阶段也走这个分支的逻辑，只是把 `self.writer.write(article_input)` 替换成了两阶段调用。

实际上看原代码：
```python
        if self.dry_run:
            markdown = self.composer.compose(quota_items, date=str(payload["date"]))
        else:
            if self.writer is None:
                return DigestRunResult(...)
            article_input = ...
            markdown = self.writer.write(article_input)
```

所以 dry_run=False 时才有两阶段。改动后：

```python
        else:
            # dry_run=False，发布模式
            if self.writer is None:
                return DigestRunResult(...)
            article_input = self.payload_builder.build_article_input(...)
            if self.outline_generator is not None:
                outline = self.outline_generator.generate(article_input)
                if outline is not None:
                    markdown = self.writer.render(outline, article_input)
                else:
                    markdown = self.writer.write(article_input)  # 降级
            else:
                markdown = self.writer.write(article_input)  # 无 outline_generator，走单阶段
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS（现有测试不受影响，因为 outline_generator 默认为 None）

- [ ] **Step 5: Commit**

```bash
git add ai_digest/pipeline.py tests/test_pipeline.py
git commit -m "feat: integrate two-phase LLM writing into pipeline"
```

---

## Task 10: WeChat HTML 渲染器

**Files:**
- Create: `ai_digest/wechat_renderer.py`
- Test: `tests/test_wechat_renderer.py`（新建）

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_wechat_renderer.py
from __future__ import annotations
import unittest
from ai_digest.wechat_renderer import render_wechat_html

class WeChatRendererTest(unittest.TestCase):
    def test_renders_h1_with_correct_style(self):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_wechat_renderer -v`
Expected: FAIL - module not found

- [ ] **Step 3: 创建 wechat_renderer.py**

```python
# ai_digest/wechat_renderer.py
from __future__ import annotations

import html
import re

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
ORDERED_LIST_PATTERN = re.compile(r"\d+\.\s+(.*)")

PARAGRAPH_STYLE = 'font-size:16px; line-height:1.8; color:#333; margin:1em 0;'
H1_STYLE = 'font-size:20px; font-weight:bold; color:#1a1a1a; margin:1.2em 0 0.6em;'
H2_STYLE = 'margin:1.4em 0 0.55em; font-size:22px; font-weight:700; line-height:1.45; color:#1f2937;'
H3_STYLE = 'margin:1em 0 0.45em; font-size:18px; font-weight:700; line-height:1.5; color:#334155;'
BLOCKQUOTE_STYLE = 'border-left:3px solid #ddd; padding-left:1em; color:#666; margin:1em 0;'
LINK_STYLE = 'color:#1a73e8; text-decoration:underline;'


def _render_inline(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in LINK_PATTERN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        label, url = match.groups()
        parts.append(f'<a href="{html.escape(url, quote=True)}" style="{LINK_STYLE}">{html.escape(label)}</a>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    rendered = "".join(parts)
    return BOLD_PATTERN.sub(lambda match: f"<strong>{html.escape(match.group(1))}</strong>", rendered)


def render_wechat_html(markdown: str) -> str:
    parts: list[str] = []
    in_unordered_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            continue

        if line.startswith("# "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[2:].strip())
            parts.append(f"<p style=\"{H1_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("## "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[3:].strip())
            parts.append(f"<p style=\"{H2_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("### "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[4:].strip())
            parts.append(f"<p style=\"{H3_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("- "):
            if not in_unordered_list:
                parts.append("<ul style=\"margin:1em 0; padding-left:1.5em;\">")
                in_unordered_list = True
            parts.append(f"<li style=\"margin-bottom:0.3em;\">{_render_inline(line[2:].strip())}</li>")
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(line.strip())
        if ordered_match:
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            # 微信不用 <ol>，用字符缩进
            parts.append(f"<p style=\"{PARAGRAPH_STYLE}\">{_render_inline(line.strip())}</p>")
            continue

        if in_unordered_list:
            parts.append("</ul>")
            in_unordered_list = False
        parts.append(f"<p style=\"{PARAGRAPH_STYLE}\">{_render_inline(line)}</p>")

    if in_unordered_list:
        parts.append("</ul>")

    return "".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_wechat_renderer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/wechat_renderer.py tests/test_wechat_renderer.py
git commit -m "feat: add WeChat-specific HTML renderer"
```

---

## Task 11: publishers/wechat.py 接入新渲染器

**Files:**
- Modify: `ai_digest/publishers/wechat.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_wechat_publisher.py 新增
def test_build_payload_uses_wechat_renderer(self):
    from ai_digest.publishers.wechat import WeChatDraftPublisher
    publisher = WeChatDraftPublisher(dry_run=True)
    publisher.build_payload(title="Test", markdown="# 标题\n\n正文")  # 验证不抛异常
    html = publisher.last_payload["articles"][0]["content"]
    # 确认用的是新渲染器（微信样式，不是 <h1>/<h2> 标签）
    assert "<h1" not in html
    assert "<h2" not in html
    assert "font-size:20px" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_wechat_publisher.WeChatPublisherTest.test_build_payload_uses_wechat_renderer -v`
Expected: FAIL - still uses old markdown_to_html

- [ ] **Step 3: 修改 publishers/wechat.py**

在文件顶部 import 区，把：
```python
from ..cover_image import generate_cover_image
```
之后加：
```python
from ..wechat_renderer import render_wechat_html
```

然后找到 `build_payload` 方法，把：
```python
"content": markdown_to_html(markdown),
```
替换为：
```python
"content": render_wechat_html(markdown),
```

同时删掉顶部不再需要的 `markdown_to_html` 函数引用（如果有地方用到的话）。检查发现 `webapp/app.py` 还在用 `from ..publishers.wechat import markdown_to_html`，所以保留原函数，不删除。

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_wechat_publisher -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/publishers/wechat.py tests/test_wechat_publisher.py
git commit -m "feat: use WeChat renderer in WeChatDraftPublisher"
```

---

## 自检清单

**Spec 覆盖检查：**
- [x] Step 3（LLM 两阶段）：Task 7 (OutlineGenerator) + Task 8 (render方法) + Task 9 (pipeline集成)
- [x] Step 4（微信渲染器）：Task 10 (wechat_renderer) + Task 11 (publisher接入)

**Placeholder 扫描：**
- 无 "TBD"、"TODO"、placeholder
- 所有代码均为完整实现

**类型一致性：**
- `Outline.title / lede / sections` 在 outline_generator.py 定义 → `ARKArticleWriter.render(outline, article_input)` 签名一致
- `SectionSpec.heading / key_points / source_hints` 全流程一致
- `DigestPipeline.outline_generator: OutlineGenerator | None` → 默认为 None，向后兼容
