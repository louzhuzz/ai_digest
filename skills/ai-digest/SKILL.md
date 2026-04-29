---
name: ai-digest
description: AI 开发者热点日报生成与公众号草稿发布。Sisyphus 全权编排——调用工具脚本抓取多源热点、去重，自行分析判断、撰写文章、发布到微信公众号。无固定模板，每日结构和风格由 Sisyphus 自行决定。
---

# AI Digest — Agent-Driven Workflow

## Available Tool Scripts

All tools via `python -m ai_digest.tool_run <command>`:

| Command | Description | Input/Output |
|---------|-------------|-------------|
| `collect` | Fetch all sources | stdout: JSON items |
| `dedup` | Cross-run dedup | stdin JSON → stdout filtered |
| `persist` | Save dedup state to SQLite | stdin JSON |
| `publish` | Submit WeChat draft | stdin markdown → JSON result |
| `cover` | Generate cover image | `--title`, `--output` |

## Workflow

### 1. Collect Data

```bash
python -m ai_digest.tool_run collect > data/items.json
```

Check stderr for collector errors (some sources may time out — that's normal).

### 2. Deduplicate

```bash
python -m ai_digest.tool_run dedup < data/items.json > data/filtered.json
```

Remove items already published within 7 days.

### 3. AI Check: Time Filtering (REQUIRED)

**Before any analysis, filter by date.** This is your single biggest source of error.

- Discard items older than **3 days** (`published_at` < today - 3d). They are not "today's news."
- If you choose to include an older item (for context/background), **explicitly note its date** in the article.
- Tip: tools like `webfetch` can be used to check an article's actual publish date if the `published_at` field looks wrong.

### 4. AI Search & Verify (REQUIRED)

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

### 5. Analyze & Think

Read `data/filtered.json` **plus your own search findings**. You decide:

- What's the main theme today? Model releases? Open-source projects? Industry moves?
- Which items are related and should be grouped?
- Which ones are worth expanding vs. mentioning in passing?

This is **your judgment call** — no more ranking formulas or section quotas.

### 6. Write the Article

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

Supported markdown (WeChat-compatible):
```
# Title
## Section heading
### Subsection
Paragraph text
- Unordered list item
1. Ordered list item
**Bold text**
[Link text](url)
![Alt](image-url)
```

### 7. Save Article

```bash
cat > data/article.md << 'ARTICLE'
# Your title here

Your article content...
ARTICLE
```

### 8. Publish

```bash
cat data/article.md | python -m ai_digest.tool_run publish --title "Your Title"
```

Output: `{"draft_id": "xxx"}` on success, `{"error": "..."}` on failure.

### 9. Persist Dedup State

```bash
python -m ai_digest.tool_run persist < data/filtered.json
```

Always do this after publishing so the same items won't be collected again tomorrow.

### 10. (Optional) Cover Image

```bash
python -m ai_digest.tool_run cover --title "Your Title" --output data/cover.jpg
```

## Quick One-Shot

For a fast publish cycle:

```bash
python -m ai_digest.tool_run collect > data/items.json
python -m ai_digest.tool_run dedup < data/items.json > data/filtered.json

# STEP 1: Filter by date (discard items > 3d old)
# STEP 2: Search & verify (webfetch key articles, web search for missed news)
# STEP 3: Write article with your findings
# STEP 4: Publish + persist

cat data/article.md | python -m ai_digest.tool_run publish --title "Your Title"
python -m ai_digest.tool_run persist < data/filtered.json
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
