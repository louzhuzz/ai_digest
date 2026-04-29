# Agent-Driven AI Digest Refactoring Plan

> **For Sisyphus:** 本 plan 描述将 ai_digest 从"代码编排 + LLM 调用"模式重构成"工具脚本 + Sisyphus 全权编排"模式的完整步骤。

**Goal:** 砍掉 pipeline/runner/composition/ranking/summarizer/section_picker/event_clusterer/cluster_tagger/article_linter/outline_generator/llm_writer/wechat_renderer 约 1400 行，改为 Sisyphus（加载 skill 后）直接调用 Python 工具脚本 + 自己写文章。

**Architecture:**
```
旧：代码编排代码 → 偶尔调 LLM
新：Sisyphus 编排 → 调工具脚本抓/存/发 + 自己写文章
```

**Tech Stack:** Python 3.11+、标准库、现有 collectors/state_store/publishers 保留为工具脚本。

---

## 改造原则

1. **Sisyphus 是大脑**，不是 pipeline。所有流程决策、内容判断、文章撰写都由 Sisyphus 完成。
2. **工具脚本只做 Sisyphus 不擅长的事**：HTTP 抓取、HTML 解析、SQLite 持久化、微信 API 调用、PIL 图片生成。
3. **不保留任何"流程编排代码"**。pipeline.py、runner.py 整文件删除。
4. **不保留任何"固定文章模板"**。composition.py、wechat_renderer.py 整文件删除。文章结构和风格由 Sisyphus 当天自行决定。
5. **不保留任何"规则引擎/打分函数"**。ranking.py、summarizer.py、section_picker.py、event_clusterer.py 等整文件删除。
6. **不保留任何"LLM 调用封装"**。llm_writer.py、outline_generator.py、cluster_tagger.py 整文件删除。Sisyphus 自己就是 LLM。
7. **测试文件同步删除或迁移**。与删除模块对应的测试文件删除。
8. **webapp 需要简化**，去除依赖 pipeline 的内部逻辑，改为触发 Sisyphus 执行 + 读取结果的壳。

## 保留的工具脚本

| 脚本 | 行数 | 用途 |
|------|------|------|
| `collectors/` 全部 5 个 | ~500 | 多源数据抓取+HTML解析 |
| `state_store.py` | ~87 | SQLite 持久化去重 |
| `publishers/wechat.py` | ~158 | 微信草稿箱 API |
| `auth.py` | ~37 | 微信 token 获取 |
| `http_client.py` | ~16 | HTTP 工具 |
| `cover_image.py` | ~102 | PIL 封面图 |
| `wechat_image_uploader.py` | ~69 | 微信 CDN 图片上传 |
| `settings.py` | ~96 | 配置加载 |

这些工具脚本需要重构为**命令行可调用**的形式（CLI entry point），让 Sisyphus 能用 bash 工具调用。

## 删除的模块

| 模块 | 行数 | 删除原因 |
|------|------|----------|
| `pipeline.py` | 161 | 流程编排 → Sisyphus 自己决定 |
| `runner.py` | 81 | 流程封装 → 同上 |
| `composition.py` | 96 | 固定模板 → Sisyphus 自由写作 |
| `ranking.py` | 45 | 打分公式 → Sisyphus 判断重要性 |
| `summarizer.py` | 107 | 规则摘要 → Sisyphus 写摘要 |
| `section_picker.py` | 125 | 来源配额硬规则 → Sisyphus 自己选 |
| `event_clusterer.py` | 133 | 规则聚类 → Sisyphus 发现关联 |
| `cluster_tagger.py` | 101 | LLM 调用 → Sisyphus 做 |
| `article_linter.py` | 34 | 规则检查 → Sisyphus 自己保证质量 |
| `outline_generator.py` | 114 | LLM 调用封装 → Sisyphus 自己生成大纲 |
| `llm_writer.py` | 306 | LLM 调用封装 → Sisyphus 自己写 |
| `wechat_renderer.py` | 112 | Markdown→HTML 转换 → Sisyphus 直接输出合规格式 |
| **合计** | **~1415** | |

## 新建的 Skill

`.claude/skills/ai-digest/SKILL.md` — 告诉 Sisyphus：
- 可用哪些工具脚本及如何调用
- 整体工作流
- 微信公众号文章的格式约束
- 质量要求

---

## File Map

### Phase 1：工具脚本 CLI 化

- **Modify:** `ai_digest/tool_run.py` — **新建**工具入口模块，把 collectors/publishers/dedup 等封装成 CLI 子命令
- **Modify:** `ai_digest/state_store.py` — 可能需调整入口
- **Modify:** `ai_digest/publishers/wechat.py` — 确保可通过 CLI 调用
- **Delete:** `ai_digest/pipeline.py`、`runner.py`

### Phase 2：删除编排/规则模块

- **Delete:** `ai_digest/composition.py`
- **Delete:** `ai_digest/ranking.py`
- **Delete:** `ai_digest/summarizer.py`
- **Delete:** `ai_digest/section_picker.py`
- **Delete:** `ai_digest/event_clusterer.py`
- **Delete:** `ai_digest/cluster_tagger.py`
- **Delete:** `ai_digest/article_linter.py`
- **Delete:** `ai_digest/outline_generator.py`
- **Delete:** `ai_digest/llm_writer.py`
- **Delete:** `ai_digest/wechat_renderer.py`

### Phase 3：清理遗留引用

- **Modify:** `ai_digest/__init__.py` — 移除已删除模块的导出
- **Modify:** `ai_digest/defaults.py` — 精简工厂函数，只保留工具脚本构建
- **Modify:** `ai_digest/cli.py` — 改为调用 tool_run 的入口
- **Modify:** `ai_digest/__main__.py` — 指向新入口
- **Delete:** 与被删模块对应的测试文件

### Phase 4：简化 webapp

- **Modify:** `ai_digest/webapp/app.py` — 去掉依赖 pipeline 的内部逻辑，简化为前端的壳
- **Modify:** `ai_digest/webapp/storage.py` — 保留

### Phase 5：写 Skill

- **New:** `.claude/skills/ai-digest/SKILL.md`

---

## Task 1：工具脚本 CLI 入口（tool_run.py）

**Files:**
- New: `ai_digest/tool_run.py`
- Modify: `ai_digest/state_store.py`（如有需要）

**Sub-steps:**

- [ ] **Step 1: 设计 tool_run.py 结构**

```python
# ai_digest/tool_run.py
# Sisyphus 可调用的工具脚本 CLI
# 用法: python -m ai_digest.tool_run <command> [args]

import sys
from .tool_collect import main as collect_main
from .tool_dedup import main as dedup_main
from .tool_publish import main as publish_main
from .tool_cover import main as cover_main

COMMANDS = {
    "collect": collect_main,
    "dedup": dedup_main,
    "publish": publish_main,
    "cover": cover_main,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python -m ai_digest.tool_run <command> [args]")
        print("Commands:", ", ".join(COMMANDS))
        sys.exit(1)
    COMMANDS[sys.argv[1]]()

if __name__ == "__main__":
    main()
```

各子命令设计：

```bash
# 收集（输出 JSON 到 stdout）
python -m ai_digest.tool_run collect
# → stdout: JSON array of DigestItem

# 去重（从 stdin 读 JSON，输出过滤后的 JSON）
python -m ai_digest.tool_run dedup < items.json
# → stdout: JSON array of filtered items

# 发布（从 stdin 读 markdown）
cat article.md | python -m ai_digest.tool_run publish [--title "xxx"]
# → stdout: {"draft_id": "xxx"} 或 {"error": "..."}

# 生成封面图
python -m ai_digest.tool_run cover --title "xxx" --output cover.jpg
# → 写入 cover.jpg
```

- [ ] **Step 2: 实现 collect 子命令**

把 `CompositeCollector` 的调用逻辑搬过来。从 stdin 读 settings 或直接加载 `.env`。输出 JSON。

```python
# tool_collect.py
import json
from .settings import load_settings
from .defaults import build_default_collector

def main():
    collector = build_default_collector()
    items = collector.collect()
    serialized = [...]  # serialize DigestItem list
    json.dump(serialized, sys.stdout, ensure_ascii=False, default=str)
```

- [ ] **Step 3: 实现 dedup 子命令**

从 stdin 读 JSON items，调用 state_store 去做重，输出过滤后的 JSON。

```python
# tool_dedup.py
import json, sys
from .settings import load_settings
from .state_store import SqliteStateStore
from .models import DigestItem

def main():
    settings = load_settings()
    store = SqliteStateStore(settings.state_db_path)
    store.initialize()
    items = [DigestItem(**item) for item in json.load(sys.stdin)]
    # dedup logic...
    filtered = [...]
    json.dump(filtered, sys.stdout, ensure_ascii=False, default=str)
```

- [ ] **Step 4: 实现 publish 子命令**

从 stdin 读 markdown，调用 WeChatDraftPublisher。

```python
# tool_publish.py
import json, sys
from .settings import load_settings
from .defaults import build_default_publisher

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="AI 每日新闻速递")
    args = parser.parse_args()
    markdown = sys.stdin.read()
    settings = load_settings()
    publisher = build_default_publisher(settings)
    draft_id = publisher.publish(markdown, title=args.title)
    print(json.dumps({"draft_id": draft_id or ""}, ensure_ascii=False))
```

- [ ] **Step 5: 实现 cover 子命令**

调用 generate_cover_image 并写文件。

```python
# tool_cover.py
import sys, argparse
from .cover_image import generate_cover_image

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = generate_cover_image(args.title)
    with open(args.output, "wb") as f:
        f.write(data)
```

### Task 1 验证

```bash
# 测试 collect
python -m ai_digest.tool_run collect > /tmp/items.json

# 测试 dedup
python -m ai_digest.tool_run dedup < /tmp/items.json > /tmp/filtered.json

# 测试 cover
python -m ai_digest.tool_run cover --title "测试标题" --output /tmp/cover.jpg
```

---

## Task 2：删除编排/规则模块

**Files:**
- Delete: `ai_digest/pipeline.py`
- Delete: `ai_digest/runner.py`
- Delete: `ai_digest/composition.py`
- Delete: `ai_digest/ranking.py`
- Delete: `ai_digest/summarizer.py`
- Delete: `ai_digest/section_picker.py`
- Delete: `ai_digest/event_clusterer.py`
- Delete: `ai_digest/cluster_tagger.py`
- Delete: `ai_digest/article_linter.py`
- Delete: `ai_digest/outline_generator.py`
- Delete: `ai_digest/llm_writer.py`
- Delete: `ai_digest/wechat_renderer.py`

**同时删除对应的测试文件：**
- `tests/test_pipeline.py`
- `tests/test_runner.py`
- `tests/test_composition.py`
- `tests/test_ranking.py`
- `tests/test_payload.py`
- `tests/test_section_picker.py`
- `tests/test_event_clusterer.py`
- `tests/test_cluster_tagger.py`
- `tests/test_article_linter.py`
- `tests/test_outline_generator.py`
- `tests/test_llm_writer.py`
- `tests/test_summarizer.py`
- `tests/test_wechat_renderer.py`

**Sub-steps:**

- [ ] **Step 1: 删除所有上述模块和测试文件**
- [ ] **Step 2: 运行测试，确认剩余测试通过**

```bash
python -m unittest discover -s tests -v
```

---

## Task 3：清理遗留引用

**Files:**
- Modify: `ai_digest/__init__.py`
- Modify: `ai_digest/defaults.py`
- Modify: `ai_digest/cli.py`
- Modify: `ai_digest/__main__.py`

**Sub-steps:**

- [ ] **Step 1: 精简 `__init__.py`**

只导出工具脚本相关的接口和模型：

```python
from .models import DigestItem, EventCluster
from .collectors import GitHubTrendingCollector, HNFrontPageCollector, HFTrendingCollector, RSSCollector, WebNewsIndexCollector
from .publishers import WeChatDraftPublisher
from .cover_image import generate_cover_image

__all__ = [
    "DigestItem", "EventCluster",
    "GitHubTrendingCollector", "HNFrontPageCollector",
    "HFTrendingCollector", "RSSCollector", "WebNewsIndexCollector",
    "WeChatDraftPublisher", "generate_cover_image",
]
```

- [ ] **Step 2: 精简 `defaults.py`**

移除 `SectionPicker`、`DigestComposer`、`ItemRanker`、`ClusterTagger`、`OutlineGenerator`、`ARKArticleWriter` 相关的所有导入和构建函数。只保留：
- `build_default_source_specs()` → 来源配置
- `build_default_collector()` → CompositeCollector
- `build_default_publisher()` → WeChatDraftPublisher
- `build_default_runner()` → 大幅精简，只构建 collector + publisher

- [ ] **Step 3: 简化 `cli.py`**

改为指向 tool_run 的入口：

```python
def main(argv=None):
    from .tool_run import main as tool_main
    return tool_main(argv)
```

- [ ] **Step 4: 简化 `__main__.py`**

```python
from .tool_run import main
if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 删除引用已删模块的测试文件**

同步删除：
- `tests/test_defaults_ark.py` — ARK 相关测试不再适用
- `tests/test_defaults_hot_pool.py` — 同上
- `tests/test_webapp_api.py` — 如依赖于 pipeline

- [ ] **Step 6: 运行测试验证**

```bash
python -m unittest discover -s tests -v
```

---

## Task 4：简化 webapp

**Files:**
- Modify: `ai_digest/webapp/app.py`
- Modify: `ai_digest/webapp/templates/index.html`（可选）
- Modify: `ai_digest/webapp/static/app.js`（可选）

**Sub-steps:**

- [ ] **Step 1: 重写 webapp 逻辑**

webapp 改为纯粹的"手动触发 + 结果查看"壳，不再依赖 pipeline：
- 点击"生成"时，Sisyphus 执行完整流程（collect → dedup → 分析 → 写作），结果 markdown 写回文件
- webapp 只负责读取已生成的文件、展示、编辑、提交发布

```python
# webapp/app.py (简化版)
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from ..settings import load_settings
from ..defaults import build_default_publisher
from ..publishers.wechat import markdown_to_html
from ..tool_run import collect_and_write  # 简化入口
from .storage import DraftStorage

def create_app():
    app = FastAPI()
    storage = DraftStorage(Path("data"))

    @app.post("/api/trigger")
    def trigger():
        """触发一次完整生成。实际由 Sisyphus 在 IDE 中手动执行。"""
        return {"status": "ok", "message": "请在 IDE 中运行 tool_run"}

    @app.get("/api/preview")
    def preview():
        return {
            "markdown": storage.read_markdown(),
            "html": storage.read_html() or markdown_to_html(storage.read_markdown()),
        }

    @app.post("/api/update")
    def update(payload: dict):
        storage.write_markdown(payload.get("markdown", ""))
        storage.write_html(markdown_to_html(payload.get("markdown", "")))
        return {"status": "ok"}

    @app.post("/api/publish")
    def publish():
        # 调用 publisher 工具脚本
        ...
```

- [ ] **Step 2: 更新前端指示**

在 webapp 首页加说明：生成流程需在 IDE 中通过 Sisyphus 完成，webapp 只用于编辑和发布。

---

## Task 5：编写 Skill

**Files:**
- New: `.claude/skills/ai-digest/SKILL.md`

**Skill 结构：**

```markdown
---
name: ai-digest
description: AI 开发者热点日报生成与公众号发布。Sisyphus 全权编排——抓取多源热点、去重、自行分析判断、撰写文章、发布到微信公众号。无固定模板，每日结构和风格由 Sisyphus 自行决定。
---

# AI Digest — Agent-Driven Workflow

## 可用工具脚本

所有工具通过 `python -m ai_digest.tool_run <command>` 调用：

| 命令 | 用途 | 输入/输出 |
|------|------|-----------|
| `collect` | 抓取全部来源热点 | stdout: JSON array of DigestItem |
| `dedup` | 跨运行去重 | stdin: JSON items → stdout: JSON filtered |
| `publish` | 提交公众号草稿 | stdin: markdown → stdout: JSON result |
| `cover` | 生成公众号封面图 | --title + --output → 图片文件 |

## 工作流

### 1. 收集数据
```bash
python -m ai_digest.tool_run collect > data/items.json
```
检查 errors（如有收集器失败在 stderr 输出）。

### 2. 去重
```bash
python -m ai_digest.tool_run dedup < data/items.json > data/filtered.json
```
去掉已发过的和历史记录中近期出现的目标。

### 3. 分析候选池
读取 data/filtered.json。自行判断：
- 今天有没有大新闻？
- 主线是行业动态还是开源项目？
- 哪些条目关联性强可以合并？
- 哪些只值得一句话带过？

### 4. 撰写文章
你（Sisyphus）自己写。约束：
- 中文 Markdown
- 标题必须点出今天最重要的判断
- 先给总判断再展开
- 不平均用力，有取舍
- 不使用"摘要：""价值：""为什么值得跟："等标签
- 只写你从候选池中看到的事实，不编造
- 长度不做硬性限制，但以"值得读"为标准
- **禁止使用代码块、表格、引用、HTML 标签**

### 5. 发布
```bash
cat data/article.md | python -m ai_digest.tool_run publish --title "xxx"
```

### 6. （可选）生成封面图
```bash
python -m ai_digest.tool_run cover --title "xxx" --output data/cover.jpg
```

## 关于微信发布的注意事项

- 微信文章支持 # / ## / ### 标题、段落、无序列表、加粗、链接、图片
- 不支持代码块、表格、引用、HTML 标签
- 图片需要引用可公开访问的 URL（GitHub avatar 等）
- 文章标题不要太长，公众号标题建议 12-24 字

## 去重要点

- `state.db` 记录了过去 7 天发过的内容和 URL
- 同一条内容通过 `dedupe_key` 或 URL 判断
- 同一条可以跨天发，但不要在同一天重复
- 如果某条非常重要但已发过，可以去 state.db 里把那条删掉再重跑

## 质量要求

- 信息准确，不编造
- 有判断和取舍
- 有自己的观察，不只是摘要堆砌
- 保持中文，语气专业克制
```

---

## 执行顺序

```
Task 1 (工具 CLI) → Task 2 (删模块) → Task 3 (清理引用) → Task 4 (简化webapp) → Task 5 (写Skill)
```

Task 1 必须先做，因为删掉 pipeline 后需要 Tool CLI 来维持 collect/publish 功能。
Task 2 和 Task 3 紧密关联，可以一起做。
Task 4 依赖 Task 1-3 完成。
Task 5 可以和其他任务并行准备，但最终写需要在代码清理完成后。

---

## 验证标准

1. `python -m ai_digest.tool_run collect` 成功的输出 JSON 列表
2. `python -m ai_digest.tool_run dedup` 能正确过滤
3. `python -m unittest discover -s tests -v` 剩余的测试全部通过
4. Sisyphus 加载 skill 后能完整走通从抓取到发布的流程
5. webapp 仍能预览和发布
