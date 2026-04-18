# AI Digest Agent — 项目规格

## 1. 概述

**目标：** 打造一个半自动化的 AI 热点日报生成流水线。

- 爬取/抓取原始数据 → 复用 `ai_digest` collectors
- 跨天去重 → 复用 `ai_digest` SQLite dedup 机制
- 候选池排序 → **小龙虾**（LLM）来做，打分更智能
- 摘要 + 成稿 → **小龙虾** 负责，自然有判断力
- 发布到公众号草稿箱 → 复用 `ai_digest` wechat publisher

**核心理念：** LLM + 规则引擎协作，数据管道标准化，文章质量靠小龙虾。

---

## 2. 系统架构

```
[数据收集层]              [LLM大脑层]              [发布层]
─────────────────        ──────────────        ──────────────

ai_digest collectors      小龙虾(我)              wechat publisher
  - GitHubTrending         - 理解每个条目         - 提交草稿箱
  - HackerNews             - 排序打分理由         - 微信公民号接口
  - HuggingFace            - 写摘要               复用 ai_digest
  - 机器之心/新智元等        - 成稿整篇文章           publishers/wechat.py
                          - 判断取舍
SQLite dedup
  复用 ai_digest
  state_store.py
```

---

## 3. 目录结构

```
ai_digest_agent/
├── SPEC.md
├── README.md
│
├── scripts/                      # 可独立运行的脚本
│   ├── collect.py                # 统一收集入库
│   ├── dedup.py                  # 查重脚本（调用SQLite）
│   ├── fetch_candidates.py        # 把当天候选取出来发给小龙虾
│   └── run_pipeline.sh           # 一键运行（collect→dedup→fetch）
│
├── lib/                          # 复用 ai_digest 代码（通过符号链接或拷贝）
│   └── (复用 ai_digest/collectors, state_store, publishers)
│
├── prompts/                       # prompt 模板
│   ├── rank_prompt.py            # 排序打分 prompt
│   └── write_prompt.py           # 成稿 prompt
│
├── output/                        # 生成结果
│   ├── candidates/               # 当天候选池
│   ├── drafts/                   # 文章草稿
│   └── published/                # 已发布记录
│
└── state/                        # SQLite 数据库
    └── digest.db                 # 复用 ai_digest 的去重状态库
```

---

## 4. 工作流程

### 4.1 数据收集（每日定时）

```bash
python scripts/collect.py
```

- 调用 `ai_digest` 各 collector 收集当天数据
- 写入 `output/candidates/YYYY-MM-DD.json`
- 原始数据不过滤，保留完整 metadata

### 4.2 去重

```bash
python scripts/dedup.py
```

- 读取当天候选
- 用 SQLite（复用 `ai_digest/state_store.py`）做 simhash 去重
- 输出去重后候选池

### 4.3 候选池处理（小龙虾工作）

```bash
python scripts/fetch_candidates.py
```

- 把去重后的候选池读取出来
- 通过**标准格式**发送给小龙虾（本地 HTTP API 或直接写文件）
- 小龙虾返回：排序结果 + 每条摘要 + 整篇文章草稿

### 4.4 发布

```bash
python scripts/publish.py --draft
```

- 小龙虾产出的草稿写入 `output/drafts/`
- 调用 `wechat publisher` 推送到公众号草稿箱

---

## 5. 与小龙虾的接口设计

### 5.1 请求格式

小龙虾通过 HTTP 本地接口（FastAPI）接收任务：

```
POST /api/digest/process
{
  "date": "2026-04-17",
  "candidates": [ ...每条 item 的完整字段... ]
}
```

### 5.2 返回格式

```json
{
  "ranking": [
    { "idx": 0, "score": 9.5, "reason": "DeepSeek新开源模型..." }
  ],
  "summaries": {
    "0": "摘要内容...",
    "1": "..."
  },
  "article": {
    "title": "今日最重磅：...",
    "body": "## 导语\n\n...",
    "items_used": [0, 1, 3, 5]
  }
}
```

---

## 6. 关键设计决策

### 6.1 为什么不让小龙虾直接爬？
- 爬虫需要维护 HTML 解析逻辑，容易因为页面结构变化坏掉
- ai_digest collectors 已经跑通，稳定性有保证
- 小龙虾擅长判断和写作，不擅长维护爬虫规则

### 6.2 为什么不让 ai_digest 直接成稿？
- 它的 LLM prompt 写得模板化，出来的文章不自然
- 小龙虾可以加判断、有取舍、语气更公众号
- 小龙虾写作时自带上下文理解能力

### 6.3 数据流向
```
Collectors → candidates.json → SQLite dedup → candidates_deduped.json
                                              ↓
                                         小龙虾（排序+摘要+成稿）
                                              ↓
                                    drafts/YYYY-MM-DD.md
                                              ↓
                                    WeChat Publisher → 草稿箱
```

---

## 7. 技术依赖

- **Python 3.11+**
- **httpx** — HTTP 客户端
- **FastAPI** — 本地 API 服务
- **uvicorn** — ASGI 服务器
- **ai_digest** collectors（从 `D:\aicodes\openclaw\ai_digest` 导入）
- **微信公民号发布**（复用 `ai_digest/publishers/wechat.py`）

---

## 8. 当前模块实现状态

| 模块 | 状态 | 说明 |
|---|---|---|
| `scripts/collect.py` | ⏳ 待写 | 复用 collectors |
| `scripts/dedup.py` | ⏳ 待写 | 复用 state_store |
| `scripts/fetch_candidates.py` | ⏳ 待写 | 标准接口 |
| `scripts/publish.py` | ⏳ 待写 | 复用 wechat publisher |
| FastAPI 服务 | ⏳ 待写 | 小龙虾接收请求 |
| prompts/ | ⏳ 待写 | rank + write prompts |
