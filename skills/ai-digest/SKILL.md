---
name: ai-digest
description: AI 开发者热点日报生成与公众号草稿发布。Sisyphus 全权编排——调用工具脚本抓取多源热点、去重，自行分析判断、撰写文章、发布到微信公众号。无固定模板，每日结构和风格由 Sisyphus 自行决定。
---

# AI Digest — Agent-Driven Workflow

**架构**：Python 工具脚本（collect/dedup/publish/cards） + Sisyphus agent（分析/写作）。agent 调用工具脚本 API 完成数据获取和发布，自行完成新闻分析、时效过滤、搜索验证、文章撰写。

## 内容导航

- **第一章 AI 日报**：多源热点收集 → 去重 → 时效过滤 → AI 验证 → 写作 → 发布（完整流水线）
- **第二章 GitHub 项目分享帖**：独立功能，推荐一个 GitHub 项目，自主撰写 + 发布

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

# GitHub 项目分享帖（独立功能）
python -m ai_digest.tool_run github-share --repo owner/repo          # 获取数据，stdout 输出 JSON
# Sisyphus 拿到 JSON 后自主撰写文章，再调用 publish --file 发布
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

## 常见问题与避坑

### Collect 阶段
- **`published_at` 不准确**：多数采集器拿不到原文发布时间，会写入采集时间。时效过滤必须 `webfetch` 打开原文逐个核实，不能信任字段值。
- **网络错误是常态**：17 个来源中总有 3-5 个超时或 403。查 `collector.errors` 确认，不影响其他来源。
- **橘鸦（Juya RSS）是最高优先级来源**：橘鸦是中文 AI 圈最全面的每日动态聚合器，聚合范围覆盖机器之心、量子位、极客公园、爱范儿、晚点等数十个中文科技媒体。**每天采集到的 AI 日报类内容 70% 来自橘鸦**，它是中文 AI 热点覆盖率最高的单一来源。其价值远高于独立抓取的机器之心/新智元等（因为这些已经在橘鸦内），重点阅读橘鸦的 `summary` 字段判断当日主线。

### 时效过滤阶段
- **用 `webfetch` + MiniMax_web_search 交叉验证**：重要新闻只在一个信源出现时，去路透/TechCrunch 等确认。同一新闻在不同信源中数据可能不一致（融资额、日期）。
- **硬规则**：超过 48 小时直接丢弃。不因为"这条很重要"而放宽。宁可少写不可写旧。
- **新闻优先级**：**模型更新/新发布 > 融资/人事变动**。GPT/Gemini/Claude/DeepSeek 等新模型推出或版本更新是最核心的新闻，必须优先处理；融资、人事变动、战略合作等次之。不要让次要新闻占用主要篇幅。
- **⚠️ 时效性红线（最易犯错）**：collector 收集的 `published_at` 字段是**采集时间**，不是**新闻发布日期**。5月10日采集到的新闻，实际发布日期可能是5月7日、5月8日甚至更早。**绝对不能因为"今天采集到了"就当成"今天发生的"**。每条新闻必须用 `webfetch` 打开原文核实实际发布日期，超过48小时一律丢弃。

### 配图阶段
- **本地文件不可用**：`file:///` 路径不能直接写入文章。所有图片必须先上传微信 CDN（`uploadimg` 接口），用 `mmbiz.qpic.cn` URL 插入。
- **微信图片上传用 `type=image`**：不是 `type=thumb`（thumb 是封面缩略图专用接口），非封面图必须用 `cgi-bin/material/add_material?type=image`。
- **PPT 配图必须遵循 pptx skill**：加载 `skill("pptx")` 获取完整规范，包括设计系统、anti-AI cliché 规则、CJK 布局陷阱、QA 检查。**不允许**用固定模板或 python-pptx 硬编码生成——每张都应按 pptx skill 的设计流程独立制作。
- **LibreOffice 渲染缓存**：覆盖 `.pptx` 源文件后重新 PDF 可能不更新（文件大小不变）。删除旧 PDF + 清理 `%TEMP%\lu*` 目录可解决。
- **QA 验证不可缺**：PPT 转 PNG 后必须做视觉检查（子代理 inspect 图片），查重叠/溢出/低对比度。有缺陷则修复→重渲染→再查，至少完成一轮 fix-and-verify。
- **Publish 只处理 HTTP URL**：`upload_all()` 只处理 `![]()` 中的 `http://`/`https://` 图片。本地 PNG 需手动调用 `_upload_single()` 或直写 multipart/form-data 上传。

### 写作阶段
- **⚠️ BOM 破坏标题渲染**：PowerShell `Set-Content` 默认加 UTF-8 BOM（`\ufeff`），导致 `# 标题` 被 markdown 解析为 `<p>` 而非 `<h1>`。所有样式失效。解决：写文件用 `-NoNewline` 参数，或 `wechat_renderer.render()` 已内置 `text[0] == '\ufeff'` 剥离。
- **列表空行产生幽灵圆点**：markdown 中两个 `- item` 之间空一行，会生成两个独立的 `<ul>` 块，微信渲染时中间出现单独圆点。必须确保 list item 之间无空行。
- **`li` 间距**：`margin-bottom` 设太大会在微信中制造空行感。建议 ≤ 2px。
- **标题封面字号**：标题超过 10 个字时封面图可能截断。`cover_image.py` 的 `_auto_size_title` 从 64px 向下适配，但 2 行以上效果不佳。标题尽量控制在 16 字内。

### 发布阶段
- **不要用 `|` 或 `>`**：任何涉及中文的管道操作一律用 `--file` 参数。
- **`--title` 必须非空**：`publish` 命令的 `--title` 参数若为空或省略，`digest` 字段会为空，微信 API 返回 `[44004] empty content hint` 错误。发布命令必须带 `--title "具体标题"`。
- **发布后检查草稿**：webfetch 草稿预览链接确认排版正常、图片可显示。

### 渲染阶段（wechat_renderer.py）
- **微信不尊重 `<pre>` 的 white-space**：不能用常规浏览器 `<pre>` 保空白方案。所有主流微信 Markdown 编辑器均采用 `<br>` + `&nbsp;` 硬编码格式。`process_code_blocks` 在 pygments 高亮后自动将 `\n` → `<br>`、空格 → `&nbsp;`。
- **macOS 三色圆点**：代码块顶部自动嵌入红/黄/绿 SVG 圆点（类似 Xcode/VS Code 风格）。
- **`nl2br` 已移除**：不再使用 `md_to_html` 的 `nl2br` 扩展，它会在表格、列表、引用中插入多余 `<br>` 导致微信显示空行。
- **代码块使用浅色 `#f8fafc` 背景 + 14px 字号**，区别于行内代码的蓝色背景。
- **外链自动转为 `[n]` 脚注**：微信发布后外链不可点击，renderer 自动收集所有非微信链接 → 去重编号为 `[1]`、`[2]`… 上标 → 文末 "📎 参考来源" 区列出完整 URL。同一 URL 复用编号。

### 持久化阶段
- **Windows 下 `dedup` 用文件输入，不用 stdin 管道**：PowerShell 的 `|` 管道会破坏 UTF-8 编码。正确做法：`python -m ai_digest.tool_run dedup < data/items_collected.json`（重定向）。
- **`persist` 必须在发布后立即执行**：否则今天去重的新闻明天会重新出现。

## 完整工作流（7 步）

### Step 1: Collect（自动来源分级）

```python
from ai_digest.defaults import build_default_collector
collector = build_default_collector()
items = collector.collect()
# items = list[DigestItem]，网络超时/403 是常态，检查 collector.errors
```

`cmd_collect()` 自动执行来源分级过滤，写入 `data/items_collected.json`：
- **HIGH 来源**（全量保留）：GitHub Trending / Hacker News / HuggingFace / OpenAI / Anthropic / Google AI / DeepMind / DeepLearning AI / **橘鸦 RSS**（中文圈每日 AI 动态聚合器，涵盖机器之心、量子位、爱范儿等数十个中文科技媒体，信息密度极高，是中文 AI 资讯的最佳单一入口）
- **MEDIUM 来源**（命中 AI 关键词后保留）：机器之心 / 新智元 / 量子位 / 雷锋网 / 爱范儿 / CSDN AI / Solidot / InfoQ / iThome
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
- 只保留**当天**和**前一天 12:00 之后**发布的新闻，其他一律丢弃。
  - 例：今天 5 月 10 日 → 保留 5 月 9 日 12:00 之后 + 5 月 10 日全天；5 月 9 日 11:59 及更早的全部丢弃。
- ⚠️ 工具脚本抓取的 `published_at` 可能是采集时间。用 `webfetch` 打开原文核实实际发布日期。
- **⚠️ 最易犯错场景**：collector 返回的 JSON 里 `published_at` 字段显示今天日期（因为是今天采集的），但原文实际发布于 2-3 天前。**绝对不能因为 JSON 里写着今天的日期就当成今天的新闻**。必须 webfetch 验证原文页面的真实日期。

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

**PPT 截图流程（必须遵循 pptx skill）**：

> ⚠️ 必须加载并使用 `pptx` skill 完成 PPT 制作，不允许跳过其设计系统、QA 等步骤直接用 python-pptx 或固定模板生成。

1. **加载 pptx skill**（`skill("pptx")`），获取完整设计规范
2. **定义设计系统**（遵循 pptx skill Step 2）：
   - pick a bold, content-informed color palette（色彩必须与当前主题相关，不可默认蓝色）
   - header/body CJK 字号：标题 48-64pt，正文 22-28pt，数字强调 60-72pt
   - CJK 字体选择：`Microsoft YaHei`（正文）/ `SimHei` 或 `Source Han Sans`（标题）
   - 避免 pptx skill 列出的 anti-AI cliché 项：渐变、装饰线、emoji 自由使用、彩条卡片边框
3. **逐张创建 PPTX**（每张配图一个独立 .pptx 文件）：
   - 每页设计应有视觉元素（形状、色块、数据框），不写纯文字
   - 数据类配图使用 Large stat callout（60-72pt 大数字 + 小标签）
   - 严格遵循 **anti-AI cliché** 规则：无渐变背景、无彩色边框卡片、无 Inter/Roboto 字体
   - CJK 布局注意：不用负 margin 叠加大段中文
4. **幻灯片 → PNG**：
   ```python
   import subprocess, shutil, os, glob
   
   for pptx_file in glob.glob('data/slide_*.pptx'):
       name = os.path.splitext(os.path.basename(pptx_file))[0]
       # 清理 LibreOffice 缓存（避免复用旧 PDF）
       for d in glob.glob(os.path.join(os.environ.get('TEMP', '/tmp'), 'lu*')):
           shutil.rmtree(d, ignore_errors=True)
       # PPTX → PDF
       subprocess.run(['soffice', '--headless', '--convert-to', 'pdf',
           '--outdir', 'data', pptx_file])
       # PDF → PNG（2x = 1080p @ 192 DPI）
       import fitz
       doc = fitz.open(f'data/{name}.pdf')
       doc[0].get_pixmap(matrix=fitz.Matrix(2, 2)).save(f'data/{name}.png')
   ```
5. **QA（pptx skill Step 3 必做）**：
   - 用 markitdown 检查每张 PPT 文本正确性：`python -m markitdown data/slide_*.pptx`
   - 视觉检查（使用子代理 inspect 图片）：不要凭代码判断，必须看渲染结果
   - 检查项：文本溢出、元素重叠、低对比度、衬线装饰线与二行标题碰撞
   - 有缺陷 → 回到第 3 步修复 → 重新渲染 → 再次检查
6. **上传微信 CDN**（`httpx` multipart → `uploadimg` 接口），验证返回的 `mmbiz.qpic.cn` URL 可访问

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
- **⚠️ 列表空行**：`- ` 开头的 list item 之间**绝对不能有空行**。空行会被 `wechat_renderer.py` 识别为多个 `<ul>` 块，每个块独立渲染出圆点，产生 ghost bullet。正确写法：连续 `- ` 行，中间无空行。例：`- item1\n- item2\n- item3`（✅），`- item1\n\n- item2`（❌ 会产生两个圆点）

### 配图风格
- **优先级**：PPT 截图（数据/架构）> Playwright 截图（GitHub/页面）> og:image（验证后）> 封面图 > AI 生图
- **密度**：balanced 3-5 张。每个主题一张，不是每段都插。留白比堆图专业。
- **来源参考**：

| 类型 | 方案 | 说明 |
|------|------|------|
| 数据图表/架构图 | PPT 截图（按 pptx skill 制作） | 质量可控、永不失效。必须定义设计系统、避 anti-AI cliché、QA 检查后上传 |
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

## 第二章：GitHub 项目分享帖

**定位**：独立于日报的文章类型，推荐一个 GitHub 项目。不走日报流水线，自己发起、自己完成。

**前置**：`GITHUB_TOKEN` 可选（建议配置，提高 rate limit：60 → 5000 req/hr）。配置在 `.env`：
```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

### 工作流（3 步）

**Step 1: 获取仓库数据**

```bash
python -m ai_digest.tool_run github-share --repo owner/repo --title "可选标题"
```

`cmd_github_share()` 调用 `github_client.py` → GitHub REST API：
- `/repos/{owner}/{repo}` → stars / forks / language / description / topics
- `/repos/{owner}/{repo}/readme` → README 原文（`Accept: application/vnd.github.raw+json`，无需 base64）
- `/repos/{owner}/{repo}/releases/latest` → 最新 release 信息（404 = 无发布，返回 None）

返回 JSON 到 stdout：
```json
{
  "metadata": {
    "owner": "ollama", "repo": "ollama",
    "stars": 170972, "forks": 12345,
    "language": "Go",
    "description": "Get up and running with...",
    "topics": ["llm", "inference"],
    "html_url": "https://github.com/ollama/ollama",
    "pushed_at": "2026-05-08T12:00:00+00:00"
  },
  "readme": "# Ollama\n...",
  "latest_release": {"tag_name": "v0.23.2", "name": "...", "body": "..."},
  "article_title": "ollama 推荐"
}
```

**Step 2: Sisyphus 自主撰写文章**

Sisyphus 拿到 JSON 数据后，自主决定文章结构并写入 `data/article_github.md`：

- **标题**：`{repo} 推荐` 或自定义 `--title`
- **内容**：项目简介 + 为什么推荐（解决什么问题、适用场景） + 最新 Release 要点（如果有）
- **GitHub 项目类配图**：Playwright 浏览器截图 `github.com/user/repo` → 上传 CDN → `![](cdn_url)` 插入正文
- **写作风格**：同第一章 Step 6 行文规则，像人写的，有判断有观点

**Step 3: 发布**

```bash
python -m ai_digest.tool_run publish --title "标题" --file data/article_github.md
```

### 关键特性

- **README 获取**：使用 `Accept: application/vnd.github.raw+json`，直接返回 Markdown 原文，无需 base64 解码
- **Rate limit 处理**：429 时自动退避重试（Retry-After → X-RateLimit-Reset → 60s 兜底）
- **软警告**：剩余请求 < 100 时打日志，避免触发硬限制
- **纯数据获取**：不发布草稿，数据返回给 agent 自主处理
- **认证**：`GITHUB_TOKEN` 环境变量，有则加 `Authorization: Bearer` 头，5000 req/hr；无则匿名 60 req/hr

### 配图规范

GitHub 项目页必须配截图（Playwright），不用 og:image。

生成 PPT 数据卡（stars / forks / languages 等关键数字）→ LibreOffice → PyMuPDF 转 PNG → 用 httpx multipart 上传微信 CDN：

```python
# httpx 直传微信 CDN（uploadimg 接口）
import httpx
url = "https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=" + token + "&type=image"
with httpx.Client(timeout=10) as client:
    with open("data/cover.png", "rb") as f:
        resp = client.post(url, files={"media": ("image.png", f, "image/png")})
    cdn_url = resp.json()["url"]   # mmbiz.qpic.cn CDN URL
```

### 质量要求

- **配图 3-5 张**：不要一张图糊弄。GitHub 项目页截图（Playwright）+ 数据 PPT（stars/forks/语言占比等关键数字）+ README 关键截图，至少 3 种不同类型。
- **有观点，不只做摘要**。每段回答「开发者为什么要关心」。
- **专业克制**。读者是 AI/ML 工程师，假设其技术能力。
