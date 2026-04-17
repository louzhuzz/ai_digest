from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..article_linter import ArticleLinter
from ..defaults import build_default_publisher, build_default_runner
from ..publishers.wechat import markdown_to_html
from ..settings import AppSettings, load_settings
from .storage import DraftStorage


def _extract_title(markdown: str, default: str = "AI 每日新闻速递") -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip() or default
    return default


def create_app(
    *,
    storage_root: Path | None = None,
    runner_factory: Callable[[AppSettings], Any] = build_default_runner,
    publisher_factory: Callable[[AppSettings], Any] = build_default_publisher,
    settings_loader: Callable[[], AppSettings] = load_settings,
    linter_factory: Callable[[], ArticleLinter] = ArticleLinter,
) -> FastAPI:
    app = FastAPI()
    root = storage_root or Path("data")
    storage = DraftStorage(root)
    publish_lock = threading.Lock()
    recent_publish: dict[str, Any] = {"fingerprint": "", "draft_id": "", "timestamp": 0.0}

    static_dir = Path(__file__).parent / "static"
    template_path = Path(__file__).parent / "templates" / "index.html"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/run")
    def run() -> dict[str, Any]:
        settings = settings_loader()
        preview_settings = AppSettings(
            wechat=settings.wechat,
            ark=settings.ark,
            dry_run=True,
            draft_mode=False,
            state_db_path=settings.state_db_path,
            llm_enabled=settings.llm_enabled,
        )
        runner = runner_factory(preview_settings)
        result = runner.run()
        if result.markdown:
            storage.write_markdown(result.markdown)
            # 用 publisher 触发图片上传，预览所见 = 草稿箱所见
            title = _extract_title(result.markdown)
            publisher = publisher_factory(preview_settings)
            publisher.publish(result.markdown, title=title)
            html_content = publisher.last_payload["articles"][0]["content"]
            storage.write_html(html_content)
        # 写 fact-card 数据
        from collections import Counter

        clusters = result.clusters or []
        source_dist: dict[str, int] = {}
        for cluster in clusters:
            for source in cluster.sources:
                source_dist[source] = source_dist.get(source, 0) + 1
        run_data = {
            "clusters": [
                {
                    "topic_tag": cluster.topic_tag,
                    "sources": list(cluster.sources),
                    "canonical_title": cluster.canonical_title,
                }
                for cluster in clusters
            ],
            "total_items": result.items_count,
            "source_distribution": source_dist,
            "high_signal_dropped": [],
        }
        run_data_path = root / "run_data.json"
        with run_data_path.open("w", encoding="utf-8") as f:
            json.dump(run_data, f, ensure_ascii=False)
        storage.append_history(
            {
                "mode": "run",
                "status": result.status,
                "error": result.error,
                "items_count": result.items_count,
                "draft_id": result.publisher_draft_id,
            }
        )
        return {
            "status": result.status,
            "error": result.error,
            "items_count": result.items_count,
            "draft_id": result.publisher_draft_id,
        }

    @app.get("/api/preview")
    def preview() -> dict[str, str]:
        return {
            "markdown": storage.read_markdown(),
            "html": storage.read_html(),
        }

    @app.post("/api/update")
    def update(payload: dict[str, str]) -> dict[str, str]:
        markdown = payload.get("markdown", "")
        storage.write_markdown(markdown)
        storage.write_html(markdown_to_html(markdown))
        return {"status": "ok"}

    @app.post("/api/publish")
    def publish() -> dict[str, Any]:
        if not publish_lock.acquire(blocking=False):
            return {"status": "failed", "error": "publish already in progress"}
        settings = settings_loader()
        try:
            if settings.dry_run:
                return {"status": "failed", "error": "WECHAT_DRY_RUN is enabled"}
            markdown = storage.read_markdown()
            if not markdown.strip():
                return {"status": "failed", "error": "no draft markdown found"}
            linter = linter_factory()
            try:
                linter.lint(markdown)
            except Exception as exc:
                return {"status": "failed", "error": f"Article lint failed: {exc}"}

            title = _extract_title(markdown)
            fingerprint = hashlib.sha256(f"{title}\n{markdown}".encode("utf-8")).hexdigest()
            now = time.time()
            if (
                recent_publish["fingerprint"] == fingerprint
                and recent_publish["draft_id"]
                and now - float(recent_publish["timestamp"]) < 15
            ):
                return {
                    "status": "published",
                    "error": None,
                    "items_count": 0,
                    "draft_id": str(recent_publish["draft_id"]),
                }

            publisher = publisher_factory(settings)
            draft_id = publisher.publish(markdown, title=title)
            if draft_id:
                recent_publish["fingerprint"] = fingerprint
                recent_publish["draft_id"] = draft_id
                recent_publish["timestamp"] = now
            storage.append_history(
                {
                    "mode": "publish",
                    "status": "published" if draft_id else "failed",
                    "error": None if draft_id else "publish failed",
                    "items_count": 0,
                    "draft_id": draft_id,
                }
            )
            return {
                "status": "published" if draft_id else "failed",
                "error": None if draft_id else "publish failed",
                "items_count": 0,
                "draft_id": draft_id,
            }
        finally:
            publish_lock.release()

    @app.get("/api/history")
    def history() -> dict[str, Any]:
        return {"items": storage.read_history(limit=20)}

    @app.get("/api/fact-card")
    def fact_card() -> dict[str, Any]:
        run_data_path = root / "run_data.json"
        if not run_data_path.exists():
            return {"clusters": [], "total_items": 0, "source_distribution": {}, "high_signal_dropped": []}
        with run_data_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "clusters": data.get("clusters", []),
            "total_items": data.get("total_items", 0),
            "source_distribution": data.get("source_distribution", {}),
            "high_signal_dropped": data.get("high_signal_dropped", []),
        }

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8010, log_level="info")
