# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ai_digest 是一个面向 AI 开发者热点的日报生成与公众号草稿发布工具。抓取多源热点，做去重、排序、摘要和成稿，然后输出一篇适合公众号发布的中文日报。

## 开发命令

### 运行测试
```bash
python3 -m unittest discover -s tests -v
```

运行单个测试文件：
```bash
python3 -m unittest tests/test_pipeline.py -v
```

### 命令行使用
```bash
# 只生成，不发布
python3 -m ai_digest --dry-run

# 生成并提交公众号草稿
python3 -m ai_digest --publish

# 输出到文件
python3 -m ai_digest --dry-run --output output.md
```

### 网页端
```bash
python3 -m ai_digest.webapp.app
# 默认监听 http://127.0.0.1:8010
```

### 依赖安装
```bash
pip install pillow fastapi uvicorn httpx
```

## 核心数据模型（ai_digest/models.py）

- **DigestItem**: 单条热点，包含 title/url/source/published_at/category/summary/why_it_matters/score/dedupe_key/metadata
- **EventCluster**: 事件聚类，包含 canonical_title/canonical_url/sources/items/score/category/topic_tag

## 架构

```
ai_digest/
├── pipeline.py          # DigestPipeline: collect→dedupe→rank→summarize→cluster→compose→publish
├── runner.py             # DigestJobRunner: 封装 pipeline 为可调用 job，含异常兜底
├── models.py             # DigestItem / EventCluster 数据模型
├── settings.py           # 从 .env 和环境变量加载 AppSettings 配置（load_settings()）
├── state_store.py        # SqliteStateStore: SQLite 状态存储（跨运行去重）
├── defaults.py           # 默认组件构建器，含 CompositeCollector+BoundCollector 模式
├── composition.py        # DigestComposer: 无 LLM 时的规则 Markdown 组稿
├── dedupe.py             # RecentDedupeFilter: 基于 simhash/url 的跨运行去重
├── event_clusterer.py    # EventClusterer: 按标题 token 相似度聚类事件
├── cluster_tagger.py     # ClusterTagger: 调用 ARK LLM 为事件 cluster 打话题标签
├── ranking.py            # ItemRanker: 按新鲜度/热度排序候选项
├── summarizer.py         # RuleBasedSummarizer / DigestPayloadBuilder
├── section_picker.py     # SectionPicker: 来源配额管理 + briefing 筛选
├── article_linter.py     # ArticleLinter: 成稿质量规则检查
├── outline_generator.py  # OutlineGenerator: ARK LLM 生成文章大纲（标题+导语+章节）
├── llm_writer.py         # ARKArticleWriter: 火山 ARK LLM 根据大纲生成完整文章
├── cover_image.py        # generate_cover_image(): PIL 生成公众号封面图
├── wechat_renderer.py    # Markdown → 微信公众号 HTML 内联样式渲染
├── wechat_image_uploader.py  # 微信素材图片上传
├── auth.py               # WeChatAccessTokenClient: 微信接口鉴权
├── http_client.py        # HTTP 请求工具
├── collectors/           # 数据收集器
│   ├── github.py         # GitHubTrendingCollector
│   ├── hn.py             # HNFrontPageCollector
│   ├── huggingface.py    # HFTrendingCollector
│   ├── web_news.py       # WebNewsIndexCollector（机器之心/新智元/量子位/CSDN等）
│   └── rss.py            # RSSCollector
├── publishers/
│   └── wechat.py         # WeChatDraftPublisher: 公众号草稿箱发布
└── webapp/               # FastAPI 网页工作台
    ├── app.py            # create_app(): 生成→预览→编辑→提交 工作流 API
    ├── storage.py        # DraftStorage: 本地 markdown/html/history 持久化
    ├── static/           # 前端静态文件
    └── templates/        # HTML 模板
```

### Pipeline 流程（pipeline.py:63）

**规则模式**（无 LLM，composition.py 负责组稿）：
1. `collector.collect()` 收集原始数据
2. `deduper.filter()` 去重（基于 SQLite 状态库跨运行判重）
3. `ranker.rank()` 排序
4. `summarizer.summarize()` 生成摘要和 "为什么值得跟"
5. `section_picker.apply_source_quota()` 来源配额控制
6. `event_clusterer.cluster()` 事件聚类（可选，用于 fact-card 展示）
7. `cluster_tagger.tag_clusters()` LLM 话题标签（可选，需 ark 配置）
8. `payload_builder.build()` 构建完整 payload
9. `composer.compose()` 规则 Markdown 组稿
10. `publisher.publish()` 提交公众号草稿
11. `deduper.persist()` 持久化去重状态

**LLM 模式**（配置 ARK_API_KEY/ARK_MODEL 后启用）：
- 步骤 1-6 同上
- `section_picker.pick_briefing()` 筛选头条素材
- `payload_builder.build_article_input()` 构建 LLM 输入
- `outline_generator.generate()` ARK 生成文章大纲（标题+导语+章节）
- `writer.render()` 或 `writer.write()` ARK 生成完整文章
- `article_linter.lint()` 质量检查
- `publisher.publish()` 提交公众号草稿

### Web 应用（ai_digest/webapp/app.py）
FastAPI 实现，独立于 CLI 运行。工作流：生成草稿 → HTML 预览（含事件聚类 fact-card）→ 修改 Markdown → 提交公众号。本地数据默认写入 `data/` 目录。

### 配置（settings.py）
通过 `.env` 文件加载，`load_settings()` 返回 `AppSettings` 不可变 dataclass：
- `WECHAT_*` 微信公众号凭证（appid/appsecret/thumb_media_id）
- `ARK_*` 火山 ARK API（api_key/base_url/model/timeout_seconds）
- `AI_DIGEST_STATE_DB` SQLite 状态库路径（默认 `data/state.db`）
- `WECHAT_DRY_RUN=1` 时不调用微信接口，所有操作为 dry run
- `llm_enabled`: 自动判断，ARK 三项配置齐全时为 True
- `draft_mode`: WECHAT 配置齐且非 dry-run 时为 True

### defaults.py：组件工厂模式
`build_default_*()` 系列函数根据 AppSettings 构建完整组件链：
- `build_default_runner()` → DigestJobRunner（含 SqliteStateStore, ClusterTagger, ARK writer/outline_generator）
- `build_default_collector()` → CompositeCollector（组合多个 Bound*Collector，独立容错）
- `build_default_publisher()` → WeChatDraftPublisher（含图片上传器）
- `build_default_writer()` / `build_default_outline_generator()` → 条件创建（ark 配置存在时才返回）
