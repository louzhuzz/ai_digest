from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request

from .outline_generator import Outline, SectionSpec


SYSTEM_PROMPT = """你在写一篇开发者专业简报，内容是 AI 热点日报短版专业简报。
目标是 800 到 1200 字，像给工程团队和产品团队看的 daily brief。
输入是一组热点候选池，不是固定栏目草稿。
你的角色是每天筛选信息的人，不是媒体编辑部。
先给当天整体判断，再只展开 2 个主重点，最后用 2 到 3 条短条补充。
不要平均照顾所有候选项，必须明确取舍和主次。
所有输出必须使用中文 Markdown。
你必须有判断和取舍，明确说明为什么值得跟。
不允许照抄输入里的英文摘要。
不允许编造输入中不存在的事实、数字、链接和结论。
新闻是主轴，项目是辅助。你可以自行决定结构和顺序，但不要把列表结构当成核心结构。
如果当天项目价值不高，可以少写项目；如果新闻更强，就把篇幅给新闻。
如果当天没有明显的大新闻，不要直接写"今日没有新增重大行业新闻"这种生硬开头。
改用更自然的转场，例如"今天更值得看的，是几条项目动态"或"今天的重点偏向开源项目"。
文章标题必须直接概括当天最重要的判断或变化。
你只能使用以下 Markdown 子集：
- # 一级标题
- ## 二级标题
- ### 三级小标题
- 普通段落
- - 无序列表
- 1. 有序列表
- **加粗**
- ![替代文字](图片URL) 图片——可引用 GitHub 项目的 avatars.githubusercontent.com 头像 URL
禁止使用以下格式：
- 代码块
- 表格
- 引用块
- HTML 标签
- 多层嵌套列表
每条内容写成短段落，不要使用"摘要：""价值："这种标签。
"""


@dataclass
class ARKArticleWriter:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 30
    transport: object | None = None

    def write(self, article_input: dict[str, object]) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
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
        opener = self.transport or request.urlopen
        try:
            with opener(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"ARK article generation failed: {exc}") from exc

        choices = decoded.get("choices") or []
        if not choices:
            raise RuntimeError(f"ARK response missing choices: {decoded}")
        markdown = str(choices[0].get("message", {}).get("content", "")).strip()
        if not markdown:
            raise RuntimeError(f"ARK response missing content: {decoded}")
        self._validate_markdown(markdown)
        return markdown

    def _validate_markdown(self, markdown: str) -> None:
        if not markdown.startswith("# "):
            raise RuntimeError("LLM output missing title")

    RENDER_SYSTEM_PROMPT = """你在写一篇开发者专业简报，内容是 AI 热点日报短版专业简报。
目标是 800 到 1200 字，像给工程团队和产品团队看的 daily brief。
输入是一组大纲和原始素材，不是自由改写稿。
你的角色是按照大纲稳定落稿，不是媒体编辑部。
先给当天整体判断，再只展开 2 个主重点，最后用 2 到 3 条短条补充。
不要平均照顾所有候选项，必须明确取舍和主次。
所有输出必须使用中文 Markdown。
你必须有判断和取舍，明确说明为什么值得跟。
不允许照抄输入里的英文摘要。
不允许编造输入中不存在的事实、数字、链接和结论。
新闻是主轴，项目是辅助。你可以自行决定结构和顺序，但不要把列表结构当成核心结构。
如果当天项目价值不高，可以少写项目；如果新闻更强，就把篇幅给新闻。
如果当天没有明显的大新闻，不要直接写"今日没有新增重大行业新闻"这种生硬开头。
改用更自然的转场，例如"今天更值得看的，是几条项目动态"或"今天的重点偏向开源项目"。
文章标题必须直接概括当天最重要的判断或变化。
你只能使用以下 Markdown 子集：
- # 一级标题
- ## 二级标题
- ### 三级小标题
- 普通段落
- - 无序列表
- 1. 有序列表
- **加粗**
- ![替代文字](图片URL) 图片——可引用 GitHub 项目的 avatars.githubusercontent.com 头像 URL
禁止使用以下格式：
- 代码块
- 表格
- 引用块
- HTML 标签
- 多层嵌套列表

要求：
- 按大纲结构写作
- key_points 提到的每条事实都要覆盖
- 控制在 800 到 1200 字
- 先给当天整体判断
- 只展开 2 个主重点
- 用 2 到 3 条短条补充
- 不要平均照顾所有候选项
- 保持中文表达，有判断和取舍
- 不允许照抄输入里的英文摘要
- 不允许编造输入中不存在的事实、数字、链接和结论
- 可以使用 ![替代文字](图片URL) 引用外部图片，GitHub 项目可引用 avatars.githubusercontent.com 头像 URL
- 最终输出为 Markdown 格式，只使用 # ## ### 段落 列表 加粗 图片
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
- 标题使用 outline.title
- 首段承接 outline.lede
- 章节标题使用各 sections[].heading
- 覆盖全部 key_points
- 不补充输入里没有的事实
- key_points 提到的每条事实都要覆盖
- 写成短版专业简报
- 最终输出为 Markdown 格式"""

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.RENDER_SYSTEM_PROMPT},
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
        self._validate_render_markdown(markdown, outline)
        return markdown

    def _validate_render_markdown(self, markdown: str, outline: Outline) -> None:
        self._validate_markdown(markdown)

        blocks = self._split_markdown_blocks(markdown)
        if not blocks:
            raise RuntimeError("render output missing title")

        title_line = blocks[0][0].strip()
        if title_line != f"# {outline.title}":
            raise RuntimeError("render output missing title")

        if outline.lede:
            if len(blocks) < 2:
                raise RuntimeError("render output missing lede")
            lede_block = "\n".join(blocks[1]).strip()
            if outline.lede not in lede_block:
                raise RuntimeError("render output missing lede")

        actual_headings = self._rendered_section_headings(blocks)
        expected_heading_set = {section.heading for section in outline.sections}
        if any(heading not in expected_heading_set for heading in actual_headings):
            raise RuntimeError("render output contains unexpected headings")

        heading_block_indexes = self._heading_block_indexes(blocks)
        section_block_ranges = self._section_block_ranges(blocks, outline, heading_block_indexes)
        for section, start, end in section_block_ranges:
            section_lines = blocks[start]
            if not any(
                line.strip() == f"## {section.heading}" or line.strip() == f"### {section.heading}"
                for line in section_lines
            ):
                raise RuntimeError(f"render output missing heading: {section.heading}")

            inline_section_lines = [
                line
                for line in section_lines
                if line.strip() != f"## {section.heading}" and line.strip() != f"### {section.heading}"
            ]
            section_text_parts = []
            if inline_section_lines:
                section_text_parts.append("\n".join(inline_section_lines))
            section_text_parts.extend("\n".join(blocks[i]) for i in range(start + 1, end))
            section_text = "\n\n".join(section_text_parts)
            for key_point in section.key_points:
                if key_point not in section_text:
                    raise RuntimeError(f"render output missing key point: {key_point}")

    def _split_markdown_blocks(self, markdown: str) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in markdown.splitlines():
            heading = self._extract_heading_text(line)
            if heading is not None and current:
                blocks.append(current)
                current = [line]
            elif line.strip():
                current.append(line)
            elif current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)
        return blocks

    def _heading_block_indexes(self, blocks: list[list[str]]) -> list[int]:
        indexes: list[int] = []
        for index, block in enumerate(blocks):
            if any(
                line.strip().startswith("## ") or line.strip().startswith("### ")
                for line in block
            ):
                indexes.append(index)
        return indexes

    def _section_block_ranges(
        self, blocks: list[list[str]], outline: Outline, heading_block_indexes: list[int]
    ) -> list[tuple[SectionSpec, int, int]]:
        heading_to_index: dict[str, int] = {}
        for index, block in enumerate(blocks):
            for line in block:
                heading = self._extract_heading_text(line)
                if heading is not None:
                    heading_to_index.setdefault(heading, index)

        ranges: list[tuple[SectionSpec, int, int]] = []
        last_block_index = -1
        for section in outline.sections:
            block_index = heading_to_index.get(section.heading)
            if block_index is None:
                raise RuntimeError(f"render output missing heading: {section.heading}")
            if block_index <= last_block_index:
                raise RuntimeError("render output breaks section order")
            next_heading_index = len(blocks)
            for heading_index in heading_block_indexes:
                if heading_index > block_index:
                    next_heading_index = heading_index
                    break
            ranges.append((section, block_index, next_heading_index))
            last_block_index = block_index
        return ranges

    def _rendered_section_headings(self, blocks: list[list[str]]) -> list[str]:
        headings: list[str] = []
        for block in blocks:
            for line in block:
                heading = self._extract_heading_text(line)
                if heading is not None:
                    headings.append(heading)
                    break
        return headings

    def _extract_heading_text(self, line: str) -> str | None:
        stripped = line.strip()
        if stripped.startswith("### "):
            return stripped[4:]
        if stripped.startswith("## "):
            return stripped[3:]
        return None
