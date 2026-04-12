# Publish UI (Local Web Panel) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local `localhost` web panel to generate, preview, edit, and publish WeChat drafts using the existing pipeline, with run history and lint-protected publish.

**Architecture:** Add a small FastAPI app that wraps the existing `ai_digest` pipeline. It writes and reads drafts from `data/` files and exposes REST endpoints consumed by a lightweight static HTML UI served by the same app. Publishing routes still run through `ArticleLinter`.

**Tech Stack:** FastAPI, Uvicorn, standard library (`pathlib`, `json`, `datetime`), existing `ai_digest` pipeline.

---

### Task 1: Add Local Web App Skeleton

**Files:**
- Create: `ai_digest/webapp/app.py`
- Create: `ai_digest/webapp/__init__.py`
- Create: `ai_digest/webapp/templates/index.html`
- Create: `ai_digest/webapp/static/app.js`
- Create: `ai_digest/webapp/static/styles.css`
- Test: `tests/test_webapp_api.py`

- [ ] **Step 1: Write failing test for API health**

```python
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from ai_digest.webapp.app import create_app


class WebAppApiTest(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: FAIL because `ai_digest.webapp.app` does not exist.

- [ ] **Step 3: Implement FastAPI app factory with /api/health**

```python
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: PASS.

### Task 2: Add Draft File IO Helpers

**Files:**
- Create: `ai_digest/webapp/storage.py`
- Modify: `ai_digest/webapp/app.py`
- Test: `tests/test_webapp_storage.py`

- [ ] **Step 1: Write failing tests for draft read/write**

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_webapp_storage -v
```

Expected: FAIL because `DraftStorage` does not exist.

- [ ] **Step 3: Implement DraftStorage**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DraftStorage:
    root: Path

    def _ensure_dir(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _md_path(self) -> Path:
        return self.root / "last_draft.md"

    def _html_path(self) -> Path:
        return self.root / "last_draft.html"

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_webapp_storage -v
```

Expected: PASS.

### Task 3: Implement /api/run and /api/preview

**Files:**
- Modify: `ai_digest/webapp/app.py`
- Modify: `ai_digest/webapp/storage.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Write failing test for /api/run and /api/preview**

```python
def test_run_and_preview_roundtrip(self) -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/run")
    self.assertEqual(resp.status_code, 200)

    preview = client.get("/api/preview")
    self.assertEqual(preview.status_code, 200)
    self.assertIn("markdown", preview.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: FAIL (missing endpoints).

- [ ] **Step 3: Implement endpoints using existing pipeline**

```python
from fastapi import FastAPI
from ai_digest.defaults import build_default_runner
from ai_digest.settings import load_settings
from ai_digest.publishers.wechat import markdown_to_html
from .storage import DraftStorage

def create_app() -> FastAPI:
    app = FastAPI()
    storage = DraftStorage(Path("data"))

    @app.post("/api/run")
    def run() -> dict[str, object]:
        settings = load_settings()
        runner = build_default_runner(settings=settings)
        result = runner.run()
        if result.markdown:
            storage.write_markdown(result.markdown)
            storage.write_html(markdown_to_html(result.markdown))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: PASS.

### Task 4: Implement /api/update and /api/publish

**Files:**
- Modify: `ai_digest/webapp/app.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Write failing tests for update & publish**

```python
def test_update_and_publish(self) -> None:
    app = create_app()
    client = TestClient(app)

    update = client.post("/api/update", json={"markdown": "# Title"})
    self.assertEqual(update.status_code, 200)

    publish = client.post("/api/publish")
    self.assertIn(publish.status_code, {200, 400})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: FAIL (missing endpoints).

- [ ] **Step 3: Implement endpoints**

```python
@app.post("/api/update")
def update(payload: dict[str, str]) -> dict[str, str]:
    markdown = payload.get("markdown", "")
    storage.write_markdown(markdown)
    storage.write_html(markdown_to_html(markdown))
    return {"status": "ok"}

@app.post("/api/publish")
def publish() -> dict[str, object]:
    settings = load_settings()
    if settings.dry_run:
        return {"status": "failed", "error": "WECHAT_DRY_RUN is enabled"}
    runner = build_default_runner(settings=settings)
    result = runner.run()
    return {
        "status": result.status,
        "error": result.error,
        "items_count": result.items_count,
        "draft_id": result.publisher_draft_id,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: PASS.

### Task 5: Add Simple Frontend UI

**Files:**
- Modify: `ai_digest/webapp/templates/index.html`
- Modify: `ai_digest/webapp/static/app.js`
- Modify: `ai_digest/webapp/static/styles.css`

- [ ] **Step 1: Create base HTML**

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>AI 日报发布面板</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header>
      <h1>AI 日报发布面板</h1>
      <div id="status">状态：--</div>
    </header>
    <section class="actions">
      <button id="run">生成草稿</button>
      <button id="publish">提交公众号</button>
      <button id="refresh">刷新预览</button>
    </section>
    <section class="editor">
      <textarea id="markdown"></textarea>
      <div id="preview"></div>
    </section>
    <script src="/static/app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Add JS to wire actions**

```js
async function fetchPreview() {
  const resp = await fetch('/api/preview');
  const data = await resp.json();
  document.querySelector('#markdown').value = data.markdown || '';
  document.querySelector('#preview').innerHTML = data.html || '';
}

document.querySelector('#run').onclick = async () => {
  const resp = await fetch('/api/run', { method: 'POST' });
  const data = await resp.json();
  document.querySelector('#status').textContent = `状态：${data.status}`;
  await fetchPreview();
};

document.querySelector('#publish').onclick = async () => {
  const resp = await fetch('/api/publish', { method: 'POST' });
  const data = await resp.json();
  document.querySelector('#status').textContent = `状态：${data.status}`;
};

document.querySelector('#refresh').onclick = fetchPreview;

document.querySelector('#markdown').oninput = async (evt) => {
  await fetch('/api/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown: evt.target.value })
  });
  await fetchPreview();
};

fetchPreview();
```

- [ ] **Step 3: Add minimal CSS**

```css
body { font-family: Arial, sans-serif; margin: 24px; }
.actions { margin: 16px 0; }
.editor { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
textarea { width: 100%; height: 60vh; }
#preview { border: 1px solid #ddd; padding: 12px; height: 60vh; overflow: auto; }
```

### Task 6: Wire Static Routes + Run Server

**Files:**
- Modify: `ai_digest/webapp/app.py`
- Test: `tests/test_webapp_api.py`

- [ ] **Step 1: Serve HTML + static**

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

@app.get("/")
def index() -> HTMLResponse:
    html = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
```

- [ ] **Step 2: Add test for index route**

```python
def test_index_page(self) -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    self.assertEqual(resp.status_code, 200)
    self.assertIn("AI 日报发布面板", resp.text)
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3 -m unittest tests.test_webapp_api -v
```

Expected: PASS.

### Task 7: Add History Tracking

**Files:**
- Modify: `ai_digest/webapp/storage.py`
- Modify: `ai_digest/webapp/app.py`
- Modify: `tests/test_webapp_storage.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Write failing tests for history**

```python
def test_history_roundtrip(self) -> None:
    storage = DraftStorage(Path(tmpdir))
    storage.append_history({"status": "composed"})
    history = storage.read_history()
    self.assertEqual(history[-1]["status"], "composed")
```

- [ ] **Step 2: Implement history in storage**

```python
def _history_path(self) -> Path:
    return self.root / "run_history.jsonl"

def append_history(self, record: dict[str, object]) -> None:
    self._ensure_dir()
    self._history_path().write_text(
        json.dumps(record, ensure_ascii=False) + "\n",
        encoding="utf-8",
        append=True,
    )
```

*(Use manual open(..., "a") for append since `Path.write_text` doesn't support append.)*

- [ ] **Step 3: Wire /api/history**

```python
@app.get("/api/history")
def history() -> dict[str, object]:
    return {"items": storage.read_history(limit=20)}
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest tests.test_webapp_storage tests.test_webapp_api -v
```

Expected: PASS.

### Task 8: Final Verification

- [ ] **Step 1: Full test suite**

```bash
python3 -m unittest discover -s /mnt/d/AIcodes/openclaw/tests -v
```

Expected: PASS.

- [ ] **Step 2: Manual run**

```bash
python3 -m ai_digest.webapp.app
```

Expected:
- App starts on `127.0.0.1:8010`
- Opening `/` shows the UI
- Generate/preview/edit/publish flows work
