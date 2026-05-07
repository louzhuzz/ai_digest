---
name: ai-digest
description: AI 开发者热点日报生成与公众号草稿发布。Sisyphus 全权编排——调用工具脚本抓取多源热点、去重，自行分析判断、撰写文章、发布到微信公众号。无固定模板，每日结构和风格由 Sisyphus 自行决定。
---

# AI Digest — Agent-Driven Workflow

**架构**：Python 工具脚本（collect/dedup/publish/cards） + Sisyphus agent（分析/写作）。agent 调用工具脚本 API 完成数据获取和发布，自行完成新闻分析、时效过滤、搜索验证、文章撰写。

## 快速命令速查

```bash
# 全部 17 个来源并行收集
python -m ai_digest.tool_run collect

# 跨运行去重（stdin → stdout）
python -m ai_digest.tool_run dedup < data/items_collected.json

# 发布图文消息（--file 避免 PowerShell 编码问题）
python -m ai_digest.tool_run publish --title "今日标题" --file data/article.md

# 生成封面图
python -m ai_digest.tool_run cover --title "今日标题" --out data/cover.png

# 持久化去重状态
python -m ai_digest.tool_run persist < data/items_deduped.json

# 贴图卡片生成 + 发布
python -m ai_digest.tool_run cards --input data/cards.json --output-dir data/cards
python -m ai_digest.tool_run publish-newspic --title "AI 速递" --image-dir data/cards --content-file data/content.txt
```

## ⚠️ 编码必读（Windows PowerShell）

PowerShell 的 `>` 重定向输出 UTF-16 LE，`|` 管道用 GBK 破坏 UTF-8 JSON。两条铁律：

```
# ❌ 绝不能做的事
python -m ai_digest.tool_run collect | python -m ai_digest.tool_run dedup   # 管道破坏中文
Get-Content data/article.md | python -m ai_digest.tool_run publish          # GBK 编码读 UTF-8

# ✅ 正确做法
python -m ai_digest.tool_run publish --title "标题" --file data/article.md  # --file 参数直接读 UTF-8
json.loads(Path("data/items.json").read_bytes())                            # 二进制读取绕过文本模式
sys.stdout.buffer.write(output.encode("utf-8"))                             # stdout 中文用二进制模式
```

## 完整工作流（7 步）

### Step 1: Collect（自动来源分级）

```python
from ai_digest.defaults import build_default_collector
collector = build_default_collector()
items = collector.collect()
# items = list[DigestItem]，网络超时/403 是常态，检查 collector.errors
```

`cmd_collect()` 自动执行来源分级过滤，写入 `data/items_collected.json`：
- **HIGH 来源**（全量保留）：GitHub Trending / Hacker News / HuggingFace / OpenAI / Anthropic / Google AI / DeepMind / DeepLearning AI
- **MEDIUM 来源**（命中 AI 关键词后保留）：机器之心 / 新智元 / 量子位 / 雷锋网 / 爱范儿 / CSDN AI / 橘鸦 RSS / Solidot / InfoQ / iThome
- **补充通道**：DeepSeek / Qwen / 智谱 GitHub Releases RSS

默认关键词：`AI, 大模型, LLM, 开源, GPT, DeepSeek`。通过 `AI_DIGEST_KEYWORDS` 环境变量自定义。

### Step 2: Dedup（跨运行去重）

```python
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings

settings = load_settings()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
deduper = RecentDedupeFilter(state_store=store)
filtered = deduper.filter(items)  # list[DigestItem]，不是 list[dict]
```

双轨去重：URL 精确匹配 + simhash 64-bit 近似匹配（Hamming ≤ 3），7 天窗口。150-200 条原始数据通常剩 30-40 条。

### Step 3: AI Time Filter + Verify（严格）

**时效过滤**（硬规则）：
- 只保留 `published_at` 在 48 小时内的新闻。否则直接丢弃。
- ⚠️ 工具脚本抓取的 `published_at` 可能是采集时间。用 `webfetch` 打开原文核实实际发布日期。

**事实验证**（不可跳过）：
- 每条关键新闻打开原文，确认标题、日期、关键数据。
- 重要 claim 只在单一信源出现时，webfetch 到路透/TechCrunch 等交叉验证。

### Step 4: Analyze & Think

读 `data/items_collected.json`（dedup 后），自主决定：
- 今日主线是什么？模型发布？融资动态？开源项目？
- 哪些新闻可以分组？哪些值得展开、哪些一句话带过？
- 这是你的判断——没有排序公式，没有来源配额。

### Step 5: Plan Illustrations（配图规划）

**写正文前决定配图方案**。配图是文章正文的插图（不是封面），密度 3-5 张（balanced）。

**来源优先级**（从高到低）：

1. **PPT 截图**（数据对比/架构图/关键数字）：`pptx` skill 生成一页 PPT → LibreOffice 转 PDF → PyMuPDF 转 PNG → 上传微信 CDN
2. **浏览器截图**（GitHub 项目优先）：Playwright 打开 `github.com/user/repo` 截图，`look_at` 验证内容
3. **真实产品图/新闻图**：og:image 验证后使用，必须 `webfetch` 确认 HTTP 200
4. **封面图**：`cover_image.py`（PIL），命令 `tool_run cover --title "..." --out data/cover.png`
5. **AI 生图**（保底）：`dashscope_image`，`qwen-image-2.0-pro`

**PPT 截图流程**：
```python
import subprocess, fitz
subprocess.run(['C:\Program Files\LibreOffice\program\soffice.exe',
    '--headless', '--convert-to', 'pdf', '--outdir', 'data', 'data/slide.pptx'])
doc = fitz.open('data/slide.pdf')
mat = fitz.Matrix(2, 2)
pix = doc[0].get_pixmap(matrix=mat)
pix.save('data/slide.png')
```

**关键规则**：
- 每篇文章必须准备封面 + 正文配图（3-5 张），缺一不可
- 每种配图生成后必须验证可访问。不可访问→退回 PPT 截图方案
- 本地文件（file:///）不能写进文章，必须先上传微信 CDN
- `publish` 会调用 `image_uploader.upload_all()` 自动处理 HTTP URL

### Step 6: Write Article

**Option A: 图文消息（Markdown）**

你自主撰写。约束：

- **标题** 12-24 字，具体到当日事件。不泛化（❌「每日新闻速递」✅「DeepSeek 开源 V4」）
- **结构**：开头直接给结论。主体 2-3 个重点展开，其他一笔带过。结尾一句总结 + 独立判断。
- **行文**：像人写的，不是机器写的。禁用「让我们」「值得注意的是」「毋庸置疑」等 AI 指纹。每段不超 3 句话。每段回答「开发者为什么要关心？」
- **数据**：有数字比没数字有说服力。数字加粗 `WordBench **98%**`。
- **GitHub 项目推荐**：每天至少一个。格式 `## 🛠️ 项目名` → 3-5 句：解决什么问题 + 为什么推荐。
- **Markdown 支持**：`#`/`##`/`###` 标题、`` ``` `` 代码块（语法高亮）、`|` 表格、`>` 引用、`> [!tip]` callout、`:::` 围栏容器。外链自动转脚注。CJK+英文自动空格。
- **配图**：`![描述](cdn_url)`。publish 时自动上传 CDN 并渲染为 `<img>`。

**Option B: 贴图卡片（newspic）**

创建 `data/cards.json`，每张卡用以下四行格式 + JSON 块：

```
# [主标题]
## [卡片标题]
desc: [30-50字描述，**数字**加粗，`英文术语`代码]
[material_icon_name]
{ JSON块 }
```

支持 10 种卡片模板：`cover` / `content` / `list` / `data` / `compare` / `closing` / `content-grid` / `content-hero` / `content-steps` / `content-quote`。每种模板的 `card_type` 和字段见下文。

物料图标（snake_case）：
`stars` `trending_up` `whatshot` `bolt` `analytics` `bar_chart` `code` `terminal`
`format_quote` `format_list_bulleted` `check_circle` `dashboard` `grid_on`
`psychology` `auto_awesome` `science` `explore` `insights`

### Step 7: Publish

**图文消息**：
```bash
python -m ai_digest.tool_run publish --title "Your Title" --file data/article.md
```

**贴图发布**（首先生成卡片 PNG）：
```bash
# 清理旧文件
python -c "import shutil; shutil.rmtree('data/cards', ignore_errors=True)"
# 生成卡片 PNG
python -m ai_digest.tool_run cards --input data/cards.json --output-dir data/cards
# 发布贴图草稿
python -m ai_digest.tool_run publish-newspic --title "标题" --image-dir data/cards --content-file data/content.txt
```

### Step 8: Persist（必须执行）

**发布后立即执行**，否则今天去重的新闻明天会重新出现。

```python
deduper.persist(filtered, now=datetime.now(timezone.utc))  # filtered = step2 去重结果
```

---

## 行文与配图风格总览

### 标题规则
- 12-24 字，具体到当日事件
- 类型：日期型（AI日报 3/22）、摘要型（标题即目录）、主题标签型（【AI日报】核心事件）
- ❌ 禁用：`每日新闻速递`、`AI 日报`（作为标题）、`今日资讯`

### 行文规则
- **删除 AI 味**：禁用「让我们」「在这个时代」「值得注意的是」「毋庸置疑」
- **段落**：每段 ≤ 3 句，短句为主。手机端友好。
- **开头**：直接给结论。「今天发生了什么」而非「在 AI 技术飞速发展的今天…」
- **节奏**：主体 2-3 个重点展开，其余一笔带过。结尾独立判断，不说「以上就是今日内容」
- **专业克制**：不自嗨、不营销、有观点。风格统一。

### 配图风格
- **优先级**：PPT 截图（数据/架构）> Playwright 截图（GitHub/页面）> og:image（验证后）> 封面图 > AI 生图
- **密度**：balanced 3-5 张。每个主题一张，不是每段都插。留白比堆图专业。
- **来源参考**：

| 类型 | 方案 | 说明 |
|------|------|------|
| 数据图表/架构图 | PPT 截图 | 质量可控、永不失效 |
| GitHub 项目 | 浏览器截图 | 显示星标+描述+Release |
| 产品发布/推文 | 浏览器截图 | 所见即所得 |
| 模型 logo | og:image | 验证 HTTP 200 后使用 |
| 新闻事件图 | og:image | 需验证防反爬 |
| **封面图** | `cover_image.py` PIL | 2.35:1 比例，自动字号 |

> ⚠️ 所有图片 URL 必须验证可下载。失效→退回 PPT 截图方案。

---

## Python API 速查

```python
# Collect
from ai_digest.defaults import build_default_collector
items = build_default_collector().collect()  # list[DigestItem]

# Dedup
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings
settings = load_settings()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
filtered = RecentDedupeFilter(state_store=store).filter(items)

# Persist
deduper.persist(filtered, now=datetime.now(timezone.utc))

# Publish
# python -m ai_digest.tool_run publish --title "标题" --file data/article.md

# Cover
from ai_digest.cover_image import generate_cover_image
data = generate_cover_image("今日标题", subtitle="可选")

# Cards
from ai_digest.image_card_generator import generate_cards
paths = generate_cards("data/cards.json", "data/cards")  # list[Path]

# Access Token
from ai_digest.auth import WeChatAccessTokenClient
token = WeChatAccessTokenClient(appid=..., appsecret=...).get_access_token()
```

## 贴图卡片模板

可选模板及 JSON 字段：

| card_type | 用途 | 关键字段 |
|-----------|------|----------|
| `cover` | 封面钩子 | title(支持\n), subtitle, body, footer_note |
| `content` | 正文内容 | title, body, highlight_text |
| `list` | 列表/时间轴 | title, items[{keyword,desc}], body |
| `data` | 数字仪表盘 | title, data_value, data_label, body |
| `compare` | 双栏对比 | title, items[{name,tag,value,highlight}] |
| `closing` | 结尾引导 | title, body, highlight_text |
| `content-grid` | 四宫格 | title, items[{label,value,desc}] |
| `content-hero` | 大字报 | title, data_value, data_label, body |
| `content-steps` | 步骤流 | title, items[{label,desc}] |
| `content-quote` | 引言卡片 | title, subtitle, body, highlight_text |

所有卡必须有 `card_type`。非 cover 卡必须有 `page_num`（从 1 开始连续编号）。

## 去重说明

- 状态库：`data/state.db`（SQLite，7 天窗口）
- 双轨：URL exact match + simhash 64-bit（hamming ≤ 3）
- 同一条新闻不会在同一天重复出现，也不会连续两天出现
- 如需重新收录某条历史新闻，从 `data/state.db` 删除对应行

## Quick One-Shot

```python
from ai_digest.defaults import build_default_collector
from ai_digest.dedupe import RecentDedupeFilter
from ai_digest.state_store import SqliteStateStore
from ai_digest.settings import load_settings
from datetime import datetime, timezone

# Step 1+2
settings = load_settings()
items = build_default_collector().collect()
store = SqliteStateStore(settings.state_db_path)
store.initialize()
deduper = RecentDedupeFilter(state_store=store)
deduped = deduper.filter(items)

# Step 3-6: AI 自行完成（无固定规则）

# Step 7: 发布（CLI 命令）
#   python -m ai_digest.tool_run publish --title "标题" --file data/article.md

# Step 8: 持久化（必须）
deduper.persist(deduped, now=datetime.now(timezone.utc))
```

## Quality Notes

- **时效是生命线**。只写 48 小时内。宁可少写，不可写旧。
- **验证，不要转载**。每条重要新闻打开原文确认。
- **搜索是 agent 的职责**。工具脚本抓不到的，你去搜。网络错误不是放弃的理由。
- **有观点，不只做摘要**。每段回答「开发者为什么要关心」。
- **专业克制**。读者是 AI/ML 工程师，假设其技术能力。
