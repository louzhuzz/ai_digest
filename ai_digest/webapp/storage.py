from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DraftStorage:
    root: Path

    def _ensure_dir(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _md_path(self) -> Path:
        return self.root / "last_draft.md"

    def _html_path(self) -> Path:
        return self.root / "last_draft.html"

    def _history_path(self) -> Path:
        return self.root / "run_history.jsonl"

    def write_markdown(self, markdown: str) -> None:
        self._ensure_dir()
        self._md_path().write_text(markdown, encoding="utf-8")

    def write_html(self, html: str) -> None:
        self._ensure_dir()
        self._html_path().write_text(html, encoding="utf-8")

    def read_markdown(self) -> str:
        path = self._md_path()
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def read_html(self) -> str:
        path = self._html_path()
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def append_history(self, record: dict[str, Any]) -> None:
        self._ensure_dir()
        record = dict(record)
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with self._history_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_history(self, limit: int = 20) -> list[dict[str, Any]]:
        path = self._history_path()
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        items = [json.loads(line) for line in lines if line.strip()]
        return items[-limit:]
