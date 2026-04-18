"""
lib/link.py — 复用 ai_digest 代码

通过 sys.path 操作从父项目导入 collector、state_store、publisher
"""

import sys
from pathlib import Path

# ai_digest 根目录
aicodes = Path(__file__).parent.parent.parent
if str(aicodes) not in sys.path:
    sys.path.insert(0, str(aicodes))

# ── collectors（作为 ai_digest 包导入，避免相对导入问题）────────────────────
from ai_digest.collectors import (
    GitHubTrendingCollector,
    HNFrontPageCollector,
    HFTrendingCollector,
    RSSCollector,
    WebNewsIndexCollector,
)

# ── publisher ───────────────────────────────────────────────────────────────
from ai_digest.publishers import WeChatDraftPublisher

# ── state store ─────────────────────────────────────────────────────────────
from ai_digest.state_store import SqliteStateStore

__all__ = [
    "GitHubTrendingCollector",
    "HNFrontPageCollector",
    "HFTrendingCollector",
    "RSSCollector",
    "WebNewsIndexCollector",
    "WeChatDraftPublisher",
    "SqliteStateStore",
]
