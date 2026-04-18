from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

if TestClient is not None:
    from ai_digest.webapp.app import create_app
    from ai_digest.settings import AppSettings


class FakeResult:
    def __init__(self) -> None:
        self.status = "composed"
        self.error = None
        self.items_count = 3
        self.publisher_draft_id = None
        self.markdown = "# AI 每日新闻速递\n\n## 今日重点\n\nA"
        self.clusters = None


class FakeRunner:
    def run(self) -> FakeResult:
        return FakeResult()


class RecordingRunner:
    def __init__(self, settings) -> None:
        self.settings = settings

    def run(self) -> FakeResult:
        return FakeResult()


class FakePublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, markdown: str, title: str = "AI 每日新闻速递") -> str:
        self.calls.append((markdown, title))
        return "draft-xyz"

    def build_payload(self, *, title: str, markdown: str, **kwargs) -> dict:
        return {"articles": [{"content": f"<preview>{title}:{markdown}</preview>"}]}


class BlockingPublisher:
    def __init__(self) -> None:
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()

    def publish(self, markdown: str, title: str = "AI 每日新闻速递") -> str:
        self.calls.append((markdown, title))
        self.started.set()
        self.release.wait(timeout=2)
        return "draft-blocked"


class FakeSettings:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run


def _fake_publish_enabled_settings() -> AppSettings:
    return AppSettings(
        wechat=None,
        ark=None,
        dry_run=False,
        draft_mode=True,
        llm_enabled=False,
        state_db_path=Path("data/state.db"),
    )


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

    def test_run_does_not_publish_even_when_settings_are_publish_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            seen = {}

            def runner_factory(settings):
                seen["dry_run"] = settings.dry_run
                seen["draft_mode"] = settings.draft_mode
                return RecordingRunner(settings)

            app = create_app(
                storage_root=Path(tmpdir),
                runner_factory=runner_factory,
                settings_loader=_fake_publish_enabled_settings,
            )
            client = TestClient(app)

            resp = client.post("/api/run")

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(seen["dry_run"])
            self.assertFalse(seen["draft_mode"])

    def test_run_does_not_call_publisher_for_preview_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = FakePublisher()
            app = create_app(
                storage_root=Path(tmpdir),
                runner_factory=lambda settings: FakeRunner(),
                publisher_factory=lambda settings: publisher,
            )
            client = TestClient(app)

            resp = client.post("/api/run")

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(publisher.calls, [])

    def test_update_preview_uses_same_wechat_renderer_as_publish(self) -> None:
        from ai_digest.wechat_renderer import render_wechat_html

        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app(storage_root=Path(tmpdir))
            client = TestClient(app)
            markdown = "# Title\n\n## Section\n\n1. 第一条\n2. 第二条"

            update = client.post("/api/update", json={"markdown": markdown})

            self.assertEqual(update.status_code, 200)
            preview = client.get("/api/preview")
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["html"], render_wechat_html(markdown))

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

    def test_publish_rejects_concurrent_duplicate_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = BlockingPublisher()
            app = create_app(
                storage_root=Path(tmpdir),
                settings_loader=lambda: FakeSettings(dry_run=False),
                publisher_factory=lambda settings: publisher,
                linter_factory=lambda: type("Linter", (), {"lint": lambda self, md: None})(),
            )
            client = TestClient(app)
            client.post(
                "/api/update",
                json={"markdown": "# Title\n\n1. x\n\n[link](https://example.com/a)\n[link](https://example.com/b)\n[link](https://example.com/c)\n"},
            )

            responses = []

            def send_publish() -> None:
                responses.append(client.post("/api/publish"))

            first = threading.Thread(target=send_publish)
            second = threading.Thread(target=send_publish)

            first.start()
            publisher.started.wait(timeout=1)
            second.start()
            time.sleep(0.1)
            publisher.release.set()
            first.join()
            second.join()

            payloads = [resp.json() for resp in responses]
            self.assertEqual(len(publisher.calls), 1)
            self.assertEqual(sum(1 for item in payloads if item["status"] == "published"), 1)
            self.assertEqual(sum(1 for item in payloads if item["status"] == "failed"), 1)
            self.assertTrue(any("already in progress" in item["error"] for item in payloads if item["status"] == "failed"))

    def test_publish_returns_same_draft_for_immediate_duplicate_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = FakePublisher()
            app = create_app(
                storage_root=Path(tmpdir),
                settings_loader=lambda: FakeSettings(dry_run=False),
                publisher_factory=lambda settings: publisher,
                linter_factory=lambda: type("Linter", (), {"lint": lambda self, md: None})(),
            )
            client = TestClient(app)
            client.post(
                "/api/update",
                json={"markdown": "# Title\n\n1. x\n\n[link](https://example.com/a)\n[link](https://example.com/b)\n[link](https://example.com/c)\n"},
            )

            first = client.post("/api/publish")
            second = client.post("/api/publish")

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.json()["draft_id"], "draft-xyz")
            self.assertEqual(second.json()["draft_id"], "draft-xyz")
            self.assertEqual(len(publisher.calls), 1)

    def test_fact_card_returns_cluster_summary(self) -> None:
        import json
        from pathlib import Path
        from fastapi.testclient import TestClient
        from ai_digest.webapp.app import create_app

        storage_root = Path(tempfile.mkdtemp())
        app = create_app(storage_root=storage_root)
        client = TestClient(app)

        # 写入 run_data.json
        run_data = {
            "clusters": [
                {"topic_tag": "模型发布", "sources": ["机器之心", "量子位"], "canonical_title": "OpenAI GPT-5"},
                {"topic_tag": "开源项目", "sources": ["GitHub"], "canonical_title": "Archon"},
            ],
            "total_items": 5,
            "source_distribution": {"news": 3, "github": 2},
            "high_signal_dropped": [],
        }
        storage_root.joinpath("run_data.json").write_text(json.dumps(run_data), encoding="utf-8")

        response = client.get("/api/fact-card")
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data
        assert len(data["clusters"]) == 2
        assert data["clusters"][0]["topic_tag"] == "模型发布"
        assert data["total_items"] == 5
        assert data["source_distribution"]["news"] == 3


if __name__ == "__main__":
    unittest.main()
