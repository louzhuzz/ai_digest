from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import DigestItem

NEWS_TOOL_CATEGORIES = {"news", "tool"}
PROJECT_CATEGORIES = {"github", "project"}
BRIEFING_CATEGORIES = NEWS_TOOL_CATEGORIES | PROJECT_CATEGORIES


@dataclass(frozen=True)
class DigestSections:
    top_items: list[DigestItem]
    github_items: list[DigestItem]
    progress_items: list[DigestItem]


@dataclass(frozen=True)
class BriefingSelection:
    lead_items: list[DigestItem]
    secondary_items: list[DigestItem]
    briefing_angle: str


class SectionPicker:
    def __init__(
        self,
        *,
        top_limit: int = 3,
        github_limit: int = 3,
        progress_limit: int = 5,
        per_source_limit: int = 2,
    ) -> None:
        self.top_limit = top_limit
        self.github_limit = github_limit
        self.progress_limit = progress_limit
        self.per_source_limit = per_source_limit

    def pick(self, items: list[DigestItem]) -> DigestSections:
        ordered = self.apply_source_quota(items)
        used: set[str] = set()
        top_items = self._pick_top_items(ordered, used)
        github_items = self._take(ordered, used, PROJECT_CATEGORIES, limit=self.github_limit)
        progress_items = self._take(ordered, used, NEWS_TOOL_CATEGORIES, limit=self.progress_limit)
        return DigestSections(
            top_items=top_items,
            github_items=github_items,
            progress_items=progress_items,
        )

    def pick_briefing(self, items: list[DigestItem]) -> BriefingSelection:
        ordered = self.apply_source_quota(items)
        used: set[str] = set()

        lead_items = self._pick_briefing_lead_items(ordered, used)
        secondary_items = self._take(ordered, used, BRIEFING_CATEGORIES, limit=3)
        briefing_angle = self._infer_briefing_angle(lead_items + secondary_items)
        return BriefingSelection(
            lead_items=lead_items,
            secondary_items=secondary_items,
            briefing_angle=briefing_angle,
        )

    def apply_source_quota(self, items: list[DigestItem]) -> list[DigestItem]:
        ordered = sorted(items, key=lambda item: item.score, reverse=True)
        source_counts: dict[str, int] = defaultdict(int)
        filtered: list[DigestItem] = []
        for item in ordered:
            source = item.source or ""
            if source_counts[source] >= self.per_source_limit:
                continue
            filtered.append(item)
            source_counts[source] += 1
        return filtered

    def _pick_top_items(self, items: list[DigestItem], used: set[str]) -> list[DigestItem]:
        selected: list[DigestItem] = []
        selected.extend(self._take(items, used, NEWS_TOOL_CATEGORIES, limit=1))
        selected.extend(self._take(items, used, PROJECT_CATEGORIES, limit=1))

        remaining = self.top_limit - len(selected)
        if remaining > 0:
            selected.extend(self._take(items, used, NEWS_TOOL_CATEGORIES, limit=remaining))
        remaining = self.top_limit - len(selected)
        if remaining > 0:
            selected.extend(self._take(items, used, PROJECT_CATEGORIES, limit=remaining))
        return selected

    def _take(
        self,
        items: list[DigestItem],
        used: set[str],
        categories: set[str],
        *,
        limit: int,
    ) -> list[DigestItem]:
        selected: list[DigestItem] = []
        for item in items:
            key = item.dedupe_key or item.url
            if item.category not in categories or key in used:
                continue
            selected.append(item)
            used.add(key)
            if len(selected) >= limit:
                break
        return selected

    def _pick_briefing_lead_items(self, items: list[DigestItem], used: set[str]) -> list[DigestItem]:
        selected: list[DigestItem] = []
        selected.extend(self._take(items, used, NEWS_TOOL_CATEGORIES, limit=1))
        remaining = 2 - len(selected)
        if remaining > 0:
            selected.extend(self._take(items, used, BRIEFING_CATEGORIES, limit=remaining))
        return selected

    def _infer_briefing_angle(self, items: list[DigestItem]) -> str:
        news_tool_count = sum(1 for item in items if item.category in NEWS_TOOL_CATEGORIES)
        github_project_count = sum(1 for item in items if item.category in PROJECT_CATEGORIES)
        if news_tool_count >= 3:
            return "今天的主线偏行业与产品更新"
        if github_project_count >= 3:
            return "今天的主线偏开源项目和工程落地"
        return "今天的主线由新闻和项目共同推动"
