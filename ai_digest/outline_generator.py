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