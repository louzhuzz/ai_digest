# 质量提升三合一优化 spec

## 概述

三项优化纵向分层推进，每步产出完整可用：

1. **聚类标签升级**（EventClusterer → ClusterTagger）：给每个 cluster 打 topic_tag
2. **事实卡预览面板**：发布前侧栏，展示入选事件、聚类标签、来源分布
3. **LLM 两阶段**：先出 Outline JSON，再渲染正文，减少跑偏
4. **微信专用 HTML 渲染器**：完整公众号风格排版模板

---

## Step 1：聚类标签升级

### 目标

每个 EventCluster 多一个 `topic_tag: str`，格式如 `"OpenAI 新模型发布"`、`"GitHub Agent 基建爆发"`、`"Claude 代码能力更新"`。

### 改动文件

- `ai_digest/event_clusterer.py`

### 数据结构

```python
@dataclass
class EventCluster:
    items: set[DigestItem]
    topic_tag: str   # 新增
```

### 实现方式

在 `EventClusterer.cluster()` 之后，加一层 `ClusterTagger.tag_clusters(clusters: list[EventCluster]) -> list[EventCluster]`。

调用方式：复用一个 ARK API key（同 `RuleBasedSummarizer` 的调用路径），一次请求对所有 clusters 打标签，不引入新依赖。

**Prompt 设计**（简单候选池）：
```
你是一个 AI 热点编辑。请为以下每个事件 cluster 生成一个简短的话题标签（最多 5 个字）。

候选标签池：
- 模型发布（指新模型、功能更新）
- 开源项目（指 GitHub 项目、库、工具）
- 代码能力（指编码、调试相关能力更新）
- 行业动态（指公司合作、投资、政策）
- 社区热点（指社区讨论、HackerNews 趋势）

输入：clusters 列表，每个含多条新闻标题
输出：JSON数组，每个元素 {cluster_index, topic_tag}

请直接输出 JSON，不要解释。
```

### 输出

`list[EventCluster]`，每个 cluster 有了 topic_tag。

### 测试

- `test_event_clusterer.py`：打标签后 cluster 数量和 topic_tag 非空

---

## Step 2：事实卡预览面板

### 目标

在网页端发布按钮旁边，新增右侧可折叠事实卡侧栏，展示"这篇稿子基于哪些原始事件"，让编辑在发布前核对方。

### 改动文件

- `ai_digest/webapp/app.py`（新增 API 端点 + 前端 panel）
- `ai_digest/webapp/static/app.js`（前端交互）
- `ai_digest/webapp/templates/index.html`（panel UI）

### 新增 API

```
GET /api/fact-card?run_id=<run_id>
```

返回：
```json
{
  "total_items": 13,
  "source_distribution": {"github": 3, "news": 8, "huggingface": 2},
  "clusters": [
    {
      "topic_tag": "OpenAI 新模型发布",
      "source_count": 3,
      "top_sources": ["机器之心", "量子位", "Hacker News"],
      "is_multi_source": true,
      "example_title": "OpenAI 发布 GPT-4o ..."

    }
  ],
  "high_signal_dropped": [
    {"title": "...", "source": "GitHub", "reason": "被聚类合并"}
  ]
}
```

### 前端 Panel UI

- 可折叠右侧边栏，宽度约 320px
- 每个 cluster 一张卡片，显示 topic_tag、来源数、示例标题
- 顶部显示来源分布文字条（"GitHub 3 / 新闻 8 / HF 2"）
- 底部显示"未入选但值得关注"（最多 3 条）

### 数据来源

直接读当前 `DigestPipeline.run()` 返回的 `items` + `clusters`，不需要新 pipeline 接口。

### 边界

纯展示组件，不修改 pipeline 或发布逻辑。

---

## Step 3：LLM 两阶段（Outline → Article）

### 目标

把 `ARKArticleWriter` 从单阶段改成两阶段，先出结构化 outline，再渲染正文，减少 LLM 跑偏和空泛总结。

### 改动文件

- `ai_digest/llm_writer.py`（拆出 OutlineGenerator）
- 新建 `ai_digest/outline_generator.py`
- `ai_digest/pipeline.py`（调用方式调整）

### 接口设计

**Phase 1：`OutlineGenerator.generate(article_input: dict) -> Outline`**

```python
@dataclass
class Outline:
    title: str
    lede: str                          # 导语，2-3 句
    sections: list[SectionSpec]

@dataclass
class SectionSpec:
    heading: str
    key_points: list[str]              # 本节核心事实点
    source_hints: list[str]            # 参考来源标题（给编辑看的提示）
```

**Phase 2：`ARKArticleWriter.render(outline: Outline, article_input: dict) -> str`**

接收 outline + article_input，输出 Markdown 正文。

### 校验与 Fallback

- Phase 1 产出后校验 outline 结构（title/lede/sections 非空）
- 校验失败 → 降级到现有单阶段 `write()` 直接写全文（不阻断发布）
- Phase 2 失败 → 降级到单阶段

### Prompt 调整

**Outline prompt**（System）：
```
你是 AI 热点日报编辑。请根据以下候选池，输出一份文章大纲。

要求：
- title：公众号标题，10-20 字，有吸引力
- lede：导语 2-3 句，交代今日整体基调
- sections：按话题重要性排序，每节含 heading（章节标题）、key_points（本节要写到的核心事实）、source_hints（参考来源标题，供编辑核实）

输出必须为有效 JSON，格式如下：
{"title": "...", "lede": "...", "sections": [{"heading": "...", "key_points": [...], "source_hints": [...]}]}

只输出 JSON，不要额外解释。
```

**Render prompt**（User）：
```
请根据以下大纲和原始素材，写成一篇公众号文章。

大纲：
<outline JSON>

原始素材：
<article_input>

要求：
- 按大纲结构写作
- key_points 提到的每条事实都要覆盖
- 写得像公众号，有判断和取舍
- 最终输出为 Markdown 格式
```

### 改动 pipeline.py

`DigestPipeline` 的 `dry_run=False` 路径改为：
1. 调用 `OutlineGenerator.generate()` → 校验 outline
2. 调用 `ARKArticleWriter.render(outline, article_input)` → 生成正文
3. 调用 `ArticleLinter.lint()` → 校验

---

## Step 4：微信专用 HTML 渲染器

### 目标

替代现有 `publishers/wechat.py` 里的 `markdown_to_html()`，输出完整公众号排版风格的 HTML。

### 改动文件

- 新建 `ai_digest/wechat_renderer.py`
- 修改 `ai_digest/publishers/wechat.py`（引入新渲染器）

### 渲染器接口

```python
def render_wechat_html(markdown: str) -> str:
    """将 Markdown 转换为微信兼容的 HTML 片段。"""
```

### 样式模板（CSS-in-inline-style）

| 元素 | 样式 |
|------|------|
| 正文段落 | `font-size:16px; line-height:1.8; color:#333; margin:1em 0;` |
| 一级标题 H1 | `font-size:20px; font-weight:bold; color:#1a1a1a; margin:1.2em 0 0.6em;` |
| 二级标题（段落式） | `<p style="margin:1.4em 0 0.55em; font-size:22px; font-weight:700; line-height:1.45;"><strong>标题</strong></p>` |
| 三级标题 | `<p style="margin:1em 0 0.45em; font-size:18px; font-weight:700; line-height:1.5;"><strong>标题</strong></p>` |
| 加粗 | `<strong style="color:#1a1a1a;">`（保留加粗但不过重） |
| 有序列表 | `1. 内容`（微信倾向不用 ol/ul，用字符 + 缩进） |
| 链接 | `<a href="..." style="color:#1a73e8; text-decoration:underline;">` |
| 引用块 | `<blockquote style="border-left:3px solid #ddd; padding-left:1em; color:#666; margin:1em 0;">` |

### 渲染流程

```
Markdown text
  → split by lines
  → for each block:
      if H1 → render_h1()
      if H2 → render_h2_wechat_style()
      if H3 → render_h3_wechat_style()
      if ordered list → render_ordered_list()
      if bold → render_bold()
      if link → render_link()
      else → render_paragraph()
  → join with "\n"
```

### 边界

- 内部编辑格式仍保留 Markdown，发布时才走 WeChat 渲染器
- 不破坏现有 `WeChatDraftPublisher` 的调用接口

---

## 实现顺序

1. Step 1：聚类标签（EventClusterer → ClusterTagger）
2. Step 2：事实卡预览面板（依赖 Step 1 的 topic_tag）
3. Step 3：LLM 两阶段（独立改 llm_writer，不破坏 pipeline）
4. Step 4：微信 HTML 渲染器（独立改 wechat_renderer，不破坏 pipeline）

Step 2 依赖 Step 1；Step 3 和 Step 4 可并行开发、单独提 PR。

---

## 测试策略

- Step 1：`test_event_clusterer.py` 加 topic_tag 断言
- Step 2：`test_webapp_api.py` 加 `/api/fact-card` 端点测试
- Step 3：`test_llm_writer.py` 拆出 outline 校验测试 + fallback 测试
- Step 4：`test_wechat_publisher.py` 加渲染器输出样式断言

---

## 未纳入范围

- 段落级事件追溯（事实卡只到聚类标签粒度）
- Pipeline 数据结构重构（仍用现有 `DigestItem`）
- 发布后微信原生样式调优（公众号后台 CSS 注入）
