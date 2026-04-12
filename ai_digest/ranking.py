from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from .models import DigestItem


class ItemRanker:
    def rank(self, items: Iterable[DigestItem], now: datetime | None = None) -> list[DigestItem]:
        current_time = now or datetime.now(timezone.utc)
        scored = [replace(item, score=self.score(item, current_time)) for item in items]
        return sorted(scored, key=lambda item: item.score, reverse=True)

    def score(self, item: DigestItem, now: datetime | None = None) -> float:
        current_time = now or datetime.now(timezone.utc)
        age_days = max((current_time - item.published_at).total_seconds() / 86400.0, 0.0)
        freshness = max(0.0, 1.0 - age_days / 7.0)
        community_heat = min(float(item.metadata.get("community_heat", 0) or 0) / 200.0, 1.0)
        source_strength = float(item.metadata.get("source_strength", 0) or 0)
        developer_relevance = float(item.metadata.get("developer_relevance", 0) or 0)

        if item.category in {"project", "github"}:
            return round(
                (0.30 * freshness)
                + (0.30 * community_heat)
                + (0.20 * source_strength)
                + (0.20 * developer_relevance),
                4,
            )

        return round(
            (0.35 * freshness)
            + (0.25 * community_heat)
            + (0.20 * source_strength)
            + (0.20 * developer_relevance),
            4,
        )
