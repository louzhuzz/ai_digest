# ai_digest

AI 开发者热点日报生成与公众号草稿发布。

**极简架构**：Python 工具脚本（抓取/去重/发布）+ Sisyphus agent（分析/写作）。  
无固定模板，无规则引擎——每日热点由 agent 自行判断主次和结构。

## 依赖

```bash
pip install pillow fastapi uvicorn
```

## 配置

```env
WECHAT_APPID=
WECHAT_APPSECRET=
WECHAT_DRY_RUN=1
AI_DIGEST_STATE_DB=data/state.db
```

## 使用

```bash
# 抓取来源
python -m ai_digest.tool_run collect > data/items.json

# 去重
python -m ai_digest.tool_run dedup < data/items.json > data/filtered.json

# 分析候选池 → 自行撰写 → 保存文章
# ...

# 发布图文消息（推荐 --file，避免 PowerShell 编码问题）
python -m ai_digest.tool_run publish --title "今日标题" --file data/article.md

# 持久化去重状态
python -m ai_digest.tool_run persist < data/filtered.json
```

### 贴图发布（newspic）

```bash
# 生成卡片截图
python -m ai_digest.tool_run cards --input data/cards.json --output-dir data/cards

# 发布贴图（含正文）
python -m ai_digest.tool_run publish-newspic --title "AI 速递" --image-dir data/cards \
  --content-file data/content.txt

# dry-run 验证
python -m ai_digest.tool_run publish-newspic --title "AI 速递" --image-dir data/cards --dry-run
```

Web 工作台（预览/编辑/发布）：

```bash
python -m ai_digest.webapp.app
# http://127.0.0.1:8010
```

## 工具命令

| 命令 | 作用 |
|------|------|
| `collect` | 抓取全部来源，输出 JSON |
| `dedup` | stdin → stdout 去重（7天窗口） |
| `persist` | 去重状态写入 SQLite |
| `publish` | 发布公众号草稿（图文） |
| `cover` | 生成封面图 |
| `cards` | 生成贴图卡片 PNG |
| `publish-newspic` | 发布贴图（图片消息） |

## 数据来源

GitHub Trending / Hacker News / Hugging Face / OpenAI / Anthropic / Google AI / 机器之心 / 新智元 / 量子位 / CSDN AI / RSS
