"""
prompts/rank.py — 排序打分 prompt
"""

from api.schemas import CandidateItem


SYSTEM_PROMPT = """你是一个 AI 热点价值评估专家。

## 你的任务
评估以下候选条目，为每条打分 0-10，并写出简短理由。

## 打分维度（权重不同）
1. **热点程度**：是否是当前最热门的话题？有没有 viral 潜力？
2. **开发者相关性**：对 AI 开发者有没有直接帮助？（开源项目、新工具、新论文）
3. **来源可信度**：来源越权威、越垂直于 AI 开发者，分数越高
4. **时效性**：越新鲜越高分（7天内）

## 输出格式（必须严格遵循）
```json
[
  {"idx": 0, "score": 9.5, "reason": "DeepSeek新开源..."},
  {"idx": 1, "score": 8.2, "reason": "HuggingFace新模型..."}
]
```

注意：
- score 是 0-10 的浮点数
- reason 20-50 字，说明为什么这个分数
- 按 score 从高到低排序
- 只输出 JSON，不要有其他文字
"""


def build_rank_prompt(candidates: list[CandidateItem]) -> str:
    """构造用户输入部分 prompt"""
    items_text = "\n".join(
        f"[{i.idx}] 来源:{i.source} | 分类:{i.category} | 标题:{i.title}"
        + (f" | 摘要:{i.summary}" if i.summary else "")
        + (
            f" | 热度:{i.metadata.get('stars_growth', 'N/A')}"
            if i.metadata.get("stars_growth") else ""
        )
        for i in candidates
    )

    return f"""## 候选条目
{items_text}
"""
