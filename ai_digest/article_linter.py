from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ArticleLinter:
    min_body_chars: int = 500

    def lint(self, markdown: str) -> None:
        text = markdown.strip()
        errors: list[str] = []

        if not text.startswith("# "):
            errors.append("必须以 # 一级标题开头")

        if len(re.findall(r"(?m)^\d+\.\s+", text)) < 1:
            errors.append("至少需要 1 个编号速览列表")

        forbidden_phrases = ["今日没有新增重大行业新闻", "摘要：", "价值："]
        for phrase in forbidden_phrases:
            if phrase in text:
                errors.append(f"禁止出现：{phrase}")

        if re.search(r"(?m)^(```|~~~)", text):
            errors.append("禁止包含代码块")

        visible_length = len(re.sub(r"\s+", "", text))
        if visible_length < self.min_body_chars:
            errors.append(f"正文长度不足，至少需要 {self.min_body_chars} 个字符")

        if errors:
            raise RuntimeError("; ".join(errors))
