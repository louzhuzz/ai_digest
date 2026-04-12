from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

if TestClient is not None:
    from ai_digest.webapp.app import create_app


class FakeResult:
    def __init__(self) -> None:
        self.status = "composed"
        self.error = None
        self.items_count = 3
        self.publisher_draft_id = None
        self.markdown = "# AI 每日新闻速递\n\n## 今日重点\n\nA"


class FakeRunner:
    def run(self) -> FakeResult:
        return FakeResult()


class FakePublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, markdown: str, title: str = "AI 每日新闻速递") -> str:
        self.calls.append((markdown, title))
        return "draft-xyz"


class FakeSettings:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run


@unittest.skipIf(TestClient is None, "fastapi not installed")
class WebAppApiTest(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_index_page(self) -> None:
        app = create_app()
        client = TestClient(app)
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("码途日志", resp.text)
        self.assertIn("issue-deck", resp.text)
        self.assertIn("workspace-grid", resp.text)
        self.assertIn("history-panel", resp.text)

    def test_run_and_preview_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app(
                storage_root=Path(tmpdir),
                runner_factory=lambda settings: FakeRunner(),
            )
            client = TestClient(app)
            resp = client.post("/api/run")
            self.assertEqual(resp.status_code, 200)

            preview = client.get("/api/preview")
            self.assertEqual(preview.status_code, 200)
            self.assertIn("markdown", preview.json())

    def test_update_and_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = FakePublisher()
            app = create_app(
                storage_root=Path(tmpdir),
                settings_loader=lambda: FakeSettings(dry_run=False),
                publisher_factory=lambda settings: publisher,
                linter_factory=lambda: type("Linter", (), {"lint": lambda self, md: None})(),
            )
            client = TestClient(app)
            update = client.post("/api/update", json={"markdown": "# Title\n\n## A\n\n1. x\n\n## B\n\n[link](https://example.com/a)\n[link](https://example.com/b)\n[link](https://example.com/c)\n"})
            self.assertEqual(update.status_code, 200)

            publish = client.post("/api/publish")
            self.assertEqual(publish.status_code, 200)
            self.assertEqual(publish.json()["status"], "published")
            self.assertEqual(publisher.calls[0][1], "Title")


if __name__ == "__main__":
    unittest.main()
