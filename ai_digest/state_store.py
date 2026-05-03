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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dedupe_history (
                    dedupe_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    content_hash TEXT DEFAULT '0',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simhash_buckets (
                    bucket_key TEXT PRIMARY KEY,
                    dedupe_key TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_simhash_bucket ON simhash_buckets(bucket_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dedupe_last_seen ON dedupe_history(last_seen_at)")

            # Migration: add content_hash column if missing (old schema didn't have it)
            try:
                conn.execute("ALTER TABLE dedupe_history ADD COLUMN content_hash TEXT DEFAULT '0'")
            except sqlite3.OperationalError:
                pass  # column already exists
            try:
                conn.execute("ALTER TABLE simhash_buckets ADD COLUMN bucket_key TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

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

    def load_recent_simhash_buckets(self, days: int, now: datetime) -> dict[int, list[dict]]:
        """
        加载最近 N 天的 simhash bucket 条目。

        bucket_key = content_hash // 2^(64-N_BUCKETS)
        同 bucket 内的 content_hash 可能相似（hamming ≤ 2^(64-N_BUCKETS+1)）。

        N_BUCKETS = 58 → 每个 bucket 覆盖 2^6 = 64 的 hamming 距离范围。
        """
        cutoff = _from_utc_iso(_to_utc_iso(now - timedelta(days=days)))
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT bucket_key, dedupe_key, content_hash, title, source, published_at, last_seen_at
                FROM simhash_buckets
                WHERE last_seen_at >= ?
                """,
                (cutoff,),
            ).fetchall()

        result: dict[int, list[dict]] = {}
        for row in rows:
            bucket_key_str, dedupe_key, content_hash_str, title, source, published_at, last_seen_at = row
            entry = {
                "dedupe_key": dedupe_key,
                "content_hash": int(content_hash_str) if content_hash_str else 0,
                "title": title,
                "source": source,
                "published_at": _from_utc_iso(published_at),
                "last_seen_at": _from_utc_iso(last_seen_at),
            }
            result.setdefault(int(bucket_key_str), []).append(entry)
        return result

    def upsert_items(self, items: Iterable[Mapping[str, object]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for item in items:
                dedupe_key = str(item["dedupe_key"])
                source = str(item["source"])
                title = str(item["title"])
                url = str(item["url"])
                published_at = item["published_at"]
                seen_at = item["seen_at"]
                content_hash = str(int(item.get("content_hash", 0)))
                if not isinstance(published_at, datetime):
                    raise TypeError("published_at must be a datetime")
                if not isinstance(seen_at, datetime):
                    raise TypeError("seen_at must be a datetime")
                conn.execute(
                    """
                    INSERT INTO dedupe_history
                    (dedupe_key, source, title, url, published_at, content_hash, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dedupe_key) DO UPDATE SET
                        source=excluded.source,
                        title=excluded.title,
                        url=excluded.url,
                        published_at=excluded.published_at,
                        content_hash=excluded.content_hash,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        dedupe_key,
                        source,
                        title,
                        url,
                        _to_utc_iso(published_at),
                        content_hash,
                        _to_utc_iso(seen_at),
                        _to_utc_iso(seen_at),
                    ),
                )

    def upsert_simhash_buckets(
        self,
        items: Iterable[Mapping[str, object]],
        n_buckets: int = 58,
    ) -> None:
        """
        将 items 的 content_hash 写入 simhash_buckets 表。

        64-bit fingerprint 分为高 N_BUCKETS 位作为 bucket_key（存为字符串），
        bucket 内再用完整 content_hash 做精确匹配 + hamming 比较。
        """
        with sqlite3.connect(self.db_path) as conn:
            for item in items:
                content_hash = int(item.get("content_hash", 0))
                if content_hash == 0:
                    continue
                # 取高 n_buckets 位作为 bucket_key（存为字符串以避免 SQLite INTEGER 溢出）
                bucket_key = str(content_hash >> (64 - n_buckets))
                conn.execute(
                    """
                    INSERT INTO simhash_buckets
                    (bucket_key, dedupe_key, content_hash, title, source, published_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bucket_key) DO UPDATE SET
                        dedupe_key=excluded.dedupe_key,
                        content_hash=excluded.content_hash,
                        title=excluded.title,
                        source=excluded.source,
                        published_at=excluded.published_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        bucket_key,
                        str(item["dedupe_key"]),
                        str(content_hash),
                        str(item["title"]),
                        str(item["source"]),
                        _to_utc_iso(item["published_at"]),
                        _to_utc_iso(item["seen_at"]),
                    ),
                )
