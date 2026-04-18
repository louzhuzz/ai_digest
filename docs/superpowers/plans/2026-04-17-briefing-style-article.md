# Briefing-Style Article Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有“热点汇总式”成稿改成 800-1200 字的短版专业简报，稳定输出 2 个主重点和 2-3 个次重点，并在首段先给当天总判断。

**Architecture:** 在成稿前增加一个“briefing selection”层，明确产出 `lead_items`、`secondary_items` 和 `briefing_angle`，再由 payload builder 生成更窄、更强约束的 article input。LLM writer 保留现有调用方式，但切换为短版专业简报 prompt，并要求标题、导语、主重点、次重点都围绕同一主线展开。

**Tech Stack:** Python 3.11+、标准库、现有 `DigestPipeline` / `SectionPicker` / `DigestPayloadBuilder` / `ARKArticleWriter`、`unittest`

---

## File Map

- Modify: `ai_digest/section_picker.py`
  - 现有 section 选择逻辑所在地；新增 briefing 选择结构，负责挑选 2 个主重点和 2-3 个次重点。
- Modify: `ai_digest/summarizer.py`
  - `DigestPayloadBuilder` 目前只产出 cluster 列表；这里要改成面向“专业简报”输入的数据结构。
- Modify: `ai_digest/pipeline.py`
  - 接入新的 briefing selection 数据流，把 writer 输入从“热点池聚类”切到“主重点 + 次重点 + 主线”。
- Modify: `ai_digest/llm_writer.py`
  - 收紧 prompt，要求短版专业简报风格；必要时扩展输出验证。
- Modify: `tests/test_section_picker.py`
  - 补 briefing 选择的行为测试。
- Modify: `tests/test_payload.py`
  - 补 article input 结构测试。
- Modify: `tests/test_pipeline.py`
  - 覆盖 pipeline 使用新 briefing 数据的行为。
- Modify: `tests/test_llm_writer.py`
  - 锁住短版专业简报 prompt 约束。

### Task 1: 定义 Briefing 选择结构

**Files:**
- Modify: `ai_digest/section_picker.py`
- Test: `tests/test_section_picker.py`

- [ ] **Step 1: 写失败测试，定义新的 briefing 输出结构**

```python
from ai_digest.section_picker import SectionPicker

sections = SectionPicker().pick_briefing(items)

assert len(sections.lead_items) == 2
assert 2 <= len(sections.secondary_items) <= 3
assert isinstance(sections.briefing_angle, str)
assert sections.briefing_angle
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_section_picker -v`
Expected: FAIL，提示 `SectionPicker` 没有 `pick_briefing` 或 `DigestSections` 不含新字段。

- [ ] **Step 3: 最小实现 briefing 结构和 `pick_briefing()`**

```python
@dataclass(frozen=True)
class BriefingSelection:
    lead_items: list[DigestItem]
    secondary_items: list[DigestItem]
    briefing_angle: str


def pick_briefing(self, items: list[DigestItem]) -> BriefingSelection:
    ordered = self.apply_source_quota(items)
    lead_items = self._pick_lead_items(ordered)
    secondary_items = self._pick_secondary_items(ordered, lead_items)
    briefing_angle = self._infer_briefing_angle(lead_items, secondary_items)
    return BriefingSelection(
        lead_items=lead_items,
        secondary_items=secondary_items,
        briefing_angle=briefing_angle,
    )
```

- [ ] **Step 4: 为主重点与次重点补最小选择规则**

```python
def _pick_lead_items(self, items: list[DigestItem]) -> list[DigestItem]:
    used: set[str] = set()
    selected: list[DigestItem] = []
    selected.extend(self._take(items, used, {"news", "tool"}, limit=1))
    remaining = 2 - len(selected)
    if remaining > 0:
        selected.extend(self._take(items, used, {"github", "project", "news", "tool"}, limit=remaining))
    return selected[:2]


def _pick_secondary_items(self, items: list[DigestItem], lead_items: list[DigestItem]) -> list[DigestItem]:
    used = {item.dedupe_key or item.url for item in lead_items}
    selected = self._take(items, used, {"github", "project", "news", "tool"}, limit=3)
    return selected[:3]
```

- [ ] **Step 5: 实现最小 `briefing_angle` 推断**

```python
def _infer_briefing_angle(self, lead_items: list[DigestItem], secondary_items: list[DigestItem]) -> str:
    combined = [*lead_items, *secondary_items]
    news_count = sum(1 for item in combined if item.category in {"news", "tool"})
    project_count = sum(1 for item in combined if item.category in {"github", "project"})
    if news_count >= 3:
        return "今天的主线偏行业与产品更新"
    if project_count >= 3:
        return "今天的主线偏开源项目和工程落地"
    return "今天的主线由新闻和项目共同推动"
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_section_picker -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add ai_digest/section_picker.py tests/test_section_picker.py
git commit -m "feat: add briefing item selection"
```

### Task 2: 让 Payload Builder 产出简报语义输入

**Files:**
- Modify: `ai_digest/summarizer.py`
- Test: `tests/test_payload.py`

- [ ] **Step 1: 写失败测试，锁定新的 article input 结构**

```python
payload = DigestPayloadBuilder().build_article_input(
    [news_item_a, news_item_b, project_item],
    date="2026-04-10",
    briefing_selection=selection,
    clusters=clusters,
)

assert payload["briefing_angle"]
assert len(payload["lead_items"]) == 2
assert 2 <= len(payload["secondary_items"]) <= 3
assert "top_event_clusters" not in payload
assert "top_project_clusters" not in payload
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_payload -v`
Expected: FAIL，提示 `build_article_input()` 不接受 `briefing_selection` 或仍输出旧字段。

- [ ] **Step 3: 修改 `build_article_input()` 签名和返回结构**

```python
def build_article_input(
    self,
    items: Iterable[DigestItem],
    date: str,
    *,
    briefing_selection=None,
    clusters: list[EventCluster] | None = None,
) -> dict[str, object]:
    ordered = list(items)
    selection = briefing_selection
    if selection is None:
        raise ValueError("briefing_selection is required for article input")
    return {
        "date": date,
        "signal_pool_size": len(ordered),
        "briefing_angle": selection.briefing_angle,
        "lead_items": [self._serialize_item(item) for item in selection.lead_items],
        "secondary_items": [self._serialize_item(item) for item in selection.secondary_items],
    }
```

- [ ] **Step 4: 限制摘要字段长度，避免 writer 输入过长**

```python
summary = str(payload.get("summary") or payload.get("metadata", {}).get("description") or "")
payload["summary"] = summary[:220] + "..." if len(summary) > 220 else summary
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_payload -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add ai_digest/summarizer.py tests/test_payload.py
git commit -m "feat: build briefing-style article input"
```

### Task 3: 在 Pipeline 中接入 Briefing 选择

**Files:**
- Modify: `ai_digest/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试，要求 pipeline 用 briefing 结构驱动 writer**

```python
result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

article_input = writer.calls[0]
assert "briefing_angle" in article_input
assert len(article_input["lead_items"]) == 2
assert 2 <= len(article_input["secondary_items"]) <= 3
assert "top_event_clusters" not in article_input
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL，writer 仍收到旧 article input。

- [ ] **Step 3: 在 pipeline 中生成 briefing selection 并传给 payload builder**

```python
briefing_selection = self.section_picker.pick_briefing(quota_items)
article_input = self.payload_builder.build_article_input(
    quota_items,
    date=str(payload["date"]),
    briefing_selection=briefing_selection,
    clusters=self._clusters,
)
```

- [ ] **Step 4: 保留 outline 两阶段链路，但改用新 article input**

```python
outline = None
if self.outline_generator is not None:
    outline = self.outline_generator.generate(article_input)
if outline is not None and hasattr(self.writer, "render"):
    markdown = self.writer.render(outline, article_input)
else:
    markdown = self.writer.write(article_input)
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add ai_digest/pipeline.py tests/test_pipeline.py
git commit -m "feat: feed briefing selection into article pipeline"
```

### Task 4: 收紧 Writer Prompt 到短版专业简报

**Files:**
- Modify: `ai_digest/llm_writer.py`
- Test: `tests/test_llm_writer.py`

- [ ] **Step 1: 写失败测试，锁住短版专业简报 prompt**

```python
self.assertIn("800 到 1200 字", SYSTEM_PROMPT)
self.assertIn("开发者专业简报", SYSTEM_PROMPT)
self.assertIn("先给当天整体判断", SYSTEM_PROMPT)
self.assertIn("只展开 2 个主重点", SYSTEM_PROMPT)
self.assertIn("2 到 3 条短条补充", SYSTEM_PROMPT)
self.assertIn("不要平均照顾所有候选项", SYSTEM_PROMPT)
self.assertNotIn("编号速览", SYSTEM_PROMPT)
self.assertNotIn("AI 每日新闻速递", SYSTEM_PROMPT)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_llm_writer -v`
Expected: FAIL，当前 prompt 仍描述“公众号文章 + 编号速览”。

- [ ] **Step 3: 改写 `SYSTEM_PROMPT` 为短版专业简报风格**

```python
SYSTEM_PROMPT = """你在写一篇面向开发者的 AI 热点专业简报。
所有输出必须使用中文 Markdown。
全文目标 800 到 1200 字，5 分钟内可以读完。
你不是在做资讯汇总，而是在帮读者判断今天最该跟什么。
开头必须先给当天整体判断，再展开正文。
全文只展开 2 个主重点，其余内容只做 2 到 3 条短条补充。
不要平均照顾所有候选项。
标题必须直接点出当天最值得跟的一条变化，不能使用通用日报标题。
语气平稳、专业、克制，不口语化，不营销化。
禁止使用“摘要：”“价值：”“为什么值得跟：”等标签。
禁止照抄英文摘要，禁止编造事实、数字、链接和结论。"""
```

- [ ] **Step 4: 收紧 `RENDER_SYSTEM_PROMPT` 与 outline 写法**

```python
RENDER_SYSTEM_PROMPT = """你是开发者专业简报编辑。
请把大纲写成 800 到 1200 字的短版专业简报。
先给总判断，再写 2 个主重点，最后补 2 到 3 条次重点。
每个主重点必须写出：发生了什么、为什么值得跟、对开发者意味着什么。
次重点只写值得继续关注的原因，不展开背景。"""
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_llm_writer -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add ai_digest/llm_writer.py tests/test_llm_writer.py
git commit -m "feat: retune writer for briefing-style articles"
```

### Task 5: 用选择结构更新 SectionPicker 的旧接口兼容

**Files:**
- Modify: `ai_digest/section_picker.py`
- Test: `tests/test_section_picker.py`

- [ ] **Step 1: 写失败测试，确保旧 `pick()` 仍可工作**

```python
sections = SectionPicker().pick(items)
assert sections.top_items
assert sections.github_items is not None
assert sections.progress_items is not None
```

- [ ] **Step 2: 运行测试，确认失败或暴露兼容问题**

Run: `python3 -m unittest tests.test_section_picker -v`
Expected: FAIL，如果改动破坏了旧接口。

- [ ] **Step 3: 保持旧 `pick()` 接口不变，只在内部复用新逻辑**

```python
def pick(self, items: list[DigestItem]) -> DigestSections:
    ordered = self.apply_source_quota(items)
    used: set[str] = set()
    top_items = self._pick_top_items(ordered, used)
    github_items = self._take(ordered, used, {"github", "project"}, limit=self.github_limit)
    progress_items = self._take(ordered, used, {"news", "tool"}, limit=self.progress_limit)
    return DigestSections(top_items=top_items, github_items=github_items, progress_items=progress_items)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_section_picker -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add ai_digest/section_picker.py tests/test_section_picker.py
git commit -m "refactor: preserve legacy section picker behavior"
```

### Task 6: 跑集成回归并做干跑样本检查

**Files:**
- Modify: none
- Test: `tests/test_section_picker.py`
- Test: `tests/test_payload.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_llm_writer.py`

- [ ] **Step 1: 跑成稿相关测试集合**

Run: `python3 -m unittest tests.test_section_picker tests.test_payload tests.test_pipeline tests.test_llm_writer -v`
Expected: PASS

- [ ] **Step 2: 跑全量回归**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 3: 做一次 dry-run 样本检查**

Run: `python3 -m ai_digest --dry-run`
Expected: 输出标题不是通用日报标题，正文首段先给总判断，正文中存在 2 个主重点与 2 到 3 条次重点。

- [ ] **Step 4: 记录样本检查结果**

```text
检查项：
- 标题是否具体
- 开头是否先给总判断
- 主重点是否为 2 条
- 次重点是否为 2 到 3 条
- 全文是否控制在短版节奏
```

- [ ] **Step 5: 提交**

```bash
git add .
git commit -m "test: verify briefing-style article generation"
```
