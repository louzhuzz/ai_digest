# ai_digest

AI 开发者热点日报生成与公众号草稿发布工具。

**极简架构**：Python 工具脚本（抓取/去重/发布）+ Sisyphus agent（分析/判断/写作）。无固定模板，无规则引擎——每日热点由 agent 自主决定主次和结构。

## 功能特性

- **多源收集**：23 个信源覆盖 GitHub Trending / Hacker News / HuggingFace / OpenAI / Anthropic / Google AI / 机器之心 / 新智元 / 量子位 / 雷锋网 / 爱范儿 / DeepMind Blog / DeepLearning AI / Solidot / InfoQ / iThome / 橘鸦 Juya RSS / OpenClaw Blog / Kiro Blog / NVIDIA Blog / 商汤 News / OpenRouter Announcements / 多个 GitHub Releases RSS（DeepSeek / Qwen / 智谱）
- **跨运行去重**：SQLite 状态库 + simhash 文本相似度（7 天窗口）
- **AI 驱动**：agent 自主完成时效过滤、多源交叉验证、主次判断、配图规划、文章写作，无固定模板
- **贴图发布（newspic）**：结构化 JSON → 10 种卡片模板（cover/content/list/data/compare/closing/content-grid/content-hero/content-steps/content-quote）→ Playwright 截图 → 永久素材上传 → 公众号草稿
- **GitHub 项目分享帖**：一键获取仓库元数据（stars/forks/languages/releases/README）→ agent 自主撰写项目推荐文章
- **Web 工作台**：生成 → 预览 → 编辑 → 提交

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium --with-deps
```

### 配置 `.env`

```env
# 微信公众号（可选，WECHAT_DRY_RUN=1 时不调用微信接口）
WECHAT_APPID=your_appid
WECHAT_APPSECRET=your_appsecret
WECHAT_DRY_RUN=1

# 火山 ARK（可选，配置后启用 LLM 模式自动生成文章）
ARK_API_KEY=your_ark_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=deepseek-chat

# GitHub Token（可选，配置后 github-share 命令自动使用）
GITHUB_TOKEN=your_github_token

# SQLite 状态库路径（去重用）
AI_DIGEST_STATE_DB=data/state.db
```

### 每日日报流水线

```bash
# 1. 收集（23 来源并行抓取，结果写入 data/items_collected.json）
python -m ai_digest.tool_run collect

# 2. 去重（读取上一步文件，stdout 输出去重后 JSON）
python -m ai_digest.tool_run dedup

# 3. AI 分析 + 写作（agent 自主完成）
#    → 时效过滤 → 搜索验证 → 判断主线 → 生成 data/article.md

# 4. 发布公众号草稿
python -m ai_digest.tool_run publish --title "今日标题" --file data/article.md

# 5. 持久化去重状态
python -m ai_digest.tool_run persist
```

### GitHub 项目分享帖

```bash
# 获取仓库元数据（JSON）
python -m ai_digest.tool_run github-share --repo owner/repo

# agent 自主写文章后发布
python -m ai_digest.tool_run publish --title "项目名" --file data/article.md
```

### 贴图发布（newspic）

```bash
# 生成卡片截图（JSON → 900×1200px PNG）
python -m ai_digest.tool_run cards --input data/cards.json --output-dir data/cards

# 发布贴图（上传永久素材 → 创建草稿）
python -m ai_digest.tool_run publish-newspic \
  --title "AI 速递" \
  --image-dir data/cards \
  --content-file data/content.txt
```

### Web 工作台

```bash
python -m ai_digest.webapp.app
# http://127.0.0.1:8010
```

## 工具命令

| 命令 | 作用 |
|------|------|
| `collect` | 多来源并行抓取，结果自动写入 `data/items_collected.json` |
| `dedup` | 跨运行 simhash 去重（7天窗口） |
| `compose` | stdin JSON → stdout Markdown（不发布） |
| `persist` | 去重状态写入 SQLite |
| `publish` | 发布公众号图文草稿 |
| `cover` | 生成封面图（PIL，900×383 微信封面比例） |
| `cards` | 生成贴图卡片 PNG（多卡，支持 10 种模板） |
| `publish-newspic` | 发布贴图（newspic），支持 `--dry-run` |
| `github-share` | 获取 GitHub 仓库元数据（JSON），供 agent 写分享帖 |

## 数据来源（23 个信源）

| 来源 | 类型 | 备注 |
|------|------|------|
| GitHub Trending | 趋势 | 每日热门项目 |
| Hacker News | 趋势 | AI 相关讨论 |
| HuggingFace Trending | 趋势 | 模型/数据集热度 |
| OpenAI News | 官方 | 产品发布 |
| Anthropic News | 官方 | Claude 更新 |
| Google AI / Gemini | 官方 | Gemini 动态 |
| 橘鸦 Juya RSS | 聚合 | 中文 AI 日报标杆 |
| DeepSeek / Qwen / 智谱 GitHub Releases | 官方 | 版本发布 |
| OpenRouter Announcements | 聚合 | 模型定价/SDK/API 更新 |
| 机器之心 / 新智元 / 量子位 | 媒体 | AI 垂直媒体 |
| 雷锋网 / 爱范儿 | 博客 | 科技博客 |
| DeepMind Blog / DeepLearning AI | 博客 | 研究/教育 |
| Solidot / InfoQ / iThome | 资讯 | 综合资讯 |
| OpenClaw Blog | 官方 | OpenClaw 动态 |
| Kiro Blog | 官方 | Kiro IDE 动态 |
| NVIDIA Blog | 官方 | GPU/加速计算 |
| 商汤 News | 官方 | 国内 AI 公司 |

## 贴图卡片系统

### 卡片模板（10 种）

| 类型 | 用途 |
|------|------|
| `cover` | 封面钩子：大标题 + 副标题 + 日期标签 |
| `content` | 内容卡片：标题 + 要点式正文 + 高亮框 |
| `list` | 列表卡片：编号 + 关键词 + 描述 |
| `data` | 数据卡片：大数值 + 标签 |
| `compare` | 对比卡片：多行对比展示 |
| `closing` | 结尾引导卡：总结 + 关注引导 |
| `content-grid` | 四宫格：2×2 网格展示 |
| `content-hero` | 大字报：主数据大字居中 |
| `content-steps` | 步骤卡片：序号 + 标签 + 描述 |
| `content-quote` | 引用卡片：大引言 + 出处 |

### 响应式字体

字号根据卡片总数自动连续缩放（Python 计算，CSS 变量注入，无需 JS）：

```
1 card  → title: 56px  (最大)
5 cards → title: 51px
7 cards → title: 48px
10 cards → title: 44px (最小)
```

## 开发

### 运行测试

```bash
python -m unittest discover -s tests -v
```

### 核心文件

```
ai_digest/
├── tool_run.py              # CLI 入口（collect/dedup/publish/cards/github-share/...）
├── pipeline.py              # 主管道：collect→dedup→rank→summarize→compose→publish
├── defaults.py              # 默认组件工厂（build_default_*）
├── models.py                # DigestItem / EventCluster 数据模型
├── settings.py              # 配置加载（.env → AppSettings）
├── state_store.py           # SQLite 去重状态
├── http_client.py           # HTTP 客户端（Chrome UA + 指数退避重试 + 超时）
├── image_card_generator.py  # 贴图卡片渲染（10 种模板 + 响应式字体）
├── cover_image.py           # 封面图 PIL 生成（900×383 微信封面比例）
├── wechat_renderer.py       # Markdown → 微信公众号 HTML（内联样式）
├── wechat_image_uploader.py # 微信图片上传（uploadimg → CDN URL）
├── github_client.py         # GitHub API 客户端（退避重试 + raw README）
├── collectors/
│   ├── github.py            # GitHubTrendingCollector
│   ├── hn.py                # HNFrontPageCollector
│   ├── huggingface.py       # HFTrendingCollector
│   ├── web_news.py          # WebNewsIndexCollector（13 个 AI 源站）
│   ├── rss.py               # RSSCollector（支持 RSS + Atom）
│   └── registry.py          # BoundCollector 统一工厂 + 注册表
└── publishers/
    └── wechat.py            # WeChatDraftPublisher（含 newspic 贴图发布）
```

## License

MIT
