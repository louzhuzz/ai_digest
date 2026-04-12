# 持久化去重、事件聚类与发布前校验设计

## 背景

当前项目已经具备从多源抓取热点、排序、交给 LLM 成稿并推送到公众号草稿箱的能力，但还存在三个结构性短板：

1. 去重只在单次运行内生效，第二天重跑时不会记住昨天发过的内容。
2. 同一热点可能以多个来源的多条素材同时进入 LLM，增加重复写作和结构混乱的风险。
3. 发布前只校验了 LLM 输出是否以一级标题开头，没有对文章结构和禁用句式做硬约束。

这三个问题会直接影响日报的稳定性、重复率和成稿质量，且比继续微调 prompt 更值得优先修复。

## 目标

本次设计覆盖三个连续模块：

1. 跨运行去重持久化
2. 事件聚类
3. 发布前 article linter

目标是让系统在不引入额外复杂基础设施的前提下，具备更稳定的“热点事件级别”处理能力，并在正式发草稿前拦截明显不合格的文章。

## 非目标

本次不做以下事项：

- 不引入向量数据库或 embedding 检索
- 不做 LLM 参与的语义去重或语义审稿
- 不做正文图片上传或图文配图系统
- 不做多账号、多频道发布
- 不改动微信发布接口协议

## 方案选择

### 方案 A：SQLite 持久化 + 规则聚类 + 规则 linter

这是推荐方案。

优点：

- 本地单文件存储，适合当前项目形态
- 去重和聚类共享同一个状态层，后续可扩展
- 规则透明，易测，问题定位明确

缺点：

- 聚类准确率不如 embedding 方案
- 标题规则需要后续迭代

### 方案 B：JSONL 持久化 + 规则聚类 + 规则 linter

优点：

- 实现更轻
- 文件可直接查看

缺点：

- 后续查询、清理、聚类统计都更笨重
- 状态演进一多就容易变成脚本堆

### 方案 C：SQLite 持久化 + embedding 聚类 + LLM linter

优点：

- 长期效果可能最好

缺点：

- 复杂度明显升高
- 当前项目还没必要承担这层成本

推荐采用方案 A。

## 模块设计

### 1. 持久化去重

新增一个本地状态存储模块，默认使用 SQLite 文件，例如：

- `data/state.db`

新增一张去重表，至少包含以下字段：

- `dedupe_key`
- `source`
- `title`
- `url`
- `published_at`
- `first_seen_at`
- `last_seen_at`

运行流程：

1. pipeline 启动后先读取近 7 天 dedupe 记录
2. 采集到的 item 用现有 `dedupe_key or url` 规则判断是否为重复
3. 非重复项进入后续排序
4. 运行结束后把本次保留项写回状态表

规则：

- 默认去重窗口仍为 7 天
- 去重键优先使用 `item.dedupe_key`
- 若缺失则回退到 `item.url`
- 同一个 dedupe key 在窗口期内只保留一次

### 2. 事件聚类

新增一个 `EventClusterer`，位置放在：

- 排序之后
- LLM 输入构造之前

目标是把“同一个热点事件的多来源条目”折叠成一个事件簇。

新增聚类对象，例如：

- `EventCluster`
  - `cluster_id`
  - `canonical_title`
  - `canonical_url`
  - `items`
  - `sources`
  - `score`
  - `category`
  - `why_it_matters`

第一版聚类规则不使用 embedding，只做规则聚类：

1. 规范化标题
   - 小写化
   - 去除标点
   - 去除明显媒体修饰词
2. 抽取核心实体词
   - 模型名、公司名、项目名、产品名
3. 若标题规范化后高度相似，或核心实体词高度重合，则归为同簇
4. 每个簇保留一条主条目作为 `canonical item`

排序：

- 簇分数取成员最高分 + 多源加成
- 多个高质量来源共同指向同一事件时，簇优先级提高

输出给 LLM 的不再是松散 item 列表，而是：

- `top_event_clusters`
- `top_project_clusters`

每个 cluster 会同时带：

- 主标题
- 主链接
- 来源列表
- 支撑条目数
- 代表性摘要

### 3. 发布前 article linter

新增一个 `ArticleLinter`，位置放在：

- `writer.write(...)` 之后
- `publisher.publish(...)` 之前

目标是把明显不符合公众号成稿要求的内容拦截掉。

第一版只做规则校验，不做自动重写。

硬规则：

1. 必须以 `# ` 一级标题开头
2. 必须至少包含 2 个 `## ` 二级标题
3. 必须至少包含 1 个编号速览列表
4. 必须至少包含 3 个行内链接
5. 不允许出现以下句式：
   - `今日没有新增重大行业新闻`
   - `摘要：`
   - `价值：`
6. 不允许出现代码块、表格、HTML 标签
7. 正文长度必须大于最小阈值，避免短稿误发

处理策略：

- 若 lint 失败，正式发布直接返回 `failed`
- 错误信息写入 runner 输出，便于定位
- 不做自动回退到旧模板发布，避免把不合格稿件推入草稿箱

## 数据流调整

新的主链路变为：

1. collect
2. persistent dedupe
3. rank
4. summarize
5. source quota
6. event clustering
7. build article input
8. LLM write
9. article lint
10. WeChat draft publish
11. persist current run dedupe state

说明：

- `dry-run` 也应尽量复用前半段链路，至少要经过持久化去重和事件聚类
- `article linter` 只对正式发布链路强制执行

## 文件结构建议

新增：

- `ai_digest/state_store.py`
- `ai_digest/event_clusterer.py`
- `ai_digest/article_linter.py`

修改：

- `ai_digest/dedupe.py`
- `ai_digest/pipeline.py`
- `ai_digest/summarizer.py`
- `ai_digest/models.py`
- `ai_digest/defaults.py`（如需注入状态文件默认路径）
- `ai_digest/runner.py`（暴露更明确错误）

测试新增：

- `tests/test_state_store.py`
- `tests/test_event_clusterer.py`
- `tests/test_article_linter.py`
- `tests/test_pipeline.py`

## 错误处理

### 状态文件异常

- 如果 SQLite 文件不存在，自动创建
- 如果状态表损坏或不可读，直接 fail fast，不继续发布
- 错误信息必须包含具体模块名，如：
  - `State store init failed: ...`

### 聚类异常

- 聚类异常视为关键链路异常，直接 fail
- 不回退到“未经聚类直接发布”，避免重复事件重新灌进文章

### lint 异常

- lint 失败不发布
- 错误中要明确列出触发的规则，如：
  - `Article lint failed: missing second-level headings`

## 测试策略

### 持久化去重

- 同一个 dedupe key 在同一次运行中不重复
- 同一个 dedupe key 在不同运行之间也不重复
- 超过 7 天窗口后可以重新进入候选池

### 事件聚类

- 同一事件来自 2 个来源时应被归为 1 个 cluster
- 明显不同事件不能误聚类
- 多源 cluster 分数应高于单源同类条目

### article linter

- 缺失二级标题时报错
- 缺失链接时报错
- 出现禁用句式时报错
- 合格稿件通过

### pipeline 集成

- 正式发布链路会在 publish 前执行 lint
- lint 失败时不会调用 publisher
- 去重状态会在运行后正确写入

## 风险与取舍

1. 规则聚类第一版不可能完美，尤其对中文媒体标题改写较多的事件，可能仍会漏聚类。
2. article linter 过严会提高失败率，过松又挡不住差稿。第一版应只挡明确低质量模式。
3. SQLite 引入后，状态文件要纳入本地运行环境的默认目录管理，但不应进入版本库。

## 成功标准

满足以下条件即可认为本轮设计达标：

1. 同一热点在 7 天内不会反复进入草稿
2. 多来源报道同一事件时，LLM 输入会以事件簇而不是散乱条目出现
3. 明显不合格的文章不会进入公众号草稿箱
4. 所有新增模块都有独立测试和 pipeline 集成测试
