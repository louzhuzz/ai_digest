from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .cluster_tagger import ClusterTagger
from .composition import DigestComposer
from .dedupe import RecentDedupeFilter
from .article_linter import ArticleLinter
from .event_clusterer import EventClusterer
from .models import DigestItem, EventCluster
from .ranking import ItemRanker
from .section_picker import SectionPicker
from .summarizer import DigestPayloadBuilder, RuleBasedSummarizer


@dataclass
class DigestRunResult:
    status: str
    reason: str | None
    items_count: int
    publisher_draft_id: str | None
    markdown: str | None
    items: list[DigestItem]
    clusters: list[EventCluster] | None = None


class DigestPipeline:
    def __init__(
        self,
        collector: Any,
        publisher: Any | None = None,
        writer: Any | None = None,
        outline_generator: Any | None = None,
        *,
        deduper: RecentDedupeFilter | None = None,
        ranker: ItemRanker | None = None,
        composer: DigestComposer | None = None,
        section_picker: SectionPicker | None = None,
        article_linter: ArticleLinter | None = None,
        cluster_tagger: ClusterTagger | None = None,
        dry_run: bool = True,
        min_items: int = 3,
    ) -> None:
        self.collector = collector
        self.publisher = publisher
        self.writer = writer
        self.outline_generator = outline_generator
        self.deduper = deduper or RecentDedupeFilter()
        self.ranker = ranker or ItemRanker()
        self.clusterer = EventClusterer()
        self.summarizer = RuleBasedSummarizer()
        self.payload_builder = DigestPayloadBuilder(clusterer=self.clusterer)
        self.composer = composer or DigestComposer()
        self.section_picker = section_picker or SectionPicker()
        self.article_linter = article_linter or ArticleLinter()
        self.cluster_tagger = cluster_tagger
        self.dry_run = dry_run
        self.min_items = min_items
        self._clusters: list[EventCluster] | None = None

    def run(self, now: datetime | None = None) -> DigestRunResult:
        current_time = now or datetime.now(timezone.utc)
        collected = list(self.collector.collect())
        deduped = self.deduper.filter(collected, now=current_time)
        ranked = self.ranker.rank(deduped, now=current_time)
        summarized = self.summarizer.summarize(ranked)

        if len(summarized) < self.min_items:
            return DigestRunResult(
                status="skipped",
                reason="候选池不足",
                items_count=len(summarized),
                publisher_draft_id=None,
                markdown=None,
                items=summarized,
            )

        quota_items = self.section_picker.apply_source_quota(summarized)
        if len(quota_items) < self.min_items:
            return DigestRunResult(
                status="skipped",
                reason="候选池配额后不足",
                items_count=len(quota_items),
                publisher_draft_id=None,
                markdown=None,
                items=quota_items,
            )

        self._clusters = self.clusterer.cluster(quota_items)
        if self.cluster_tagger is not None:
            self._clusters = self.cluster_tagger.tag_clusters(self._clusters)
        payload = self.payload_builder.build(quota_items, date=current_time.date().isoformat())

        if not self.dry_run and self.writer is None:
            return DigestRunResult(
                status="failed",
                reason="writer is required for publish mode",
                items_count=len(quota_items),
                publisher_draft_id=None,
                markdown=None,
                items=quota_items,
                clusters=self._clusters,
            )

        if self.writer is not None and not self.dry_run:
            briefing_selection = self.section_picker.pick_briefing(quota_items)
            article_input = self.payload_builder.build_article_input(
                quota_items,
                date=str(payload["date"]),
                briefing_selection=briefing_selection,
            )
            outline = None
            if self.outline_generator is not None:
                outline = self.outline_generator.generate(article_input)
            if outline is not None and hasattr(self.writer, "render"):
                markdown = self.writer.render(outline, article_input)
            else:
                markdown = self.writer.write(article_input)
            try:
                self.article_linter.lint(markdown)
            except Exception as exc:
                return DigestRunResult(
                    status="failed",
                    reason=f"Article lint failed: {exc}",
                    items_count=len(quota_items),
                    publisher_draft_id=None,
                    markdown=None,
                    items=quota_items,
                    clusters=self._clusters,
                )
        else:
            markdown = self.composer.compose(quota_items, date=str(payload["date"]))

        draft_id = None
        if not self.dry_run and self.publisher is not None:
            draft_id = self.publisher.publish(markdown)
        try:
            self.deduper.persist(quota_items, now=current_time)
        except Exception as exc:
            return DigestRunResult(
                status="failed",
                reason=f"Persist failed: {exc}",
                items_count=len(quota_items),
                publisher_draft_id=draft_id,
                markdown=markdown,
                items=quota_items,
                clusters=self._clusters,
            )

        return DigestRunResult(
            status="published" if draft_id else "composed",
            reason=None,
            items_count=len(quota_items),
            publisher_draft_id=draft_id,
            markdown=markdown,
            items=quota_items,
            clusters=self._clusters,
        )
