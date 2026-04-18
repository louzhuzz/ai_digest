# AI Digest Agent — 开发计划书

**项目名称：** AI Digest Agent
**负责人：** 小龙虾 🦞
**日期：** 2026-04-17
**目标：** 搭建半自动化 AI 热点日报生成流水线

---

## 一、目标

用小龙虾替代 ai_digest 的 LLM 成稿环节（原来用 ARK API），同时复用其数据收集、去重、发布代码，形成完整流水线。

---

## 二、分阶段计划

### 阶段一：基础设施搭建 ✅
**目标：** 建立目录结构、依赖关系、接口契约

- [x] 创建完整目录结构
  ```
  scripts/
    collect.py
  api/
    main.py              # FastAPI 服务
    schemas.py           # 请求/响应数据模型
  prompts/
    rank.py
    write.py
  lib/                   # 复用 ai_digest 代码（link.py）
  output/
    candidates/
    drafts/
    published/
  state/
  tests/
  ```
- [x] 数据模型（api/schemas.py — CandidateItem / DigestProcessRequest 等）
- [x] 小龙虾接口格式（POST /digest/process 请求/响应）
- [x] README.md

---

### 阶段二：数据收集层
**目标：** 独立运行 collectors，输出候选池 JSON

- [ ] `scripts/collect.py`
  - 从 `ai_digest.collectors` 导入各 collector
  - 支持指定来源（GitHub/HN/HuggingFace/机器之心等）
  - 收集结果写入 `output/candidates/YYYY-MM-DD.json`
  - 保留完整 metadata（stars_growth, source_strength 等）
- [ ] `scripts/dedup.py`
  - 复用 `ai_digest/state_store.py` SQLite 去重逻辑
  - 读取当天候选，输出去重后结果
  - 写入 `output/candidates/YYYY-MM-DD_deduped.json`
- [ ] 本地测试：确认收集 + 去重流程跑通

---

### 阶段三：小龙虾接口层
**目标：** FastAPI 服务接收候选池，返回结构化处理结果

- [ ] `api/schemas.py`
  ```python
  class CandidateItem(BaseModel)   # 候选条目
  class RankingResult(BaseModel)  # 排序结果
  class SummaryResult(BaseModel)  # 摘要结果
  class ArticleDraft(BaseModel)   # 文章草稿
  class DigestProcessResponse(BaseModel)  # 完整响应
  ```
- [ ] `api/main.py`
  - `POST /digest/process` — 接收候选池，触发小龙虾处理
  - `GET /digest/status` — 查看任务状态
  - `GET /digest/draft/{date}` — 读取某天草稿
  - `POST /digest/publish` — 触发发布
- [ ] `prompts/rank.py` — 排序打分 prompt
  - 输入：候选条目列表
  - 输出：每条评分 + 理由（JSON 格式）
  - 包含判断维度：热点程度、开发者相关性、来源可信度
- [ ] `prompts/write.py` — 成稿 prompt
  - 输入：排序后的条目 + 摘要
  - 输出：完整 Markdown 文章
  - 要求：公众号风格、有取舍判断、不模板化
- [ ] 本地测试：用真实数据跑通小龙虾接口

---

### 阶段四：流水线串联
**目标：** 一键运行 collect → dedup → 小龙虾处理 → 发布

- [ ] `scripts/run_pipeline.py`
  ```bash
  # 伪代码
  python scripts/collect.py
  python scripts/dedup.py
  curl -X POST http://localhost:8011/digest/process \
    -d @output/candidates/YYYY-MM-DD_deduped.json
  python scripts/publish.py --draft
  ```
- [ ] 定时任务配置（可选）
  - Windows Task Scheduler / cron
  - 每天早上 9:00 自动运行

---

### 阶段五：发布层
**目标：** 小龙虾产出的草稿成功推送到公众号草稿箱

- [ ] `scripts/publish.py`
  - 读取 `output/drafts/YYYY-MM-DD.md`
  - 复用 `ai_digest/publishers/wechat.py` 推送草稿箱
  - 支持 dry-run 模式
- [ ] 微信公民号接口配置
  - 需要 `.env` 填入 WECHAT_APPID / WECHAT_APP SECRET
  - 草稿箱 API 文档

---

### 阶段六：优化与迭代
**目标：** 让文章质量达到可直接发布水平

- [ ] 优化 rank prompt：加入更多判断维度
- [ ] 优化 write prompt：提升文章可读性、自然度
- [ ] 支持手动调整：预览 → 修改 Markdown → 再发布
- [ ] 统计：每天候选数量 → 通过去重数量 → 最终使用数量
- [ ] 历史草稿管理

---

## 三、技术栈

| 层级 | 技术 |
|---|---|
| 数据收集 | Python + httpx（复用 ai_digest collectors） |
| 去重 | SQLite + simhash（复用 ai_digest） |
| API 服务 | FastAPI + uvicorn |
| 大脑 | 小龙虾 🦞 |
| 发布 | 微信草稿箱 API（复用 ai_digest） |

---

## 四、关键接口

### 小龙虾 ↔ FastAPI 接口

**请求（POST /digest/process）**
```json
{
  "date": "2026-04-17",
  "candidates": [
    {
      "idx": 0,
      "title": "DeepSeek 开源新模型",
      "url": "https://...",
      "source": "GitHub Trending",
      "summary": "...",
      "metadata": { "stars_growth": 1230, ... }
    }
  ]
}
```

**响应**
```json
{
  "ranking": [
    { "idx": 0, "score": 9.5, "reason": "DeepSeek 新开源..." }
  ],
  "summaries": {
    "0": "这是...",
    "1": "..."
  },
  "article": {
    "title": "今日最重磅：...",
    "body": "## 导语\n\n..."
  }
}
```

---

## 五、里程碑

| 阶段 | 产出 | 验收标准 |
|---|---|---|
| 阶段一 | 目录结构 + 接口契约 | 文档完整 |
| 阶段二 | collect.py + dedup.py | 能跑出 JSON |
| 阶段三 | FastAPI 服务 + 小龙虾接口 | 接口返回结构正确 |
| 阶段四 | run_pipeline.py | 一键跑完前三步 |
| 阶段五 | publish.py | 草稿成功推送 |
| 阶段六 | 调优 | 文章可直接发布 |

---

## 六、风险与对策

| 风险 | 对策 |
|---|---|
| ai_digest collectors 页面结构变化 | 写好日志，异常时告警 |
| 小龙虾成稿质量不稳定 | prompt 迭代优化，增加示例 |
| 微信 API 调不通 | 支持 dry-run，保留手动发布路径 |
