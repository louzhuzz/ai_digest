# 圈内高热度 AI 动态候选池设计

**目标**

把现有公众号日报从“固定来源 + 固定栏目 + 逐条总结”重构为“圈内高热度 AI 动态候选池 + LLM 自主编排”。程序只负责抓热点、去重、打分和过滤噪音，文章结构交给 LLM 组织。

**核心变化**

旧思路：
- 以 RSS 为主
- `arXiv` 和杂项新闻占主体
- 程序先固定栏目，再让 LLM 改写

新思路：
- 以“圈内高热度动态”作为主轴
- 官方源只是验证和补充，不再是主干
- 程序输出一个热点候选池
- LLM 决定最终文章结构和重点顺序

## 产品定义

日报的内容目标不是“完整覆盖”，而是“今天 AI 圈里最值得跟的动态”。

输出风格：
- 偏行业快讯和开发者判断
- 新闻为主，项目为辅
- 不要求固定公司栏目
- 不要求每条都平铺直叙总结
- 更强调：这条为什么热、为什么值得跟

## 候选池设计

候选池只保留两类内容：

1. `news`
- AI 公司发布
- 模型发布
- 产品更新
- 政策/平台/生态变化
- 圈内高热度讨论事件

2. `project`
- 热门 AI 开源项目
- 热门模型/Space/框架
- 对开发者工作流有明显影响的工具

不再把论文摘要作为主体来源。论文只在满足“圈内热度高”时才作为新闻候选的一部分，而不是默认主栏目。

## 来源策略

### 1. 高热度源为主

程序优先抓高热度入口，而不是先抓官方源。

候选来源类型：
- GitHub Trending 中的 AI 相关项目
- Hugging Face 热门模型 / Space
- Hacker News 上的 AI 相关新闻和项目
- 高信号社区聚合页

这些来源解决“今天圈内在讨论什么”。

### 2. 官方源为补充和交叉验证

官方页不再承担“决定今天写什么”，而是：
- 补充细节
- 验证真伪
- 提供原始链接

适合保留的官方来源示例：
- OpenAI News
- Anthropic News
- Google / Gemini 官方博客或产品更新页
- Qwen / DeepSeek / MiniMax / 其他实验室的官方更新页或 GitHub Org 动态

### 3. RSS 降级

RSS 可以继续保留，但不再是主干，只作为少量补充抓取通道。不能再让 RSS 结构决定内容结构。

## 打分逻辑

候选池打分不再只看“发布时间 + stars”，而要更像“热度分”。

热度分由四部分组成：

1. `freshness`
- 越新越高

2. `source_strength`
- 来源信号强度
- 例如官方页、高信号社区页、头部项目平台优先

3. `community_heat`
- 项目或事件在高热度入口中的热度
- 例如 GitHub stars today、HN 排名、HF 热门度

4. `developer_relevance`
- 是否影响开发者工作流
- 是否属于 LLM / agent / multimodal / inference / toolchain / model release 等高相关主题

## 过滤原则

程序必须在 LLM 之前过滤掉以下噪音：

1. 非 AI 主题
- 泛工具、泛编程项目、与 AI 无关的技术新闻

2. 低信号内容
- 没有热度、没有来源强度、也没有开发者影响的内容

3. 重复搬运
- 同一事件多源重复出现时，只保留最强来源和少量辅助信息

4. 论文式噪音
- 没有明显行业讨论热度、只是新发论文的条目，不默认入选

## LLM 输入设计

程序不再给 LLM 固定栏目，而是给它一个结构化热点候选池。

输入字段包含：
- `title`
- `url`
- `source`
- `type` (`news` / `project`)
- `published_at`
- `summary`
- `heat_score`
- `heat_signals`
- `why_relevant`

其中：
- `heat_signals` 记录热度证据，例如：
  - `GitHub stars today`
  - `HN front page`
  - `HF trending`
  - `official announcement`
- `why_relevant` 是程序对开发者相关性的结构化描述，不是最终成稿

## LLM 职责

LLM 不再机械接收固定栏目，而是：
- 自主挑选今天最值得写的 5 到 7 条
- 决定文章结构
- 自主组织段落顺序
- 给出“为什么值得跟”的判断

但仍保留硬约束：
- 全文中文
- 不编造事实
- 不照抄长英文摘要
- 新闻为主，项目为辅
- 不要变成“逐条摘要流水账”

## 正文结构

程序不再强制固定成：
- 今日重点
- GitHub 新项目 / 热项目
- AI 技术进展

更适合的目标结构是：
- 开头导语：今天最热的核心信号
- 中段：最值得跟的 3 到 5 条动态
- 后段：补充 2 到 3 个开发者值得关注的项目或变化
- 结尾：一句判断，说明今天的整体趋势

程序不再写死栏目名。最终结构由 LLM 组织，但必须满足“新闻为主、项目为辅、按热度排序”的约束。

## 发布链路

公众号发布链路保持不变：
- 程序生成热点候选池
- ARK 生成 Markdown 成稿
- 本地转 HTML
- 提交草稿箱

这部分不需要重写，只需要替换采集层和 LLM 输入层。

## 代码结构调整

保留：
- `/mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py`
- `/mnt/d/AIcodes/openclaw/ai_digest/publishers/wechat.py`
- `/mnt/d/AIcodes/openclaw/ai_digest/pipeline.py`

重构重点：
- `/mnt/d/AIcodes/openclaw/ai_digest/defaults.py`
  - 替换默认来源清单
- `/mnt/d/AIcodes/openclaw/ai_digest/collectors/`
  - 新增高热度源 collector
  - 弱化 RSS collector 的主地位
- `/mnt/d/AIcodes/openclaw/ai_digest/ranking.py`
  - 从“新鲜度 + stars”升级为“热度分”
- `/mnt/d/AIcodes/openclaw/ai_digest/section_picker.py`
  - 退出主路径，改为候选池裁剪器，而不是固定栏目器
- `/mnt/d/AIcodes/openclaw/ai_digest/summarizer.py`
  - 改为构建热点候选池 payload，而不是固定栏目 payload

## 风险

1. 热度源会带来更多噪音
- 需要更严格的预过滤

2. 结构交给 LLM 后，文章稳定性会下降
- 需要通过 prompt 约束“新闻为主、项目为辅、不要流水账”

3. 过度追逐热度可能牺牲准确性
- 官方源和原始链接仍要保留，用于交叉验证

## 成功标准

完成后，应满足：

- 草稿主体不再被论文和杂项新闻占满
- 内容更像“今天 AI 圈最热的几个信号”
- 公司新闻、项目热榜、模型发布可以混在同一候选池里竞争
- LLM 能基于候选池组织更自然的公众号文章，而不是被固定栏目绑死
- GitHub / Hugging Face / 社区热度源能稳定提供候选内容
