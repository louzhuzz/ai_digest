from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from urllib.parse import urlparse

from .models import DigestItem, EventCluster


_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "today",
    "with",
}


class EventClusterer:
    def cluster(self, items: Iterable[DigestItem]) -> list[EventCluster]:
        ordered = sorted(items, key=lambda item: item.score, reverse=True)
        clusters: list[EventCluster] = []

        for item in ordered:
            matched_index = self._find_cluster_index(clusters, item)
            if matched_index is None:
                clusters.append(
                    EventCluster(
                        canonical_title=item.title,
                        canonical_url=item.url,
                        sources=[item.source] if item.source else [],
                        items=[item],
                        score=round(min(item.score, 1.0), 4),
                        category=self._cluster_category(item.category),
                    )
                )
                continue

            current = clusters[matched_index]
            canonical_item = self._canonical_item(current)
            next_items = [*current.items, item]
            next_sources = self._merge_sources(current.sources, item.source)
            next_score = self._score_cluster(next_items, next_sources)
            next_canonical = canonical_item
            if self._is_better_canonical(item, canonical_item):
                next_canonical = item

            clusters[matched_index] = replace(
                current,
                canonical_title=next_canonical.title,
                canonical_url=next_canonical.url,
                sources=next_sources,
                items=next_items,
                score=next_score,
            )

        return sorted(clusters, key=lambda cluster: cluster.score, reverse=True)

    def _find_cluster_index(self, clusters: list[EventCluster], item: DigestItem) -> int | None:
        for index, cluster in enumerate(clusters):
            if cluster.category != self._cluster_category(item.category):
                continue
            if self._is_same_cluster(item, self._canonical_item(cluster)):
                return index
        return None

    def _is_same_cluster(self, left: DigestItem, right: DigestItem) -> bool:
        left_repo = self._github_repo_key(left.url)
        right_repo = self._github_repo_key(right.url)
        if left_repo and right_repo and left_repo == right_repo:
            return True

        left_tokens = self._title_tokens(left.title)
        right_tokens = self._title_tokens(right.title)
        if not left_tokens or not right_tokens:
            return False
        if left_tokens[0] != right_tokens[0]:
            return False

        common = len(set(left_tokens) & set(right_tokens))
        return common >= 3 and (common / min(len(set(left_tokens)), len(set(right_tokens)))) >= 0.6

    def _cluster_category(self, category: str) -> str:
        if category in {"github", "project"}:
            return "project"
        return "event"

    def _score_cluster(self, items: list[DigestItem], sources: list[str]) -> float:
        max_score = max((item.score for item in items), default=0.0)
        source_bonus = 0.05 * max(len(sources) - 1, 0)
        return round(min(max_score + source_bonus, 1.0), 4)

    def _is_better_canonical(self, candidate: DigestItem, current: DigestItem) -> bool:
        if candidate.score != current.score:
            return candidate.score > current.score
        return candidate.published_at > current.published_at

    def _merge_sources(self, sources: list[str], source: str) -> list[str]:
        if not source or source in sources:
            return list(sources)
        return [*sources, source]

    def _canonical_item(self, cluster: EventCluster) -> DigestItem:
        for item in cluster.items:
            if item.url == cluster.canonical_url and item.title == cluster.canonical_title:
                return item
        return cluster.items[0]

    def _github_repo_key(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host not in {"github.com", "www.github.com"}:
            return ""
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return ""
        return f"github.com/{parts[0].lower()}/{parts[1].lower()}"

    def _title_tokens(self, title: str) -> list[str]:
        normalized = re.sub(r"[^a-z0-9]+", " ", title.lower())
        return [
            token
            for token in normalized.split()
            if token and token not in _STOPWORDS
        ]
