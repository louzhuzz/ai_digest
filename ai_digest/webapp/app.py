# ai_digest/webapp/app.py — 简化版 web 工作台
#
# 注意：生成流程由 Sisyphus（在 IDE 中）通过 tool_run 工具脚本完成。
# webapp 只负责预览、编辑和发布已生成的草稿。

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..defaults import build_default_publisher
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
    publisher_factory: Callable[[AppSettings], Any] = build_default_publisher,
    settings_loader: Callable[[], AppSettings] = load_settings,
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

    @app.get("/api/draft")
    def draft_info() -> dict[str, Any]:
        """返回当前草稿信息。"""
        md = storage.read_markdown()
        return {
            "has_draft": bool(md.strip()),
            "chars": len(md.strip()),
            "title": _extract_title(md) if md.strip() else "",
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

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8010, log_level="info")
