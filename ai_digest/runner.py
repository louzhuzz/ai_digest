from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .cluster_tagger import ClusterTagger
from .models import EventCluster
from .pipeline import DigestPipeline, DigestRunResult


@dataclass
class DigestJobOutcome:
    status: str
    error: str | None
    items_count: int
    publisher_draft_id: str | None
    markdown: str | None
    clusters: list[EventCluster] | None = None


class DigestJobRunner:
    def __init__(
        self,
        *,
        collector_factory: Callable[[], Any],
        publisher: Any | None = None,
        writer: Any | None = None,
        deduper: Any | None = None,
        dry_run: bool = True,
        alert_callback: Callable[[str], None] | None = None,
        min_items: int = 3,
        cluster_tagger: ClusterTagger | None = None,
    ) -> None:
        self.collector_factory = collector_factory
        self.publisher = publisher
        self.writer = writer
        self.deduper = deduper
        self.dry_run = dry_run
        self.alert_callback = alert_callback
        self.min_items = min_items
        self.cluster_tagger = cluster_tagger

    def run(self, now: datetime | None = None) -> DigestJobOutcome:
        try:
            pipeline = DigestPipeline(
                collector=self.collector_factory(),
                publisher=self.publisher,
                writer=self.writer,
                deduper=self.deduper,
                dry_run=self.dry_run,
                min_items=self.min_items,
                cluster_tagger=self.cluster_tagger,
            )
            result = pipeline.run(now=now)
            return self._from_pipeline_result(result)
        except Exception as exc:  # pragma: no cover - exercised in tests
            message = str(exc)
            if self.alert_callback is not None:
                self.alert_callback(message)
            return DigestJobOutcome(
                status="failed",
                error=message,
                items_count=0,
                publisher_draft_id=None,
                markdown=None,
                clusters=None,
            )

    def _from_pipeline_result(self, result: DigestRunResult) -> DigestJobOutcome:
        return DigestJobOutcome(
            status=result.status,
            error=result.reason,
            items_count=result.items_count,
            publisher_draft_id=result.publisher_draft_id,
            markdown=result.markdown,
            clusters=result.clusters,
        )
