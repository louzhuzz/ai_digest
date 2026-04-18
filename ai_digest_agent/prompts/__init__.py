"""
prompts/__init__.py — 对外统一的 prompt 构建接口
"""

from api.schemas import CandidateItem
from .rank import build_rank_prompt as _rank
from .write import build_write_prompt as _write


def build_rank_prompt(candidates: list[CandidateItem]) -> str:
    from .rank import SYSTEM_PROMPT as RANK_SYS
    user_part = _rank(candidates)
    return f"{RANK_SYS}\n\n{user_part}"


def build_write_prompt(candidates: list[CandidateItem], ranking: list[dict], top_n: int = 8) -> str:
    from .write import SYSTEM_PROMPT as WRITE_SYS
    user_part = _write(candidates, ranking, top_n)
    return f"{WRITE_SYS}\n\n{user_part}"
