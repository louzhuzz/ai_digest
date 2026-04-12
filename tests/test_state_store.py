from __future__ import annotations

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

            first_seen = datetime(2026, 4, 11, 9, tzinfo=timezone.utc)
            last_seen = datetime(2026, 4, 12, 8, tzinfo=timezone.utc)
            store.upsert_items(
                [
                    {
                        "dedupe_key": "k1",
                        "source": "OpenAI News",
                        "title": "GPT-6 update",
                        "url": "https://openai.com/news/gpt-6",
                        "published_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
                        "seen_at": first_seen,
                    }
                ]
            )
            store.upsert_items(
                [
                    {
                        "dedupe_key": "k1",
                        "source": "OpenAI News",
                        "title": "GPT-6 update",
                        "url": "https://openai.com/news/gpt-6",
                        "published_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
                        "seen_at": last_seen,
                    }
                ]
            )

            rows = store.load_recent_dedupe_keys(days=7, now=datetime(2026, 4, 12, 12, tzinfo=timezone.utc))

            self.assertTrue(db_path.exists())
            self.assertIn("k1", rows)
            self.assertEqual(rows["k1"], last_seen)

    def test_load_recent_dedupe_keys_filters_old_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            store = SqliteStateStore(db_path)
            store.initialize()
            store.upsert_items(
                [
                    {
                        "dedupe_key": "fresh",
                        "source": "OpenAI News",
                        "title": "Fresh item",
                        "url": "https://example.com/fresh",
                        "published_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
                        "seen_at": datetime(2026, 4, 10, tzinfo=timezone.utc),
                    },
                    {
                        "dedupe_key": "old",
                        "source": "OpenAI News",
                        "title": "Old item",
                        "url": "https://example.com/old",
                        "published_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
                        "seen_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
                    },
                ]
            )

            rows = store.load_recent_dedupe_keys(days=7, now=datetime(2026, 4, 12, 12, tzinfo=timezone.utc))

            self.assertIn("fresh", rows)
            self.assertNotIn("old", rows)


if __name__ == "__main__":
    unittest.main()
