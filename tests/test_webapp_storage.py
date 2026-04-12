from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_digest.webapp.storage import DraftStorage


class DraftStorageTest(unittest.TestCase):
    def test_roundtrip_draft_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DraftStorage(Path(tmpdir))
            storage.write_markdown("# Title\n\nBody")
            storage.write_html("<h1>Title</h1>")

            md = storage.read_markdown()
            html = storage.read_html()

        self.assertEqual(md, "# Title\n\nBody")
        self.assertEqual(html, "<h1>Title</h1>")

    def test_history_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DraftStorage(Path(tmpdir))
            storage.append_history({"status": "composed"})
            history = storage.read_history()

        self.assertEqual(history[-1]["status"], "composed")


if __name__ == "__main__":
    unittest.main()
