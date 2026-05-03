# ai_digest/collectors/keywords.py — 关键词过滤器 + 来源分级
# 支持 AI_DIGEST_KEYWORDS 环境变量配置，逗号分隔，OR 匹配
from __future__ import annotations

from ..models import DigestItem

# 来源分级：高质量 AI 来源 → 全量保留；中质量来源（知乎/微博）→ 必须命中关键词
HIGH_PRIORITY_SOURCES = frozenset({
    "GitHub Trending", "Hacker News", "Hugging Face", "OpenAI Blog",
    "Anthropic News", "Google AI", "机器之心", "新智元", "量子位",
    "CSDN AI", "RSS",
})
MEDIUM_PRIORITY_SOURCES = frozenset({"知乎热榜", "微博热搜", "微博", "知乎"})


def filter_by_keywords(
    items: list[DigestItem],
    keywords: tuple[str, ...],
    require_keywords_for_medium: bool = True,
) -> list[DigestItem]:
    """
    按关键词 + 来源分级过滤 DigestItem 列表。

    逻辑：
    - HIGH_PRIORITY 来源：全量保留（不受关键词影响）
    - MEDIUM_PRIORITY 来源：
        - keywords 为空 → 全量保留（passthrough）
        - keywords 有值 → 必须命中任一关键词才保留
    - 其他来源 → 等同于 MEDIUM_PRIORITY

    关键词匹配忽略大小写，支持子串匹配。
    """
    if not keywords:
        return items

    lowered = [k.lower() for k in keywords]

    def matches(item: DigestItem) -> bool:
        text = f"{item.title} {item.summary} {item.url}".lower()
        return any(kw in text for kw in lowered)

    def item_matches(item: DigestItem) -> bool:
        # 高优先级来源：直接通过
        if item.source in HIGH_PRIORITY_SOURCES:
            return True
        # 中优先级来源：关键词匹配
        if require_keywords_for_medium:
            return matches(item)
        # 关闭关键词过滤时：全部保留
        return True

    return [item for item in items if item_matches(item)]