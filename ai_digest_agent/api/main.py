"""
api/main.py — FastAPI 服务

小龙虾通过 HTTP API 接收候选池、处理并返回结果。
启动：uvicorn api.main:app --port 8011
"""

import json
import re
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    ArticleDraft,
    CandidateItem,
    DigestProcessRequest,
    DigestProcessResponse,
    DigestStatusResponse,
    RankingItem,
    SummaryResult,
)
from prompts import build_rank_prompt, build_write_prompt


# ── 路径 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CANDIDATES_DIR = ROOT / "output" / "candidates"
DRAFTS_DIR = ROOT / "output" / "drafts"
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

# ── 状态 ──────────────────────────────────────────────────────────────────
_state = {"status": "idle", "last_run": None, "candidates_count": None}


# ── FastAPI ────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Digest Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/digest/status", response_model=DigestStatusResponse)
async def get_status():
    return DigestStatusResponse(
        status=_state["status"],
        current_date=date.today().isoformat(),
        last_run=_state.get("last_run"),
        candidates_count=_state.get("candidates_count"),
        items_used=None,
    )


@app.post("/digest/process", response_model=DigestProcessResponse)
async def process_digest(req: DigestProcessRequest):
    """
    接收候选池 → 返回排序打分 + 摘要 + 文章草稿。

    小龙虾通过这个接口完成：
    1. 读取候选池，理解每条的价值
    2. 构造 rank prompt，打分排序
    3. 构造成稿 prompt，生成文章

    注意：实际 LLM 调用由调用方（小龙虾）通过 prompts/ 模块构造，
    本接口返回结构和提示，供小龙虾填充结果。
    """
    _state["status"] = "processing"

    if len(req.candidates) < req.min_items:
        _state["status"] = "idle"
        return DigestProcessResponse(
            status="insufficient_items",
            date=req.date,
            reason=f"候选不足：{len(req.candidates)} < {req.min_items}",
        )

    _state["candidates_count"] = len(req.candidates)

    # 保存候选池
    candidates_file = CANDIDATES_DIR / f"{req.date}.json"
    with open(candidates_file, "w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in req.candidates], f, ensure_ascii=False, indent=2)

    # 构造 rank prompt（小龙虾执行评分的提示）
    rank_prompt = build_rank_prompt(req.candidates)
    write_prompt = build_write_prompt(req.candidates, ranking=[], top_n=min(8, len(req.candidates)))

    rank_prompt_file = CANDIDATES_DIR / f"{req.date}_rank_prompt.txt"
    write_prompt_file = CANDIDATES_DIR / f"{req.date}_write_prompt.txt"
    with open(rank_prompt_file, "w", encoding="utf-8") as f:
        f.write(rank_prompt)
    with open(write_prompt_file, "w", encoding="utf-8") as f:
        f.write(write_prompt)

    _state["status"] = "prompt_ready"
    _state["last_run"] = datetime.now().isoformat()

    return DigestProcessResponse(
        status="prompt_ready",
        date=req.date,
        reason=f"候选 {len(req.candidates)} 条，prompt 已生成。",
        ranking=[],
        summaries={},
        article=None,
    )


@app.get("/digest/prompts/{draft_date}")
async def get_prompts(draft_date: str):
    """获取某天的 rank prompt 和 write prompt 内容"""
    rank_file = CANDIDATES_DIR / f"{draft_date}_rank_prompt.txt"
    write_file = CANDIDATES_DIR / f"{draft_date}_write_prompt.txt"

    if not rank_file.exists():
        raise HTTPException(status_code=404, detail="Prompt 文件不存在，请先调用 /digest/process")

    return {
        "date": draft_date,
        "rank_prompt": rank_file.read_text(encoding="utf-8") if rank_file.exists() else "",
        "write_prompt": write_file.read_text(encoding="utf-8") if write_file.exists() else "",
    }


@app.post("/digest/save-ranking")
async def save_ranking(payload: dict):
    """小龙虾保存排序结果"""
    draft_date = payload.get("date", date.today().isoformat())
    ranking = payload.get("ranking", [])

    if not ranking:
        raise HTTPException(status_code=400, detail="ranking 为空")

    ranking_file = CANDIDATES_DIR / f"{draft_date}_ranking.json"
    with open(ranking_file, "w", encoding="utf-8") as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)

    return {"status": "saved", "file": str(ranking_file)}


@app.post("/digest/save-draft")
async def save_draft(payload: dict):
    """小龙虾保存文章草稿"""
    draft_date = payload.get("date", date.today().isoformat())
    title = payload.get("title", "无标题")
    body = payload.get("body", "")
    items_used = payload.get("items_used", [])

    draft_file = DRAFTS_DIR / f"{draft_date}.md"
    title_file = DRAFTS_DIR / f"{draft_date}_title.txt"
    meta_file = DRAFTS_DIR / f"{draft_date}_meta.json"

    with open(draft_file, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{body}")

    with open(title_file, "w", encoding="utf-8") as f:
        f.write(title)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"date": draft_date, "items_used": items_used}, f, ensure_ascii=False)

    _state["status"] = "done"

    return {"status": "saved", "draft": str(draft_file)}


@app.get("/digest/draft/{draft_date}")
async def get_draft(draft_date: str):
    """读取某天草稿"""
    draft_file = DRAFTS_DIR / f"{draft_date}.md"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="草稿不存在")
    return {"date": draft_date, "content": draft_file.read_text(encoding="utf-8")}


@app.get("/digest/ranking/{draft_date}")
async def get_ranking(draft_date: str):
    """读取某天排序结果"""
    ranking_file = CANDIDATES_DIR / f"{draft_date}_ranking.json"
    if not ranking_file.exists():
        raise HTTPException(status_code=404, detail="排序结果不存在")
    return {"date": draft_date, "ranking": json.loads(ranking_file.read_text(encoding="utf-8"))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8011)
