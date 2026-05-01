---
name: ai-digest
description: AI 开发者热点日报生成与公众号草稿发布。Sisyphus 全权编排——调用工具脚本抓取多源热点、去重，自行分析判断、撰写文章、发布到微信公众号。无固定模板，每日结构和风格由 Sisyphus 自行决定。
---

# AI Digest — Agent-Driven Workflow

## Overview

**架构**：Python 工具脚本（collect/dedup/publish/cards） + Sisyphus agent（分析/写作）。agent 调用工具脚本 API 完成数据获取和发布，自行完成新闻分析、时效过滤、搜索验证、文章撰写。

**⚠️ 关键：不要使用 PowerShell 管道 `|` 传输 JSON。** PowerShell 管道会用 GBK 编码破坏中文数据。所有数据操作请使用下方 Python API 示例。

## Python API Reference

以下函数的 import 路径均在 `ai_digest` 包内（如 `from ai_digest.defaults import build_default_collector`）。

### Collect（收集全部来源）

```python
from ai_digest.defaults import build_default_collector
from ai_digest.models import DigestItem

collector = build_default_collector()  # 无参数
items = collector.collect()  # list[DigestItem]
# 检查错误：collector.errors
```

### Dedup（跨运行去重，7天窗口）

```python
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings

settings = load_settings()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
deduper = RecentDedupeFilter(state_store=store)  # 无参 window_days 默认 7

filtered = deduper.filter(items)  # items 是 list[DigestItem]，不是 list[dict]
```

**⚠️ 必须传 `list[DigestItem]`，不是 `list[dict]`。** 工具脚本 `tool_run collect` 输出的 JSON 包含 serialized DigestItem，需要反序列化后传给 dedup。

### Persist（持久化去重状态）

```python
deduper.persist(filtered)  # filtered 是 deduper.filter() 的返回值
```

### Publish（图文消息）

```python
# 推荐 --file 参数，避免 PowerShell 管道编码问题
python -m ai_digest.tool_run publish --title "今日标题" --file data/article.md
```

### Publish-newspic（贴图）

```bash
python -m ai_digest.tool_run publish-newspic --title "AI 速递" --image-dir data/cards \
  --content-file data/content.txt --dry-run  # 先 dry-run 验证
```

### Cards（生成贴图卡片 PNG）

```python
from ai_digest.image_card_generator import generate_cards

cards = generate_cards("data/cards.json", "data/cards")  # -> list[Path] 文件路径
```

⚠️ 生成前先清理 `data/cards/` 目录，避免旧文件混入。详见 Step 7。

### Cover（封面图）

```python
from ai_digest.cover_image import generate_cover_image

data = generate_cover_image("今日标题")  # -> bytes (PNG)
with open("data/cover.png", "wb") as f:
    f.write(data)
```

## Workflow（完整流程）

### Step 1: Collect

```python
import json, sys
from ai_digest.defaults import build_default_collector

collector = build_default_collector()
items = collector.collect()

# 序列化到文件（需要 datetime → ISO string）
from dataclasses import asdict
from datetime import datetime

def serialize(item):
    d = asdict(item)
    if isinstance(d.get("published_at"), datetime):
        d["published_at"] = d["published_at"].isoformat()
    return d

with open("data/items.json", "w", encoding="utf-8") as f:
    json.dump([serialize(i) for i in items], f, ensure_ascii=False, indent=2)
```

### Step 2: Dedup

```python
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings
from ai_digest.models import DigestItem
from datetime import datetime

# 读取 collect 输出并反序列化为 DigestItem 对象
with open("data/items.json", "r", encoding="utf-8") as f:
    raw = json.load(f)
items = []
for d in raw:
    if isinstance(d.get("published_at"), str):
        d["published_at"] = datetime.fromisoformat(d["published_at"])
    items.append(DigestItem(**d))

# 执行去重
settings = load_settings()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
deduper = RecentDedupeFilter(state_store=store)
filtered = deduper.filter(items)
print(f"Dedup: {len(items)} → {len(filtered)} items")
```

### Step 3: AI Time Filtering (REQUIRED)

**Before any analysis, filter by date.** This is your single biggest source of error.

- Discard items older than **3 days** (`published_at` < today - 3d). They are not "today's news."
- If you choose to include an older item (for context/background), **explicitly note its date** in the article.
- Tip: tools like `webfetch` can be used to check an article's actual publish date if the `published_at` field looks wrong.

### Step 4: AI Search & Verify (REQUIRED)

**Do not passively accept collector output.** The collector is a starting point. You must:

- **Verify facts** from the original source. Use `webfetch` to open key articles and confirm title/date/quotes.
- **Search for news the collector missed.** Use `MiniMax_web_search` to find breaking news, trending topics, and Chinese AI news that the collector might have failed to fetch (many sources time out or return 403).
- **Cross-reference** important claims. If a claim appears only in one source, verify it independently.
- **Log your search** — note which items you verified and which you added from search.

Search queries to consider:
- Latest model releases (DeepSeek, Qwen, Kimi, Claude, GPT)
- Chinese AI industry news from last 24 hours
- GitHub trending AI projects
- Open-source releases

### Step 5: Analyze & Think

Read `data/filtered.json` **plus your own search findings**. You decide:

- What's the main theme today? Model releases? Open-source projects? Industry moves?
- Which items are related and should be grouped?
- Which ones are worth expanding vs. mentioning in passing?

This is **your judgment call** — no more ranking formulas or section quotas.

### Step 6: Write Article or Card Content

**Option A: Write markdown article（图文消息）**

You write it. Constraints:

- **Chinese Markdown**. Title must state today's key judgment.
- Start with a **lede** (overall take), then expand.
- **Don't cover everything equally**. Pick 2-3 main points, mention others briefly.
- No code blocks, tables, blockquotes, or HTML tags.
- No labels like "摘要:", "价值:", "为什么值得跟:" — just natural prose.
- **Only use facts you have verified**. If you're unsure, say so or skip it.
- **Explicitly mention dates** for any item that is not from today.
- Title should be 12-24 characters, specific to today, not generic.
- Professional tone, not marketing or colloquial.

**Option B: Create card data（贴图/newspic）**

Create `data/cards.json` — an array of card objects. Card types: `cover` | `content` | `list` | `data` | `compare` | `closing`

```json
[
  {
    "card_type": "cover",
    "title": "今日 AI 热点",
    "subtitle": "AI DAILY DIGEST",
    "body": "2026.05.01",
    "footer_note": "AI 开发者日报"
  },
  {
    "card_type": "content",
    "page_num": 1,
    "title": "重点新闻",
    "body": "正文内容...",
    "highlight_text": "关键信息"
  },
  {
    "card_type": "closing",
    "title": "今日总结",
    "body": "一句话总结今天",
    "highlight_text": "关注公众号获取每日更新"
  }
]
```

### Step 7: Generate Cards (贴图 Only)

**⚠️ 生成前必须清理旧文件，否则会把历史测试图片一起上传到微信草稿箱。**

```python
import shutil, os
cards_dir = "data/cards"
if os.path.exists(cards_dir):
    shutil.rmtree(cards_dir)  # 清空旧卡片 PNG
```

```bash
python -m ai_digest.tool_run cards --input data/cards.json --output-dir data/cards
```

Output: `{"cards": ["data/cards/card_01.png", ...], "count": N}`

### Step 8: Publish

**Option A: 图文消息**

```bash
python -m ai_digest.tool_run publish --title "Your Title" --file data/article.md
```

**Option B: 贴图 (newspic)**

```bash
# 写正文到文件（纯文本，不支持 HTML）
python -c "open('data/content.txt','w',encoding='utf-8').write('今日要点...')"

# 发布
python -m ai_digest.tool_run publish-newspic --title "AI 速递" --image-dir data/cards \
  --content-file data/content.txt
```

Output: `{"draft_id": "xxx"}` on success, `{"error": "..."}` on failure.

> ⚠️ **不要用** `Get-Content | python` 或 `cat | python`，PowerShell 会用 GBK 编码读 UTF-8 文件导致中文乱码。永远用 `--file` 参数或 Python `open(..., encoding="utf-8")`。

### Step 9: Persist Dedup State

**必须在发布后执行**，否则相同新闻明天会被重复抓取。

```python
deduper.persist(filtered)  # filtered 是 Step 2 的去重结果
```

## Quick One-Shot（完整 Python 流程）

```python
# collect
from ai_digest.defaults import build_default_collector
collector = build_default_collector()
items = collector.collect()

# dedup
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings
settings = load_settings()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
deduper = RecentDedupeFilter(state_store=store)
filtered = deduper.filter(items)

# → 此时 agent 执行时效过滤、搜索验证、撰写文章或卡片数据

# persist（发布后调用）
deduper.persist(filtered)
```

## Using the Webapp

After saving the article to `data/`:

```bash
python -m ai_digest.webapp.app
# Open http://127.0.0.1:8010
```

The webapp lets you preview the rendered HTML, edit markdown, and publish. But the generation/analysis step is done here in the IDE.

## Dedup Notes

- State stored in `data/state.db` (SQLite, 7-day window).
- Items with same `dedupe_key` or URL within 7 days will be filtered out.
- Same item can appear on different days, but not same day.
- If something important was already published and you want to re-include, manually delete its row from `data/state.db`.

## Quality Notes

- **时效性是生命线。** 日报不是周报，超过 3 天的新闻必须标记日期或干脆不用。
- **验证，不要转载。** 每条重要新闻都要打开原文确认标题、日期、关键数据。从搜索补进的新闻也要打开原文核实。
- **搜索是 agent 的职责。** 工具脚本抓不到的东西，你去搜。网络超时、403、DNS 失败是常态，不是放弃的理由。
- Be accurate. Don't fabricate facts, figures, or links.
- Have an opinion. Don't just summarize — say what matters.
- Every paragraph should answer "why should a developer care?"
- Professional, restrained tone. No emojis unless the content genuinely calls for it.
- The reader is an AI/ML engineer. Assume technical competence.
