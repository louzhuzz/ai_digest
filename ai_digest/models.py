from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DigestItem:
    title: str
    url: str
    source: str
    published_at: datetime
    category: str
    summary: str = ""
    why_it_matters: str = ""
    score: float = 0.0
    dedupe_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventCluster:
    canonical_title: str
    canonical_url: str
    sources: list[str]
    items: list[DigestItem]
    score: float
    category: str
