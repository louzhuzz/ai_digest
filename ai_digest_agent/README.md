# AI Digest Agent

AI 热点日报生成流水线，小龙虾担任大脑。

## 架构

```
收集（ai_digest collectors）
    ↓
去重（SQLite，复用 ai_digest）
    ↓
候选池 → 小龙虾（排序 + 摘要 + 成稿）
    ↓
发布（微信公众号草稿箱）
```

## 快速开始

```bash
# 1. 收集当天数据
python scripts/collect.py

# 2. 去重
python scripts/dedup.py

# 3. 启动本地 API（小龙虾接收任务用）
uvicorn api:app --port 8011

# 4. 发布到草稿箱
python scripts/publish.py --draft
```

## 目录

- `scripts/` — 流水线脚本
- `lib/` — 复用 ai_digest 代码
- `prompts/` — rank + write prompt 模板
- `output/candidates/` — 候选池
- `output/drafts/` — 文章草稿
- `state/` — SQLite 去重状态库
