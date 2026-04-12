from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _from_utc_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
        cutoff = _to_utc_iso(now - timedelta(days=days))
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT dedupe_key, last_seen_at
                FROM dedupe_history
                WHERE last_seen_at >= ?
                """,
                (cutoff,),
            ).fetchall()
        return {key: _from_utc_iso(last_seen_at) for key, last_seen_at in rows}

    def upsert_items(self, items: Iterable[Mapping[str, object]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for item in items:
                dedupe_key = str(item["dedupe_key"])
                source = str(item["source"])
                title = str(item["title"])
                url = str(item["url"])
                published_at = item["published_at"]
                seen_at = item["seen_at"]
                if not isinstance(published_at, datetime):
                    raise TypeError("published_at must be a datetime")
                if not isinstance(seen_at, datetime):
                    raise TypeError("seen_at must be a datetime")
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
                        dedupe_key,
                        source,
                        title,
                        url,
                        _to_utc_iso(published_at),
                        _to_utc_iso(seen_at),
                        _to_utc_iso(seen_at),
                    ),
                )
