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

## 架构

```
ai_digest/
├── pipeline.py          # DigestPipeline: collect→dedupe→rank→summarize→compose→publish
├── runner.py             # DigestJobRunner: 封装 pipeline 为可调用的 job
├── settings.py           # .env 配置加载
├── state_store.py        # SQLite 状态存储（跨运行去重）
├── defaults.py           # 默认组件构建器
├── composition.py        # DigestComposer: Markdown 组稿
├── dedupe.py             # RecentDedupeFilter: 基于 simhash 的去重
├── event_clusterer.py    # EventClusterer: 事件聚类
├── ranking.py            # ItemRanker: 候选项排序
├── summarizer.py         # RuleBasedSummarizer / DigestPayloadBuilder
├── section_picker.py     # SectionPicker: 来源配额管理
├── article_linter.py     # ArticleLinter: 文章质量检查
├── llm_writer.py         # ARKArticleWriter: 火山 ARK LLM 重写
├── collectors/
│   ├── github.py         # GitHubTrendingCollector
│   ├── hn.py             # HNFrontPageCollector
│   ├── huggingface.py    # HFTrendingCollector
│   └── web_news.py       # WebNewsIndexCollector（机器之心/新智元/量子位/CSDN等）
└── publishers/
    └── wechat.py         # WeChatDraftPublisher: 公众号草稿箱发布
```

### Pipeline 流程（pipeline.py:56）
1. `collector.collect()` 收集原始数据
2. `deduper.filter()` 基于 simhash 去重
3. `ranker.rank()` 排序
4. `summarizer.summarize()` 生成摘要
5. `section_picker.apply_source_quota()` 来源配额
6. `payload_builder.build()` 构建日报 payload
7. `composer.compose()` 或 `writer.write()` 生成 Markdown
8. `publisher.publish()` 提交公众号草稿
9. `deduper.persist()` 持久化去重状态到 SQLite

### Web 应用（webapp/app.py）
FastAPI 实现，workflow: 生成草稿 → HTML 预览 → 修改 Markdown → 提交公众号。本地数据默认写入 `data/` 目录。

### 配置（settings.py）
通过 `.env` 文件配置：
- `WECHAT_*` 微信公众号凭证
- `ARK_*` 火山 ARK API（可选，用于整篇重写）
- `AI_DIGEST_STATE_DB` SQLite 状态库路径

`WECHAT_DRY_RUN=1` 时不调用微信接口，所有操作均为 dry run。
