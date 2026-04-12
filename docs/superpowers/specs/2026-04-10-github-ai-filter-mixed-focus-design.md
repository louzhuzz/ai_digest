# GitHub AI 过滤与今日重点混排设计

**目标**

让 GitHub 栏目只保留 AI 相关项目，同时让“今日重点”保持新闻与 GitHub 的混排，不再被单一类别占满。

**本次改动**

1. GitHub Collector 增加 AI 相关过滤
   - 基于 `title + description` 命中 AI 关键词才保留
   - 对明显泛工具关键词做排除
   - 过滤逻辑放在 collector 层，不把无关项目传到后续排序

2. SectionPicker 改为显式混排
   - 今日重点优先保证：
     - 至少 1 条 `news/tool`
     - 至少 1 条 `github`
   - 第 3 条从剩余高分候选补
   - 若某一类不足，则回退给另一类

**成功标准**

- `markitdown` 这类泛工具项目默认不进入 GitHub 栏目
- `agent / llm / rag / model` 等 AI 相关项目能进入 GitHub 栏目
- 当新闻和 GitHub 都有候选时，“今日重点”必须混排
- 全量测试通过
