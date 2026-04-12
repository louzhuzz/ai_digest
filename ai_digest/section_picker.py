from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import DigestItem


@dataclass(frozen=True)
class DigestSections:
    top_items: list[DigestItem]
    github_items: list[DigestItem]
    progress_items: list[DigestItem]


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
        github_items = self._take(ordered, used, {"github"}, limit=self.github_limit)
        progress_items = self._take(ordered, used, {"news", "tool"}, limit=self.progress_limit)
        return DigestSections(
            top_items=top_items,
            github_items=github_items,
            progress_items=progress_items,
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
        selected.extend(self._take(items, used, {"news", "tool"}, limit=1))
        selected.extend(self._take(items, used, {"github"}, limit=1))

        remaining = self.top_limit - len(selected)
        if remaining > 0:
            selected.extend(self._take(items, used, {"news", "tool"}, limit=remaining))
        remaining = self.top_limit - len(selected)
        if remaining > 0:
            selected.extend(self._take(items, used, {"github"}, limit=remaining))
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
