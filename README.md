# ai_digest

一个面向 AI 开发者热点的日报生成与公众号草稿发布工具。

它会抓取多源热点，做去重、排序、摘要和成稿，然后输出一篇适合公众号发布的中文日报。默认支持两种使用方式：

- 命令行生成或提交公众号草稿
- 网页端生成、预览、编辑后再提交

## 功能概览

- 抓取 AI 相关新闻、GitHub 热门项目和社区热点
- 跨运行去重，避免同一条内容反复入选
- 生成固定结构的中文日报
- 支持接入火山 ARK 做整篇公众号风格改写
- 支持提交到微信公众号草稿箱
- 提供本地网页端发布工作台

当前默认来源包括：

- GitHub Trending
- Hacker News
- Hugging Face Trending
- OpenAI / Anthropic / Google AI / Gemini 官方新闻页
- 机器之心 / 新智元 / 量子位 / CSDN AI

## 环境要求

- Python 3.11+
- Windows 或 WSL/Linux 均可

命令行核心功能主要依赖 Python 标准库和 `Pillow`。  
如果你要使用网页端，还需要额外安装 `fastapi` 和 `uvicorn`。

## 安装

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pillow fastapi uvicorn httpx
```

如果你只需要命令行，不需要网页端，可以只安装：

```bash
pip install pillow
```

Windows PowerShell 示例：

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install pillow fastapi uvicorn httpx
```

## 配置 `.env`

先复制模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

`.env.example` 中的主要配置如下：

```env
# 微信公众号
WECHAT_APPID=
WECHAT_APPSECRET=
WECHAT_THUMB_MEDIA_ID=
WECHAT_DRY_RUN=0

# ARK 成稿
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=
ARK_TIMEOUT_SECONDS=90

# 本地状态库，可选
AI_DIGEST_STATE_DB=data/state.db
```

配置说明：

- `WECHAT_APPID`：公众号 AppID
- `WECHAT_APPSECRET`：公众号 AppSecret
- `WECHAT_THUMB_MEDIA_ID`：封面图素材 ID；如果未提供，发布时会尝试自动生成并上传封面图
- `WECHAT_DRY_RUN`：
  - `1` 表示只生成内容，不调用微信接口
  - `0` 表示允许真实提交公众号草稿
- `ARK_API_KEY` / `ARK_BASE_URL` / `ARK_MODEL`：用于整篇改写和公众号风格重写
- `AI_DIGEST_STATE_DB`：SQLite 状态库路径，默认是 `data/state.db`

## 命令行使用

### 1. 只生成，不发布

```bash
python3 -m ai_digest --dry-run
```

这个模式会：

- 抓取热点
- 生成日报正文
- 直接在终端打印 Markdown
- 不调用微信公众号接口

如果想把结果写入文件：

```bash
python3 -m ai_digest --dry-run --output output.md
```

### 2. 提交公众号草稿

```bash
python3 -m ai_digest --publish
```

成功时终端会输出类似结果：

```text
状态: published
草稿ID: xxx
```

失败时会输出错误原因，例如：

```text
状态: failed
错误: WECHAT_DRY_RUN is enabled
```

### 3. Windows 一键运行

仓库根目录提供了一个批处理脚本：

```powershell
run_publish.bat
```

它会优先使用 `py -m ai_digest --publish`，找不到 `py` 时再回退到 `python -m ai_digest --publish`。

## 网页端启动

网页端适合“生成 -> 预览 -> 手工编辑 -> 提交草稿”这一工作流。

先确保依赖已安装：

```bash
pip install fastapi uvicorn httpx pillow
```

然后启动：

```bash
python3 -m ai_digest.webapp.app
```

默认监听：

```text
http://127.0.0.1:8010
```

网页端支持：

- 一键生成草稿
- 查看 HTML 预览
- 直接修改 Markdown
- 提交公众号草稿
- 查看最近运行历史

## 常见流程

### 本地试跑

```bash
python3 -m ai_digest --dry-run --output sample.md
```

先确认抓取和成稿是否符合预期，再决定是否打开真实发布。

### 真实提交公众号草稿

1. 在 `.env` 中填入公众号配置
2. 把 `WECHAT_DRY_RUN` 设为 `0`
3. 运行：

```bash
python3 -m ai_digest --publish
```

### 使用网页端审核后再发

1. 启动网页端
2. 打开 `http://127.0.0.1:8010`
3. 点击“生成草稿”
4. 在页面里修改 Markdown
5. 点击“提交公众号”

## 注意事项

- `.env` 不要提交到仓库
- 公众号接口依赖 IP 白名单时，需要把真实出口 IP 加到微信后台
- 如果你开了代理或 VPN，微信接口调用的出口 IP 可能变化
- `WECHAT_DRY_RUN=1` 时，网页端和命令行都不会真实提交公众号
- 网页端本地数据默认写到 `data/` 目录

## 测试

运行全部单元测试：

```bash
python3 -m unittest discover -s tests -v
```

如果当前环境没有安装 `fastapi`，部分网页端测试会被跳过。
