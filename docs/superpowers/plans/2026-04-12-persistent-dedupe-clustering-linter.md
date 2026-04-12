# Persistent Dedupe, Event Clustering, and Article Linter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-run dedupe persistence, event clustering before article generation, and a publish-time article linter that blocks low-quality drafts from reaching the WeChat draft box.

**Architecture:** Add a local SQLite-backed state store to persist dedupe keys across runs, introduce a rule-based event clustering stage between source quota and LLM input assembly, and enforce a rule-based article linter after LLM generation but before WeChat publishing. Keep the first version deterministic and test-driven; do not introduce embeddings or LLM-based review in this phase.

**Tech Stack:** Python standard library (`sqlite3`, `re`, `datetime`, `pathlib`), existing `unittest` test suite, current `ai_digest` pipeline and WeChat publisher integration.

---

### Task 1: Add Persistent State Store

**Files:**
- Create: `ai_digest/state_store.py`
- Modify: `ai_digest/settings.py`
- Test: `tests/test_state_store.py`

- [ ] **Step 1: Write the failing test for state store initialization and persistence**

```python
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_digest.state_store import SqliteStateStore


class SqliteStateStoreTest(unittest.TestCase):
    def test_state_store_creates_database_and_roundtrips_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            store = SqliteStateStore(db_path)
            store.initialize()

            record = {
                "dedupe_key": "k1",
                "source": "OpenAI News",
                "title": "GPT-6 update",
                "url": "https://openai.com/news/gpt-6",
                "published_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
                "seen_at": datetime(2026, 4, 12, 8, tzinfo=timezone.utc),
            }
            store.upsert_items([record])
            rows = store.load_recent_dedupe_keys(days=7, now=datetime(2026, 4, 12, 12, tzinfo=timezone.utc))

            self.assertIn("k1", rows)
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_state_store -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `SqliteStateStore`.

- [ ] **Step 3: Write minimal SQLite-backed store**

```python
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class StoredDedupeRecord:
    dedupe_key: str
    source: str
    title: str
    url: str
    published_at: datetime
    seen_at: datetime


class SqliteStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedupe_history (
                    dedupe_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )

    def load_recent_dedupe_keys(self, days: int, now: datetime) -> dict[str, datetime]:
        cutoff = now - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT dedupe_key, last_seen_at
                FROM dedupe_history
                WHERE last_seen_at >= ?
                """,
                (cutoff.isoformat(),),
            ).fetchall()
        return {key: datetime.fromisoformat(last_seen_at) for key, last_seen_at in rows}

    def upsert_items(self, items: list[dict[str, object]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for item in items:
                seen_at = item["seen_at"]
                published_at = item["published_at"]
                conn.execute(
                    """
                    INSERT INTO dedupe_history
                    (dedupe_key, source, title, url, published_at, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dedupe_key) DO UPDATE SET
                        source=excluded.source,
                        title=excluded.title,
                        url=excluded.url,
                        published_at=excluded.published_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        item["dedupe_key"],
                        item["source"],
                        item["title"],
                        item["url"],
                        published_at.isoformat(),
                        seen_at.isoformat(),
                        seen_at.isoformat(),
                    ),
                )
```

- [ ] **Step 4: Add state store path to settings**

```python
@dataclass(frozen=True)
class AppSettings:
    wechat: WeChatCredentials | None
    ark: ArkCredentials | None
    dry_run: bool
    draft_mode: bool
    state_db_path: Path


state_db_path = Path(env.get("AI_DIGEST_STATE_DB", "data/state.db"))
...
return AppSettings(
    wechat=wechat,
    ark=ark,
    dry_run=dry_run,
    draft_mode=draft_mode,
    state_db_path=state_db_path,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_state_store tests.test_settings -v
```

Expected: PASS.

### Task 2: Connect Persistent Dedupe To The Existing Dedupe Filter

**Files:**
- Modify: `ai_digest/dedupe.py`
- Modify: `ai_digest/pipeline.py`
- Test: `tests/test_dedupe.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test for cross-run dedupe**

```python
def test_filters_items_seen_in_previous_runs(self) -> None:
    state_store = FakeStateStore({"same-key": datetime(2026, 4, 11, tzinfo=timezone.utc)})
    deduper = RecentDedupeFilter(window_days=7, state_store=state_store)
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)
    items = [
        DigestItem(
            title="A",
            url="https://example.com/a",
            source="OpenAI News",
            published_at=now,
            category="news",
            dedupe_key="same-key",
        )
    ]

    filtered = deduper.filter(items, now=now)
    self.assertEqual(filtered, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_dedupe tests.test_pipeline -v
```

Expected: FAIL because `RecentDedupeFilter` has no `state_store`.

- [ ] **Step 3: Extend dedupe filter to read and write persistent state**

```python
class RecentDedupeFilter:
    def __init__(self, window_days: int = 7, state_store: object | None = None) -> None:
        self.window = timedelta(days=window_days)
        self.state_store = state_store

    def filter(self, items: Iterable[DigestItem], now: datetime | None = None) -> list[DigestItem]:
        current_time = now or datetime.now(timezone.utc)
        seen = {}
        if self.state_store is not None:
            seen.update(self.state_store.load_recent_dedupe_keys(self.window.days, current_time))
        ...

    def persist(self, items: Iterable[DigestItem], now: datetime | None = None) -> None:
        if self.state_store is None:
            return
        current_time = now or datetime.now(timezone.utc)
        payload = []
        for item in items:
            payload.append(
                {
                    "dedupe_key": item.dedupe_key or item.url,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at,
                    "seen_at": current_time,
                }
            )
        self.state_store.upsert_items(payload)
```

- [ ] **Step 4: Persist accepted items at the end of the pipeline**

```python
quota_items = self.section_picker.apply_source_quota(summarized)
...
if self.publisher is not None:
    draft_id = self.publisher.publish(markdown)

self.deduper.persist(quota_items, now=current_time)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_dedupe tests.test_pipeline -v
```

Expected: PASS.

### Task 3: Add Event Cluster Data Model And Clusterer

**Files:**
- Create: `ai_digest/event_clusterer.py`
- Modify: `ai_digest/models.py`
- Test: `tests/test_event_clusterer.py`

- [ ] **Step 1: Write the failing test for same-event clustering**

```python
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.event_clusterer import EventClusterer
from ai_digest.models import DigestItem


class EventClustererTest(unittest.TestCase):
    def test_groups_similar_titles_from_multiple_sources(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=timezone.utc)
        items = [
            DigestItem(
                title="OpenAI 发布 GPT-6 编码更新",
                url="https://openai.com/news/gpt-6-coding",
                source="OpenAI News",
                published_at=now,
                category="news",
                score=0.9,
                dedupe_key="1",
            ),
            DigestItem(
                title="GPT-6 编码能力更新发布，OpenAI 强化开发者体验",
                url="https://www.jiqizhixin.com/pro/abc",
                source="机器之心",
                published_at=now,
                category="news",
                score=0.8,
                dedupe_key="2",
            ),
        ]
        clusters = EventClusterer().cluster(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_event_clusterer -v
```

Expected: FAIL because clusterer does not exist.

- [ ] **Step 3: Add event cluster model and normalization-based clusterer**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DigestItem


@dataclass
class EventCluster:
    cluster_id: str
    canonical_title: str
    canonical_url: str
    items: list[DigestItem]
    sources: list[str]
    score: float
    category: str


class EventClusterer:
    def cluster(self, items: list[DigestItem]) -> list[EventCluster]:
        clusters: list[EventCluster] = []
        for item in items:
            normalized = self._normalize_title(item.title)
            matched = None
            for cluster in clusters:
                if self._is_same_event(normalized, self._normalize_title(cluster.canonical_title)):
                    matched = cluster
                    break
            if matched is None:
                clusters.append(
                    EventCluster(
                        cluster_id=item.dedupe_key or item.url,
                        canonical_title=item.title,
                        canonical_url=item.url,
                        items=[item],
                        sources=[item.source],
                        score=item.score,
                        category=item.category,
                    )
                )
                continue
            matched.items.append(item)
            if item.source not in matched.sources:
                matched.sources.append(item.source)
            matched.score = max(matched.score, item.score) + 0.02
        return sorted(clusters, key=lambda cluster: cluster.score, reverse=True)

    def _normalize_title(self, title: str) -> str:
        lowered = title.lower()
        lowered = re.sub(r"[\\W_]+", " ", lowered)
        return re.sub(r"\\s+", " ", lowered).strip()

    def _is_same_event(self, left: str, right: str) -> bool:
        if left == right:
            return True
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        overlap = left_tokens & right_tokens
        return len(overlap) >= max(2, min(len(left_tokens), len(right_tokens)) // 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_event_clusterer -v
```

Expected: PASS.

### Task 4: Feed Event Clusters Into Article Input

**Files:**
- Modify: `ai_digest/summarizer.py`
- Modify: `ai_digest/pipeline.py`
- Test: `tests/test_payload.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test for clustered article input**

```python
def test_build_article_input_groups_clustered_events(self) -> None:
    cluster = EventCluster(
        cluster_id="cluster-1",
        canonical_title="OpenAI 发布 GPT-6 编码更新",
        canonical_url="https://openai.com/news/gpt-6",
        items=[item1, item2],
        sources=["OpenAI News", "机器之心"],
        score=0.95,
        category="news",
    )
    payload = DigestPayloadBuilder().build_article_input_from_clusters(
        [cluster],
        date="2026-04-12",
    )
    self.assertEqual(payload["top_event_clusters"][0]["supporting_sources"], ["OpenAI News", "机器之心"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_payload tests.test_pipeline -v
```

Expected: FAIL because clustered payload builder method is missing.

- [ ] **Step 3: Build cluster-based article input and wire it into the pipeline**

```python
def build_article_input_from_clusters(self, clusters: Iterable[EventCluster], date: str) -> dict[str, object]:
    ordered = list(clusters)
    event_clusters = [self._serialize_cluster(cluster) for cluster in ordered if cluster.category in {"news", "tool"}]
    project_clusters = [self._serialize_cluster(cluster) for cluster in ordered if cluster.category in {"github", "project"}]
    return {
        "date": date,
        "signal_pool_size": sum(len(cluster.items) for cluster in ordered),
        "top_event_clusters": event_clusters,
        "top_project_clusters": project_clusters,
    }
```

```python
clustered = self.clusterer.cluster(quota_items)
if self.dry_run:
    markdown = self.composer.compose(quota_items, date=str(payload["date"]))
else:
    article_input = self.payload_builder.build_article_input_from_clusters(clustered, date=str(payload["date"]))
    markdown = self.writer.write(article_input)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_payload tests.test_pipeline -v
```

Expected: PASS.

### Task 5: Add Publish-Time Article Linter

**Files:**
- Create: `ai_digest/article_linter.py`
- Modify: `ai_digest/pipeline.py`
- Test: `tests/test_article_linter.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests for lint failures**

```python
from __future__ import annotations

import unittest

from ai_digest.article_linter import ArticleLinter


class ArticleLinterTest(unittest.TestCase):
    def test_rejects_article_without_second_level_headings(self) -> None:
        markdown = "# 标题\n\n只有导语。"
        with self.assertRaisesRegex(RuntimeError, "missing second-level headings"):
            ArticleLinter().lint(markdown)

    def test_rejects_banned_phrases(self) -> None:
        markdown = "# 标题\n\n## 导语\n\n今日没有新增重大行业新闻。"
        with self.assertRaisesRegex(RuntimeError, "banned phrase"):
            ArticleLinter().lint(markdown)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_article_linter tests.test_pipeline -v
```

Expected: FAIL because linter does not exist.

- [ ] **Step 3: Implement rule-based linter**

```python
from __future__ import annotations

import re


class ArticleLinter:
    BANNED_PHRASES = (
        "今日没有新增重大行业新闻",
        "摘要：",
        "价值：",
    )

    def lint(self, markdown: str) -> None:
        if not markdown.startswith("# "):
            raise RuntimeError("Article lint failed: missing title")
        if len(re.findall(r"^##\\s+", markdown, flags=re.M)) < 2:
            raise RuntimeError("Article lint failed: missing second-level headings")
        if len(re.findall(r"^\\d+\\.\\s+", markdown, flags=re.M)) < 1:
            raise RuntimeError("Article lint failed: missing numbered overview")
        if len(re.findall(r"\\[[^\\]]+\\]\\([^)]+\\)", markdown)) < 3:
            raise RuntimeError("Article lint failed: missing links")
        if "```" in markdown:
            raise RuntimeError("Article lint failed: code block is not allowed")
        for phrase in self.BANNED_PHRASES:
            if phrase in markdown:
                raise RuntimeError(f"Article lint failed: banned phrase: {phrase}")
        if len(markdown.strip()) < 400:
            raise RuntimeError("Article lint failed: article too short")
```

- [ ] **Step 4: Call the linter before publishing**

```python
markdown = self.writer.write(article_input)
self.article_linter.lint(markdown)
draft_id = None
if self.publisher is not None:
    draft_id = self.publisher.publish(markdown)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_article_linter tests.test_pipeline -v
```

Expected: PASS.

### Task 6: Wire Defaults And Improve Failure Context

**Files:**
- Modify: `ai_digest/defaults.py`
- Modify: `ai_digest/runner.py`
- Test: `tests/test_defaults.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing tests for default state store wiring and lint failure reporting**

```python
def test_build_default_runner_wires_state_store_from_settings(self) -> None:
    settings = load_settings(
        {
            "AI_DIGEST_STATE_DB": "data/test-state.db",
            "WECHAT_DRY_RUN": "1",
        }
    )
    runner = build_default_runner(settings)
    self.assertIsNotNone(runner.state_store)

def test_runner_surfaces_article_lint_error(self) -> None:
    runner = DigestJobRunner(
        collector_factory=lambda: collector,
        publisher=publisher,
        writer=writer,
        dry_run=False,
    )
    outcome = runner.run(now=now)
    self.assertIn("Article lint failed", outcome.error)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_defaults tests.test_runner -v
```

Expected: FAIL because runner/defaults do not yet expose these dependencies.

- [ ] **Step 3: Inject defaults and preserve contextual errors**

```python
def build_default_runner(...):
    state_store = SqliteStateStore(settings.state_db_path)
    state_store.initialize()
    return DigestJobRunner(
        collector_factory=build_default_collector,
        publisher=...,
        writer=...,
        state_store=state_store,
        dry_run=...,
        min_items=3,
    )
```

```python
pipeline = DigestPipeline(
    collector=self.collector_factory(),
    publisher=self.publisher,
    writer=self.writer,
    state_store=self.state_store,
    dry_run=self.dry_run,
    min_items=self.min_items,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_defaults tests.test_runner -v
```

Expected: PASS.

### Task 7: Run Full Regression And Realistic Dry Run

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_payload.py`
- Modify: `tests/test_defaults_hot_pool.py`

- [ ] **Step 1: Add integrated pipeline assertions for the new order**

```python
def test_publish_mode_clusters_then_lints_before_publish(self) -> None:
    ...
    self.assertEqual(writer.calls, 1)
    self.assertEqual(publisher.calls, 1)
    self.assertIn("top_event_clusters", writer.last_input)
```

- [ ] **Step 2: Run targeted regression**

Run:

```bash
python3 -m unittest \
  tests.test_state_store \
  tests.test_dedupe \
  tests.test_event_clusterer \
  tests.test_article_linter \
  tests.test_payload \
  tests.test_pipeline \
  tests.test_defaults \
  tests.test_runner -v
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
python3 -m unittest discover -s /mnt/d/AIcodes/openclaw/tests -v
```

Expected: PASS with all tests green.

- [ ] **Step 4: Run a real dry run to inspect the pipeline path**

Run:

```bash
cd /mnt/d/AIcodes/openclaw
python3 -m ai_digest --dry-run
```

Expected:
- command exits cleanly
- no traceback
- output includes markdown content
- no publish attempt is made
