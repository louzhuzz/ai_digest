"""
API 数据模型 — 对应 ai_digest/models.py 的 DigestItem
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CandidateItem(BaseModel):
    """候选条目 — 对应 DigestItem 的最小必要字段"""

    idx: int = Field(description="在候选池中的序号")
    title: str = Field(description="标题")
    url: str = Field(description="原文链接")
    source: str = Field(description="来源：GitHub Trending / Hacker News / 机器之心 等")
    summary: str = Field(default="", description="摘要/描述")
    category: str = Field(
        default="news",
        description="类别：github/news/tool/project",
    )
    published_at: str = Field(
        default="",
        description="发布时间 ISO 格式",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="原始 metadata（stars_growth, source_strength 等）",
    )

    model_config = {"extra": "allow"}


class RankingItem(BaseModel):
    """单条排序结果"""

    idx: int = Field(description="对应 CandidateItem.idx")
    score: float = Field(description="综合评分 0-10")
    reason: str = Field(description="评分理由，为什么值得看")


class DigestProcessRequest(BaseModel):
    """POST /digest/process 请求体"""

    date: str = Field(description="日期 YYYY-MM-DD")
    candidates: list[CandidateItem] = Field(description="候选条目列表")
    min_items: int = Field(default=5, description="最少使用条目数")


class SummaryResult(BaseModel):
    """单条摘要结果"""

    idx: int
    summary: str = Field(description="小龙虾写的摘要")


class ArticleDraft(BaseModel):
    """文章草稿"""

    title: str = Field(description="文章标题")
    body: str = Field(description="文章正文 Markdown")
    items_used: list[int] = Field(
        description="使用的候选条 idx 列表"
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="今日亮点列表（供发布参考）",
    )


class DigestProcessResponse(BaseModel):
    """POST /digest/process 响应"""

    status: str = Field(description="success / insufficient_items / error")
    date: str
    ranking: list[RankingItem] = Field(
        default_factory=list,
        description="排序结果，按分数从高到低",
    )
    summaries: dict[str, str] = Field(
        default_factory=dict,
        description="idx → 摘要",
    )
    article: ArticleDraft | None = None
    reason: str | None = None


class DigestStatusResponse(BaseModel):
    """GET /digest/status 响应"""

    status: str = Field(description="idle / processing / done / error")
    current_date: str
    last_run: str | None
    candidates_count: int | None
    items_used: int | None


class PublishRequest(BaseModel):
    """POST /digest/publish 请求体"""

    date: str = Field(description="要发布的草稿日期 YYYY-MM-DD")
    title: str | None = Field(default=None, description="可选：覆盖标题")
