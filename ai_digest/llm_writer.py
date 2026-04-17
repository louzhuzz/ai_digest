from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request

from .outline_generator import Outline, SectionSpec


SYSTEM_PROMPT = """你在写一篇面向开发者的 AI 热点日报。
输入是一组热点候选池，不是固定栏目草稿。
你的角色是每天筛选信息的人，不是媒体编辑部。
请优先写成一篇自然的公众号文章，而不是生硬的模板填空。
所有输出必须使用中文 Markdown。
你必须有判断和取舍，明确说明为什么值得跟。
不允许照抄输入里的英文摘要。
不允许编造输入中不存在的事实、数字、链接和结论。
新闻是主轴，项目是辅助。你可以自行决定结构和顺序，不必平均分配。
如果当天项目价值不高，可以少写项目；如果新闻更强，就把篇幅给新闻。
如果当天没有明显的大新闻，不要直接写"今日没有新增重大行业新闻"这种生硬开头。
改用更自然的转场，例如"今天更值得看的，是几条项目动态"或"今天的重点偏向开源项目"。
推荐结构是：导语 -> 编号速览 -> 正文展开。
如果内容组织更自然，可以不严格照这个顺序执行，但要让读者读起来顺。
全文只保留一个编号速览，不要满篇编号列表。
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

    RENDER_SYSTEM_PROMPT = """你是一个 AI 热点日报编辑。请根据以下大纲和原始素材，写成一篇公众号文章。

要求：
- 按大纲结构写作
- key_points 提到的每条事实都要覆盖
- 写得像公众号，有判断和取舍
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
- key_points 提到的每条事实都要覆盖
- 写得像公众号
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
        self._validate_markdown(markdown)
        return markdown
