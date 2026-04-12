# 发布界面（本地网页面板）设计

## 目标

提供一个本地 `localhost` 发布界面，用于：

- 一键生成草稿（走现有 pipeline）
- 预览/编辑草稿（Markdown + HTML）
- 一键提交公众号草稿
- 查看最近运行历史

默认不做鉴权，仅允许本机访问。

## 非目标

- 不支持公网访问
- 不做多用户登录/权限管理
- 不做多公众号账号切换
- 不做自动定时发布（仍由现有 CLI/任务调度负责）

## 架构

**后端**

- FastAPI（推荐）或 Flask
- 单进程运行在 `127.0.0.1:8010`
- 复用现有 pipeline：`dry-run` 生成、`publish` 发布

**前端**

- 轻量静态页面（HTML + CSS + 少量 JS）
- 本地渲染 Markdown + HTML 预览

**存储**

- `data/last_draft.md`
- `data/last_draft.html`
- `data/run_history.jsonl`

## 页面结构

1. **状态栏**
   - 上次运行时间
   - 上次状态
   - 候选条数
   - 草稿 ID

2. **操作区**
   - `生成草稿`
   - `重新生成`
   - `提交公众号`
   - `清理历史`

3. **编辑区**
   - 左侧 Markdown 编辑
   - 右侧 HTML 预览

4. **历史区**
   - 最近 N 次运行记录

## API 设计

- `POST /api/run`
  - 触发 pipeline（dry-run）
  - 写入 `data/last_draft.md` / `data/last_draft.html`
  - 返回运行结果与摘要

- `GET /api/preview`
  - 返回最新 Markdown 和 HTML

- `POST /api/update`
  - 保存用户编辑后的 Markdown
  - 同步更新 HTML 预览

- `POST /api/publish`
  - 使用当前草稿提交公众号草稿
  - 仍走 `ArticleLinter`

- `GET /api/history`
  - 返回最近运行记录

## 数据流

1. 点击“生成草稿”
   - 调 `POST /api/run`
   - 运行 dry-run pipeline
   - 落盘 `last_draft.md` / `last_draft.html`

2. 预览/编辑
   - 读取 `GET /api/preview`
   - 编辑后调用 `POST /api/update`

3. 点击“提交公众号”
   - 调 `POST /api/publish`
   - 走 publish pipeline（含 lint）
   - 返回草稿 ID

## 错误处理

- `run` 失败：前端展示错误信息，不覆盖 last_draft
- `publish` 失败：保留当前草稿，返回 lint 或发布错误
- `lint` 失败：前端提示具体规则失败原因

## 成功标准

1. 本机启动后可通过浏览器完成“生成-预览-编辑-发布”闭环
2. 发布路径仍受 `ArticleLinter` 约束
3. 运行历史可回看，便于排查
