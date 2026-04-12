from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from typing import Iterable

from .event_clusterer import EventClusterer
from .models import DigestItem, EventCluster


class RuleBasedSummarizer:
    def summarize(self, items: Iterable[DigestItem]) -> list[DigestItem]:
        return [self._enrich(item) for item in items]

    def _enrich(self, item: DigestItem) -> DigestItem:
        summary = item.summary or self._build_summary(item)
        why_it_matters = item.why_it_matters or self._build_why_it_matters(item)
        return replace(item, summary=summary, why_it_matters=why_it_matters)

    def _build_summary(self, item: DigestItem) -> str:
        description = item.metadata.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
        return item.title

    def _build_why_it_matters(self, item: DigestItem) -> str:
        if item.category in {"github", "project"}:
            stars_growth = item.metadata.get("stars_growth", 0)
            return f"GitHub 热门项目动态，近期热度上升，适合开发者关注后续落地。当前新增热度指标：{stars_growth}。"
        if item.category in {"news", "tool"}:
            return f"这条动态来自 {item.source}，对开发者工具链、模型使用方式或行业方向有直接参考价值。"
        return f"这条内容来自 {item.source}，值得继续关注。"


class DigestPayloadBuilder:
    def __init__(self, clusterer: EventClusterer | None = None) -> None:
        self.clusterer = clusterer or EventClusterer()

    def build(self, items: Iterable[DigestItem], date: str) -> dict[str, object]:
        return {
            "date": date,
            "items": [self._serialize_item(item) for item in items],
        }

    def build_article_input(
        self,
        items: Iterable[DigestItem],
        date: str,
        *,
        clusters: list[EventCluster] | None = None,
    ) -> dict[str, object]:
        ordered = list(items)
        grouped = clusters or self.clusterer.cluster(ordered)
        top_event_clusters = [self._serialize_cluster(cluster) for cluster in grouped if cluster.category == "event"]
        top_project_clusters = [self._serialize_cluster(cluster) for cluster in grouped if cluster.category == "project"]
        return {
            "date": date,
            "signal_pool_size": len(ordered),
            "top_event_clusters": top_event_clusters,
            "top_project_clusters": top_project_clusters,
        }

    def _serialize_item(self, item: DigestItem) -> dict[str, object]:
        payload = asdict(item)
        published_at = payload.get("published_at")
        if isinstance(published_at, datetime):
            payload["published_at"] = published_at.isoformat()
        summary = str(payload.get("summary") or payload.get("metadata", {}).get("description") or "")
        payload["summary"] = summary
        if len(summary) > 400:
            payload["summary"] = summary[:397] + "..."
        return payload

    def _serialize_cluster(self, cluster: EventCluster) -> dict[str, object]:
        return {
            "canonical_title": cluster.canonical_title,
            "canonical_url": cluster.canonical_url,
            "sources": list(cluster.sources),
            "score": cluster.score,
            "category": cluster.category,
            "items": [self._serialize_item(item) for item in cluster.items],
        }
