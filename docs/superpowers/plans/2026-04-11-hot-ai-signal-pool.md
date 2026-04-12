# Hot AI Signal Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有公众号日报改造成“圈内高热度 AI 动态候选池 + LLM 自主编排”的链路，让新闻为主、项目为辅，弱化 RSS 和固定栏目。

**Architecture:** 保留现有发布和 LLM 成稿主链路，只替换采集层、排序层和 LLM 输入层。默认来源改成高热度源集合，`ranking.py` 负责热度分，`summarizer.py` 负责构建热点候选池 payload，`section_picker.py` 退出正式发布主路径，仅保留 `dry-run` 或兼容路径。

**Tech Stack:** Python 3、`unittest`、标准库 HTTP/HTML 解析、现有 WeChat draft publisher、ARK LLM writer

---

### Task 1: 重写默认来源清单为“高热度源 + 官方补充”

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/defaults.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_defaults_hot_pool.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_defaults_hot_pool.py`

- [ ] **Step 1: 写失败测试，定义新的默认来源集合**

```python
def test_default_sources_cover_hot_ai_pool(self) -> None:
    specs = build_default_source_specs()
    names = [spec.name for spec in specs]
    self.assertIn("GitHub Trending", names)
    self.assertIn("Hacker News AI", names)
    self.assertIn("Hugging Face Trending", names)
    self.assertIn("OpenAI News", names)
    self.assertNotIn("arXiv cs.AI", names)
```

- [ ] **Step 2: 跑测试确认当前失败**

Run:
```bash
python3 -m unittest tests.test_defaults_hot_pool -v
```

Expected: FAIL，因为当前默认源里仍然有 `arXiv cs.AI`，也没有高热度源

- [ ] **Step 3: 最小实现新的 `SourceSpec` 集合**

```python
return [
    SourceSpec(name="GitHub Trending", url="https://github.com/trending", kind="github_trending", category="project"),
    SourceSpec(name="Hacker News AI", url="https://news.ycombinator.com/", kind="hn_frontpage", category="news"),
    SourceSpec(name="Hugging Face Trending", url="https://huggingface.co/models?sort=trending", kind="hf_trending", category="project"),
    SourceSpec(name="OpenAI News", url="https://openai.com/news", kind="web_news_index", category="news"),
]
```

- [ ] **Step 4: 为新增 source kind 预留 collector 绑定点**

```python
elif source.kind == "hn_frontpage":
    collectors.append(BoundHNCollector(HNFrontPageCollector(), source.url))
elif source.kind == "hf_trending":
    collectors.append(BoundHFTrendingCollector(HFTrendingCollector(), source.url))
elif source.kind == "web_news_index":
    collectors.append(BoundWebNewsCollector(WebNewsIndexCollector(source.name), source.url))
```

- [ ] **Step 5: 跑默认来源测试**

Run:
```bash
python3 -m unittest tests.test_defaults tests.test_defaults_hot_pool -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/defaults.py /mnt/d/AIcodes/openclaw/tests/test_defaults_hot_pool.py
git commit -m "feat: replace default sources with hot ai pool"
```

### Task 2: 新增高热度源 collectors

**Files:**
- Create: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/hn.py`
- Create: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/huggingface.py`
- Create: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/web_news.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/__init__.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_hn_collector.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_huggingface_collector.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_web_news_collector.py`

- [ ] **Step 1: 写 HN 失败测试**

```python
def test_hn_collector_extracts_ai_news_items(self) -> None:
    html = '''
    <span class="titleline"><a href="https://example.com/openai-update">OpenAI launches new model</a></span>
    <span class="score">120 points</span>
    '''
    items = HNFrontPageCollector().parse_frontpage(html, page_url="https://news.ycombinator.com/")
    self.assertEqual(len(items), 1)
    self.assertEqual(items[0].category, "news")
    self.assertEqual(items[0].metadata["community_heat"], 120)
```

- [ ] **Step 2: 写 Hugging Face 失败测试**

```python
def test_hf_collector_extracts_trending_models(self) -> None:
    html = '''
    <article><a href="/org/model-x">Model X</a><div>Multimodal reasoning model</div></article>
    '''
    items = HFTrendingCollector().parse_trending(html, page_url="https://huggingface.co/models?sort=trending")
    self.assertEqual(len(items), 1)
    self.assertEqual(items[0].category, "project")
```

- [ ] **Step 3: 写官方新闻索引失败测试**

```python
def test_web_news_index_collector_extracts_links(self) -> None:
    html = '''
    <a href="/news/new-update">New Update</a>
    '''
    items = WebNewsIndexCollector("OpenAI News").parse_index(html, base_url="https://openai.com/news")
    self.assertEqual(len(items), 1)
    self.assertEqual(items[0].source, "OpenAI News")
```

- [ ] **Step 4: 跑测试确认当前失败**

Run:
```bash
python3 -m unittest tests.test_hn_collector tests.test_huggingface_collector tests.test_web_news_collector -v
```

Expected: module not found / attribute missing

- [ ] **Step 5: 最小实现 3 个 collector**

```python
class HNFrontPageCollector:
    def parse_frontpage(...): ...
    def collect(...): ...

class HFTrendingCollector:
    def parse_trending(...): ...
    def collect(...): ...

class WebNewsIndexCollector:
    def parse_index(...): ...
    def collect(...): ...
```

要求：
- 统一产出 `DigestItem`
- 设置 `category`
- 在 `metadata` 中带上 `community_heat` / `source_strength` 等基础信号
- 只保留 AI 相关条目

- [ ] **Step 6: 跑 collector 测试**

Run:
```bash
python3 -m unittest tests.test_hn_collector tests.test_huggingface_collector tests.test_web_news_collector -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/collectors /mnt/d/AIcodes/openclaw/tests/test_hn_collector.py /mnt/d/AIcodes/openclaw/tests/test_huggingface_collector.py /mnt/d/AIcodes/openclaw/tests/test_web_news_collector.py
git commit -m "feat: add hot ai source collectors"
```

### Task 3: 把 ranking 改成“热度分”

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/ranking.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_ranking.py`

- [ ] **Step 1: 写失败测试，定义热度分优先级**

```python
def test_ranks_hot_community_signal_above_plain_recent_item(self) -> None:
    hot_item = DigestItem(..., category="news", metadata={"source_strength": 0.8, "community_heat": 200, "developer_relevance": 0.9})
    plain_item = DigestItem(..., category="news", metadata={"source_strength": 0.2, "community_heat": 0, "developer_relevance": 0.3})
    ranked = ItemRanker().rank([plain_item, hot_item], now=now)
    self.assertEqual(ranked[0].title, hot_item.title)
```

- [ ] **Step 2: 跑测试确认当前失败**

Run:
```bash
python3 -m unittest tests.test_ranking -v
```

Expected: FAIL，因为当前主要按 freshness + stars

- [ ] **Step 3: 最小实现热度分**

```python
community_heat = min(float(item.metadata.get("community_heat", 0) or 0) / 200.0, 1.0)
source_strength = float(item.metadata.get("source_strength", 0) or 0)
developer_relevance = float(item.metadata.get("developer_relevance", 0) or 0)

if item.category == "project":
    return round((0.30 * freshness) + (0.30 * community_heat) + (0.20 * source_strength) + (0.20 * developer_relevance), 4)
return round((0.35 * freshness) + (0.25 * community_heat) + (0.20 * source_strength) + (0.20 * developer_relevance), 4)
```

- [ ] **Step 4: 跑 ranking 测试**

Run:
```bash
python3 -m unittest tests.test_ranking -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/ranking.py /mnt/d/AIcodes/openclaw/tests/test_ranking.py
git commit -m "feat: rank items by hot ai signal score"
```

### Task 4: 把 payload 从固定栏目改成热点候选池

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/summarizer.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_payload.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_llm_writer.py`

- [ ] **Step 1: 写失败测试，定义热点候选池 payload**

```python
def test_build_article_input_uses_signal_pool_shape(self) -> None:
    payload = DigestPayloadBuilder().build_article_input(items=[item], date="2026-04-11")
    self.assertEqual(payload["date"], "2026-04-11")
    self.assertEqual(payload["items"][0]["type"], "news")
    self.assertIn("heat_signals", payload["items"][0])
    self.assertIn("why_relevant", payload["items"][0])
```

- [ ] **Step 2: 跑测试确认当前失败**

Run:
```bash
python3 -m unittest tests.test_payload tests.test_llm_writer -v
```

Expected: FAIL，因为当前还是 `top_items/github_items/progress_items`

- [ ] **Step 3: 最小实现新 payload builder**

```python
def build_article_input(self, items: Iterable[DigestItem], date: str) -> dict[str, object]:
    return {
        "date": date,
        "items": [self._serialize_signal_item(item) for item in items],
    }

def _serialize_signal_item(self, item: DigestItem) -> dict[str, object]:
    payload = self._serialize_item(item)
    payload["type"] = "project" if item.category == "github" else "news"
    payload["heat_signals"] = {
        "community_heat": item.metadata.get("community_heat", 0),
        "source_strength": item.metadata.get("source_strength", 0),
        "stars_growth": item.metadata.get("stars_growth", 0),
    }
    payload["why_relevant"] = item.why_it_matters
    return payload
```

- [ ] **Step 4: 调整 `llm_writer` 测试输入**

```python
article_input = {
    "date": "2026-04-11",
    "items": [
        {"title": "OpenAI update", "type": "news", ...},
        {"title": "Agent project", "type": "project", ...},
    ],
}
```

- [ ] **Step 5: 跑 payload 与 writer 测试**

Run:
```bash
python3 -m unittest tests.test_payload tests.test_llm_writer -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/summarizer.py /mnt/d/AIcodes/openclaw/tests/test_payload.py /mnt/d/AIcodes/openclaw/tests/test_llm_writer.py
git commit -m "feat: build hot ai signal pool payload"
```

### Task 5: 调整 pipeline 与 LLM prompt，退出固定栏目主路径

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/pipeline.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_pipeline.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_llm_writer.py`

- [ ] **Step 1: 写失败测试，定义发布路径不再依赖固定栏目 payload**

```python
def test_pipeline_passes_ranked_signal_items_to_writer(self) -> None:
    writer = FakeWriter()
    pipeline = DigestPipeline(..., writer=writer, dry_run=False, min_items=3)
    result = pipeline.run(now=...)
    self.assertEqual(result.status, "published")
    self.assertIn("items", writer.calls[0])
    self.assertNotIn("top_items", writer.calls[0])
```

- [ ] **Step 2: 跑测试确认当前失败**

Run:
```bash
python3 -m unittest tests.test_pipeline tests.test_llm_writer -v
```

Expected: FAIL，因为 pipeline 仍依赖 `section_picker.pick()` 结果构造 article input

- [ ] **Step 3: 最小实现 pipeline 改造**

```python
if self.dry_run:
    markdown = self.composer.compose(summarized, date=str(payload["date"]))
else:
    article_input = self.payload_builder.build_article_input(summarized, date=str(payload["date"]))
    markdown = self.writer.write(article_input)
```

`section_picker` 保留，但不再进入正式发布主路径。

- [ ] **Step 4: 调整 `SYSTEM_PROMPT`**

```python
SYSTEM_PROMPT = \"\"\"...
你会收到一个“圈内高热度 AI 动态候选池”。
请从中挑选今天最值得跟的 5 到 7 条，新闻为主，项目为辅。
不要机械分栏目，不要平均分配，不要逐条流水账摘要。
按热度和影响组织结构，写成一篇自然的公众号文章。
...\"\"\"
```

- [ ] **Step 5: 跑 pipeline 与 writer 测试**

Run:
```bash
python3 -m unittest tests.test_pipeline tests.test_llm_writer -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/pipeline.py /mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py /mnt/d/AIcodes/openclaw/tests/test_pipeline.py /mnt/d/AIcodes/openclaw/tests/test_llm_writer.py
git commit -m "feat: publish from hot ai signal pool"
```

### Task 6: 全量回归与真实验证

**Files:**
- Test: `/mnt/d/AIcodes/openclaw/tests`

- [ ] **Step 1: 跑全量测试**

Run:
```bash
python3 -m unittest discover -s /mnt/d/AIcodes/openclaw/tests -v
```

Expected: PASS

- [ ] **Step 2: 跑真实 collector 验证**

Run:
```bash
python3 - <<'PY'
from ai_digest.defaults import build_default_collector
collector = build_default_collector()
items = collector.collect()
print(len(items))
for item in items[:10]:
    print(item.category, item.source, item.title)
PY
```

Expected: 输出中包含 `news` 与 `project` 两类信号，不再由 `arXiv` 占主体

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: switch digest to hot ai signal pool"
```

## 自检

- spec coverage：已覆盖默认来源替换、高热度 collectors、热度分、候选池 payload、固定栏目退出主路径、真实验证。
- placeholder scan：无 `TODO/TBD/以后再说` 之类占位。
- type consistency：统一使用 `type`、`heat_signals`、`why_relevant`、`community_heat`、`source_strength` 这些字段。
