from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from .models import DigestItem


class DigestComposer:
    def compose(self, items: Iterable[DigestItem], date: str | None = None) -> str:
        ordered = sorted(items, key=lambda item: item.score, reverse=True)
        report_date = date or self._format_date(ordered)
        top_items = ordered[:5]
        grouped = defaultdict(list)
        for item in ordered:
            grouped[item.category].append(item)

        intro = self._build_intro(grouped)
        lines: list[str] = [
            "# AI 每日新闻速递",
            "",
            f"数据时间：{report_date}",
            "",
            intro,
            "",
            "### 先看结论",
        ]

        if top_items:
            for index, item in enumerate(top_items[:3], start=1):
                lines.extend(self._render_numbered_item(index, item))
        else:
            lines.append("1. 今日候选池不足，暂无可发布内容。")

        lines.extend(["", "## 今日重点"])
        if top_items:
            for item in top_items:
                lines.extend(self._render_bullet(item))
        else:
            lines.append("- 今日候选池不足，暂无可发布内容。")

        lines.extend(["", "## GitHub 新项目 / 热项目"])
        github_items = grouped.get("github", [])
        if github_items:
            for item in github_items[:5]:
                lines.extend(self._render_bullet(item))
        else:
            lines.append("- 暂无 GitHub 新项目入选。")

        lines.extend(["", "## AI 技术进展 / 工具更新"])
        news_items = grouped.get("news", []) + grouped.get("tool", [])
        if news_items:
            for item in news_items[:5]:
                lines.extend(self._render_bullet(item))
        else:
            lines.append("- 暂无 AI 技术进展入选。")

        return "\n".join(lines).strip() + "\n"

    def _render_bullet(self, item: DigestItem) -> list[str]:
        summary = item.summary or item.title
        why = item.why_it_matters or "值得关注。"
        return [
            f"- **[{item.title}]({item.url})**",
            f"  - **看点**：{summary}",
            f"  - **为什么值得跟**：{why}",
        ]

    def _render_numbered_item(self, index: int, item: DigestItem) -> list[str]:
        summary = item.summary or item.title
        why = item.why_it_matters or "值得关注。"
        return [
            f"{index}. **[{item.title}]({item.url})**",
            f"   - 看点：{summary}",
            f"   - 为什么值得跟：{why}",
        ]

    def _build_intro(self, grouped: defaultdict[str, list[DigestItem]]) -> str:
        news_count = len(grouped.get("news", [])) + len(grouped.get("tool", []))
        github_count = len(grouped.get("github", []))
        if news_count and github_count:
            return "今天的重点比较均衡，**新闻和项目都有看点**，先把最值得跟的几条挑出来。"
        if github_count:
            return "今天更值得看的，是**几条 AI 开源项目**，适合先看项目再看细节。"
        if news_count:
            return "今天的重点主要在**行业动态**，先看最值得跟的几条更新。"
        return "今天先看这几条最值得跟的动态。"

    def _format_date(self, items: list[DigestItem]) -> str:
        if not items:
            return date.today().isoformat()
        published = items[0].published_at
        if isinstance(published, datetime):
            return published.date().isoformat()
        return date.today().isoformat()
