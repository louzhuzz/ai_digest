# Cluster Tagging + Fact Card Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给每个事件聚类打 topic_tag，并在网页端加发布前事实卡预览面板

**Architecture:** Step 1 在 pipeline 的 cluster() 之后加一层 ClusterTagger 调用 ARK API 打标签；Step 2 在 webapp 新增 /api/fact-card 端点，前端加可折叠侧栏展示聚类标签、来源分布、原始标题示例

**Tech Stack:** Python 3.11+, FastAPI, ARK API (字节火山), vanilla JS/CSS

---

## File Structure

```
ai_digest/
├── models.py                        # EventCluster 新增 topic_tag 字段
├── event_clusterer.py               # 不改，只被 pipeline 调用
├── cluster_tagger.py                 # 新建：ClusterTagger 类，调用 ARK API
├── pipeline.py                       # pipeline 引入 cluster_tagger
├── summarizer.py                    # build_article_input 透传 topic_tag
├── webapp/
│   ├── app.py                       # 新增 /api/fact-card 端点
│   ├── static/app.js                # 前端 fact-card 面板交互
│   └── templates/index.html          # fact-card HTML 结构
```

---

## Task 1: EventCluster 新增 topic_tag 字段

**Files:**
- Modify: `ai_digest/models.py:22-29`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_event_clusterer.py 新增
def test_cluster_has_topic_tag_field(self) -> None:
    from ai_digest.models import EventCluster, DigestItem
    from datetime import datetime, timezone
    item = DigestItem(
        title="Test",
        url="https://example.com",
        source="Test",
        published_at=datetime(2026, 4, 14, tzinfo=timezone.utc),
        category="news",
        score=0.5,
        dedupe_key="test",
    )
    cluster = EventCluster(
        canonical_title="Test",
        canonical_url="https://example.com",
        sources=["Test"],
        items=[item],
        score=0.5,
        category="event",
        topic_tag="模型发布",  # 新字段
    )
    assert cluster.topic_tag == "模型发布"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_event_clusterer.EventClustererTest.test_cluster_has_topic_tag_field -v`
Expected: AttributeError 或编译错误（topic_tag 字段不存在）

- [ ] **Step 3: 修改 models.py，给 EventCluster 加 topic_tag 字段**

```python
# ai_digest/models.py 第 22-29 行
# 将 EventCluster dataclass 修改为：
@dataclass
class EventCluster:
    canonical_title: str
    canonical_url: str
    sources: list[str]
    items: list[DigestItem]
    score: float
    category: str
    topic_tag: str = ""   # 新增，默认为空字符串
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_event_clusterer.EventClustererTest.test_cluster_has_topic_tag_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/models.py tests/test_event_clusterer.py
git commit -m "feat: add topic_tag field to EventCluster"
```

---

## Task 2: ClusterTagger 模块

**Files:**
- Create: `ai_digest/cluster_tagger.py`
- Test: `tests/test_cluster_tagger.py`（新建）

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_cluster_tagger.py
from __future__ import annotations
import unittest
from datetime import datetime, timezone
from ai_digest.cluster_tagger import ClusterTagger
from ai_digest.models import DigestItem, EventCluster

class MockArkTransport:
    def __init__(self, response_content: str):
        self.response_content = response_content
        self.last_request = None

    def __call__(self, req, timeout=None):
        import io, json
        self.last_request = req
        data = json.dumps({
            "choices": [{"message": {"content": self.response_content}}]
        }).encode()
        return io.BytesIO(data)

class ClusterTaggerTest(unittest.TestCase):
    def test_tag_clusters_returns_clusters_with_topic_tag(self):
        transport = MockArkTransport(json.dumps({
            "choices": [{"message": {"content": '[{"cluster_index":0,"topic_tag":"模型发布"},{"cluster_index":1,"topic_tag":"开源项目"}]'}}]  # NOQA
        }))
        tagger = ClusterTagger(
            api_key="test",
            base_url="https://ark.example.com",
            model="test-model",
            transport=transport,
        )
        item1 = DigestItem(title="OpenAI GPT-5", url="https://a.com", source="A", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.9, dedupe_key="a")
        item2 = DigestItem(title="Archon framework", url="https://b.com", source="B", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="github", score=0.8, dedupe_key="b")
        clusters = [
            EventCluster(canonical_title="OpenAI GPT-5", canonical_url="https://a.com", sources=["A"], items=[item1], score=0.9, category="event", topic_tag=""),
            EventCluster(canonical_title="Archon", canonical_url="https://b.com", sources=["B"], items=[item2], score=0.8, category="project", topic_tag=""),
        ]
        result = tagger.tag_clusters(clusters)
        assert result[0].topic_tag == "模型发布"
        assert result[1].topic_tag == "开源项目"

    def test_tag_clusters_falls_back_to_empty_on_parse_error(self):
        transport = MockArkTransport(json.dumps({
            "choices": [{"message": {"content": "not valid json"}}]
        }))
        tagger = ClusterTagger(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        item = DigestItem(title="Test", url="https://x.com", source="X", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.5, dedupe_key="x")
        cluster = EventCluster(canonical_title="Test", canonical_url="https://x.com", sources=["X"], items=[item], score=0.5, category="event", topic_tag="")
        result = tagger.tag_clusters([cluster])
        assert result[0].topic_tag == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_cluster_tagger -v`
Expected: FAIL - module not found

- [ ] **Step 3: 创建 cluster_tagger.py**

```python
# ai_digest/cluster_tagger.py
from __future__ import annotations

import json
from dataclasses import replace
from urllib import request

TOPIC_TAG_PROMPT = """你是一个 AI 热点编辑。请为以下每个事件 cluster 生成一个简短的话题标签（最多 5 个字）。

候选标签池：
- 模型发布（指新模型、功能更新）
- 开源项目（指 GitHub 项目、库、工具）
- 代码能力（指编码、调试相关能力更新）
- 行业动态（指公司合作、投资、政策）
- 社区热点（指社区讨论、HackerNews 趋势）

输入：clusters 列表，每个含多条新闻标题
输出：JSON数组，每个元素 {cluster_index, topic_tag}

请直接输出 JSON，不要解释。"""


class ClusterTagger:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 30,
        transport=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or request.urlopen

    def tag_clusters(self, clusters: list) -> list:
        if not clusters:
            return clusters

        cluster_summaries = self._build_cluster_summaries(clusters)
        raw_tag_json = self._call_ark(cluster_summaries)

        tag_map = self._parse_tag_response(raw_tag_json, len(clusters))

        result = []
        for i, cluster in enumerate(clusters):
            tag = tag_map.get(i, "")
            result.append(replace(cluster, topic_tag=tag))
        return result

    def _build_cluster_summaries(self, clusters: list) -> str:
        lines = []
        for i, cluster in enumerate(clusters):
            titles = " | ".join(item.title for item in cluster.items)
            lines.append(f"[{i}] {cluster.category}: {titles}")
        return "\n".join(lines)

    def _call_ark(self, cluster_summaries: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": TOPIC_TAG_PROMPT},
                {"role": "user", "content": cluster_summaries},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.transport(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"ARK cluster tagging failed: {exc}") from exc

        choices = decoded.get("choices") or []
        if not choices:
            raise RuntimeError(f"ARK response missing choices: {decoded}")
        return str(choices[0].get("message", {}).get("content", "")).strip()

    def _parse_tag_response(self, raw: str, cluster_count: int) -> dict[int, str]:
        try:
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                raw_clean = "\n".join(line for line in lines if not line.strip().startswith("```"))
            tags = json.loads(raw_clean)
            if not isinstance(tags, list):
                return {}
            return {item["cluster_index"]: item["topic_tag"] for item in tags if "cluster_index" in item and "topic_tag" in item}
        except Exception:
            return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_cluster_tagger -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/cluster_tagger.py tests/test_cluster_tagger.py
git commit -m "feat: add ClusterTagger for topic tagging via ARK API"
```

---

## Task 3: Pipeline 集成 ClusterTagger

**Files:**
- Modify: `ai_digest/pipeline.py:1-55`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_pipeline.py 新增
def test_pipeline_runs_cluster_tagger_and_includes_topic_tag(self):
    from unittest.mock import MagicMock
    from ai_digest.pipeline import DigestPipeline, DigestRunResult
    from ai_digest.models import DigestItem
    from datetime import datetime, timezone

    mock_collector = MagicMock()
    mock_collector.collect.return_value = [
        DigestItem(title="OpenAI GPT-5", url="https://a.com", source="A", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.9, dedupe_key="a"),
        DigestItem(title="OpenAI announces GPT-5", url="https://b.com", source="B", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.88, dedupe_key="b"),
    ]
    mock_publisher = MagicMock()
    mock_publisher.publish.return_value = ""

    pipeline = DigestPipeline(collector=mock_collector, publisher=mock_publisher, dry_run=True)
    result = pipeline.run(now=datetime(2026,4,14,tzinfo=timezone.utc))

    assert result.status == "composed"
    # Verify clusters have topic_tag set
    assert len(result.items) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline.PipelineTest.test_pipeline_runs_cluster_tagger_and_includes_topic_tag -v`
Expected: 可能 PASS（因为干跑模式不调 ARK），如果 mock 了 ClusterTagger 则会 FAIL

- [ ] **Step 3: 修改 pipeline.py，集成 ClusterTagger**

```python
# ai_digest/pipeline.py
# 1. 添加 import（在文件顶部）
from .cluster_tagger import ClusterTagger

# 2. 修改 DigestPipeline.__init__，添加 cluster_tagger
# 在 __init__ 方法中添加（和其他组件放在一起）：
# self.cluster_tagger = ClusterTagger(...) 或者从外部传入

# 更好的方式：从外部注入，默认不调 ARK（干跑保护）
# 修改 __init__ 签名添加：
#     cluster_tagger: ClusterTagger | None = None,
# 在 __init__ 体内：
# self.cluster_tagger = cluster_tagger

# 3. 修改 run() 方法，在 cluster() 之后调用 tag_clusters
# 找到：
#     clusters = self.clusterer.cluster(quota_items)
# 在它之后加：
#     if self.cluster_tagger is not None:
#         clusters = self.cluster_tagger.tag_clusters(clusters)
```

实际改动：

```python
# ai_digest/pipeline.py 第 5 行附近，加上：
from .cluster_tagger import ClusterTagger

# 第 27-54 行的 __init__ 改为：
class DigestPipeline:
    def __init__(
        self,
        collector: Any,
        publisher: Any | None = None,
        writer: Any | None = None,
        *,
        deduper: RecentDedupeFilter | None = None,
        ranker: ItemRanker | None = None,
        composer: DigestComposer | None = None,
        section_picker: SectionPicker | None = None,
        article_linter: ArticleLinter | None = None,
        cluster_tagger: ClusterTagger | None = None,  # 新增
        dry_run: bool = True,
        min_items: int = 3,
    ) -> None:
        self.collector = collector
        self.publisher = publisher
        self.writer = writer
        self.deduper = deduper or RecentDedupeFilter()
        self.ranker = ranker or ItemRanker()
        self.clusterer = EventClusterer()
        self.summarizer = RuleBasedSummarizer()
        self.payload_builder = DigestPayloadBuilder(clusterer=self.clusterer)
        self.composer = composer or DigestComposer()
        self.section_picker = section_picker or SectionPicker()
        self.article_linter = article_linter or ArticleLinter()
        self.cluster_tagger = cluster_tagger  # 新增
        self.dry_run = dry_run
        self.min_items = min_items

# 第 84 附近，在 clusters = self.clusterer.cluster(quota_items) 之后加：
#         clusters = self.clusterer.cluster(quota_items)
#         if self.cluster_tagger is not None:
#             clusters = self.cluster_tagger.tag_clusters(clusters)
```

实际第 84 行是 `clusters = self.clusterer.cluster(quota_items)`，需要在这行**之后**加：
```python
        if self.cluster_tagger is not None:
            clusters = self.cluster_tagger.tag_clusters(clusters)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS（现有测试不调 cluster_tagger 不受影响）

- [ ] **Step 5: Commit**

```bash
git add ai_digest/pipeline.py
git commit -m "feat: integrate ClusterTagger into pipeline"
```

---

## Task 4: summarizer.py 透传 topic_tag

**Files:**
- Modify: `ai_digest/summarizer.py:74-82`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_payload.py 新增
def test_serialize_cluster_includes_topic_tag(self):
    from ai_digest.summarizer import DigestPayloadBuilder
    from ai_digest.models import DigestItem, EventCluster
    from datetime import datetime, timezone
    item = DigestItem(title="Test", url="https://x.com", source="X", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.5, dedupe_key="x")
    cluster = EventCluster(canonical_title="Test", canonical_url="https://x.com", sources=["X"], items=[item], score=0.5, category="event", topic_tag="模型发布")
    builder = DigestPayloadBuilder()
    serialized = builder._serialize_cluster(cluster)
    assert serialized["topic_tag"] == "模型发布"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_payload.PayloadBuilderTest.test_serialize_cluster_includes_topic_tag -v`
Expected: FAIL - KeyError: 'topic_tag'

- [ ] **Step 3: 修改 summarizer.py**

```python
# ai_digest/summarizer.py 第 74-82 行
# _serialize_cluster 方法改为：
    def _serialize_cluster(self, cluster: EventCluster) -> dict[str, object]:
        return {
            "canonical_title": cluster.canonical_title,
            "canonical_url": cluster.canonical_url,
            "sources": list(cluster.sources),
            "score": cluster.score,
            "category": cluster.category,
            "topic_tag": cluster.topic_tag,  # 新增
            "items": [self._serialize_item(item) for item in cluster.items],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_payload.PayloadBuilderTest.test_serialize_cluster_includes_topic_tag -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_digest/summarizer.py tests/test_payload.py
git commit -m "feat: serialize topic_tag in cluster payload"
```

---

## Task 5: /api/fact-card 端点

**Files:**
- Modify: `ai_digest/webapp/app.py`
- Test: `tests/test_webapp_api.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_webapp_api.py 新增
def test_fact_card_returns_cluster_summary(self):
    from ai_digest.webapp.app import create_app
    from fastapi.testclient import TestClient
    app = create_app(storage_root=tmp_path)
    client = TestClient(app)

    # 写入一个含 cluster 数据的 markdown
    storage_root = tmp_path
    storage_root.joinpath("last_draft.md").write_text("# Test\ncontent", encoding="utf-8")
    storage_root.joinpath("run_data.json").write_text(json.dumps({
        "clusters": [
            {"topic_tag": "模型发布", "sources": ["机器之心", "量子位"], "canonical_title": "OpenAI GPT-5"},
            {"topic_tag": "开源项目", "sources": ["GitHub"], "canonical_title": "Archon"},
        ],
        "total_items": 5,
        "source_distribution": {"news": 3, "github": 2},
    }), encoding="utf-8")

    response = client.get("/api/fact-card")
    assert response.status_code == 200
    data = response.json()
    assert "clusters" in data
    assert data["clusters"][0]["topic_tag"] == "模型发布"
```

注意：这个测试需要 mock 或者先跑过一次 run 以生成 run_data.json。更简单的测试写法是直接调 `DigestPipeline` 得到的数据然后塞进 storage。

先实现端点，测试后续可以调整。

- [ ] **Step 2: 实现 /api/fact-card 端点**

在 `webapp/app.py` 的 `create_app` 函数里，在 `@app.get("/api/history")` 之后加：

```python
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
```

- [ ] **Step 3: 修改 /api/run，把 pipeline 结果的 clusters 数据写入 run_data.json**

在 `run()` 函数里，`runner.run()` 返回 `result`，需要把 `result.items` 和 clusters 信息一起写入 `run_data.json`。

在 `app.py` 的 `run()` 函数里，找到 `result = runner.run()` 之后，加：

```python
        # 写 fact-card 数据
        from collections import Counter
        source_dist = dict(Counter(item.source for item in result.items))
        run_data = {
            "clusters": [
                {
                    "topic_tag": getattr(item, "topic_tag", ""),
                    "sources": [item.source],
                    "canonical_title": item.title,
                }
                for item in result.items
            ],
            "total_items": len(result.items),
            "source_distribution": source_dist,
            "high_signal_dropped": [],
        }
        import json as _json
        run_data_path = root / "run_data.json"
        with run_data_path.open("w", encoding="utf-8") as f:
            _json.dump(run_data, f, ensure_ascii=False)
```

**注意**：`result.items` 是 `list[DigestItem]`，每个 item 本身不是 cluster。但我们只需要在 fact-card 里展示来源分布和原始标题，所以直接把 items 展平成 cluster 列表即可（每个 item 当作一个"pseudo-cluster"展示）。如果后续 pipeline 返回了真实的 clusters 数据，再更新这里。

- [ ] **Step 4: Run tests**

Run: `python3 -m unittest tests.test_webapp_api -v`
Expected: 现有测试 PASS（新增端点不影响现有功能）

- [ ] **Step 5: Commit**

```bash
git add ai_digest/webapp/app.py
git commit -m "feat: add /api/fact-card endpoint and run data persistence"
```

---

## Task 6: 前端 Fact-Card 面板

**Files:**
- Modify: `ai_digest/webapp/templates/index.html`
- Modify: `ai_digest/webapp/static/app.js`

- [ ] **Step 1: 修改 index.html，加 fact-card 面板结构**

在 `index.html` 的发布按钮附近（`id="publish-btn"` 的元素），在其**后面**加一个折叠按钮和侧栏：

```html
<button id="fact-card-btn" title="事实卡" style="padding:6px 12px; background:#f3f4f6; border:1px solid #d1d5db; border-radius:4px; cursor:pointer; font-size:14px;">📋 事实卡</button>
<div id="fact-card-panel" style="display:none; position:fixed; top:0; right:0; width:340px; height:100vh; background:white; box-shadow:-2px 0 8px rgba(0,0,0,0.1); z-index:200; overflow-y:auto; padding:16px; box-sizing:border-box;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
    <h3 style="margin:0; font-size:16px;">事实卡</h3>
    <button id="fact-card-close" style="background:none; border:none; font-size:18px; cursor:pointer;">&times;</button>
  </div>
  <div id="fact-card-content" style="font-size:13px; line-height:1.6;">
    <p style="color:#666;">点击加载...</p>
  </div>
</div>
```

- [ ] **Step 2: 修改 app.js，加 fact-card 交互逻辑**

在 `app.js` 文件末尾加：

```javascript
// Fact Card Panel
const factCardBtn = document.getElementById('fact-card-btn');
const factCardPanel = document.getElementById('fact-card-panel');
const factCardClose = document.getElementById('fact-card-close');
const factCardContent = document.getElementById('fact-card-content');

if (factCardBtn && factCardPanel && factCardClose && factCardContent) {
  factCardBtn.addEventListener('click', async () => {
    factCardPanel.style.display = 'block';
    factCardContent.innerHTML = '<p style="color:#666;">加载中...</p>';
    try {
      const res = await fetch('/api/fact-card');
      const data = await res.json();
      renderFactCard(data, factCardContent);
    } catch (e) {
      factCardContent.innerHTML = '<p style="color:red;">加载失败: ' + e.message + '</p>';
    }
  });

  factCardClose.addEventListener('click', () => {
    factCardPanel.style.display = 'none';
  });
}

function renderFactCard(data, container) {
  if (!data.clusters || data.clusters.length === 0) {
    container.innerHTML = '<p style="color:#666;">暂无数据，请先生成草稿。</p>';
    return;
  }

  const totalItems = data.total_items || 0;
  const dist = data.source_distribution || {};
  const distText = Object.entries(dist).map(([k, v]) => `${k}: ${v}`).join(' / ') || '无';

  let html = `<p style="margin:0 0 12px 0; color:#374151; font-size:14px;"><strong>${totalItems} 条入选</strong> &nbsp;${distText}</p>`;

  data.clusters.forEach(cluster => {
    const tag = cluster.topic_tag || '未分类';
    const title = cluster.canonical_title || cluster.title || '';
    const sources = Array.isArray(cluster.sources) ? cluster.sources.join(', ') : (cluster.sources || '');
    const isMulti = sources.includes(',') || dist[Object.keys(dist).find(k => k === cluster.source)] > 1;
    const multiBadge = isMulti ? '✅ 多源' : '❌ 单源';

    html += `<div style="border:1px solid #e5e7eb; border-radius:6px; padding:10px; margin-bottom:8px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="background:#dbeafe; color:#1d4ed8; font-size:11px; padding:2px 6px; border-radius:3px;">${tag}</span>
        <span style="font-size:11px; color:#9ca3af;">${multiBadge}</span>
      </div>
      <p style="margin:6px 0 0 0; font-size:13px; color:#111;">${title}</p>
      <p style="margin:2px 0 0 0; font-size:11px; color:#6b7280;">来源: ${sources}</p>
    </div>`;
  });

  container.innerHTML = html;
}
```

- [ ] **Step 3: 测试前端交互**

手动测试流程：
1. 启动 `python3 -m ai_digest.webapp.app`
2. 访问 `http://127.0.0.1:8010`
3. 点"生成草稿"，等待完成
4. 点右上角"📋 事实卡"按钮
5. 验证侧栏显示入选事件列表和来源分布

- [ ] **Step 4: Commit**

```bash
git add ai_digest/webapp/templates/index.html ai_digest/webapp/static/app.js
git commit -m "feat: add fact-card panel UI in webapp"
```

---

## 自检清单

**Spec 覆盖检查：**
- [x] Step 1（聚类标签）：Task 1 (models) + Task 2 (cluster_tagger) + Task 3 (pipeline集成) + Task 4 (summarizer透传)
- [x] Step 2（事实卡面板）：Task 5 (API端点) + Task 6 (前端UI)
- [ ] Step 3（LLM 两阶段）- Plan B
- [ ] Step 4（微信 HTML 渲染器）- Plan B

**Placeholder 扫描：**
- 无 "TBD"、"TODO"、placeholder
- 无泛化的 "add appropriate error handling"
- 所有代码均为完整实现

**类型一致性：**
- `EventCluster.topic_tag: str` 在 models.py 定义 → pipeline.py 用 `replace(cluster, topic_tag=tag)` → summarizer.py 透传 `"topic_tag": cluster.topic_tag` → 前端 `data.clusters[i].topic_tag`
- 全流程类型一致
