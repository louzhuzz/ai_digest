"""
scripts/write_article.py — 小龙虾生成文章草稿

小龙虾调用此脚本，把候选池处理成文章草稿。

用法：
    python scripts/write_article.py
    python scripts/write_article.py --date 2026-04-17
    python scripts/write_article.py --candidates path/to/candidates.json
    python scripts/write_article.py --ranked path/to/ranked.json  # 已排序时跳过排序步骤

工作流程：
    1. 读取去重后的候选池
    2. 生成排序（build_rank_prompt → 小龙虾打分）
    3. 生成文章（build_write_prompt → 小龙虾成稿）
    4. 保存 ranking.json + draft.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from prompts import build_rank_prompt, build_write_prompt


# ── 路径 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CANDIDATES_DIR = ROOT / "output" / "candidates"
DRAFTS_DIR = ROOT / "output" / "drafts"
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


def load_candidates(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_ranking(ranking: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)


def save_draft(title: str, body: str, path: Path) -> None:
    content = f"# {title}\n\n{body}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_candidate_items(raw: list[dict]) -> list:
    """
    把原始 dict 转成一个简化对象列表，
    供 prompts/build_rank_prompt 使用 CandidateItem 字段。
    """
    items = []
    for i, item in enumerate(raw):
        obj = type("CandidateItem", (), {
            "idx": i,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "summary": item.get("summary", ""),
            "category": item.get("category", "news"),
            "published_at": item.get("published_at", ""),
            "metadata": item.get("metadata", {}),
        })()
        items.append(obj)
    return items


def main():
    parser = argparse.ArgumentParser(description="小龙虾生成文章草稿")
    parser.add_argument(
        "--date",
        default=None,
        help="指定日期（默认今天）",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="候选池 JSON 文件路径（默认：output/candidates/<date>_deduped.json）",
    )
    parser.add_argument(
        "--ranked",
        type=Path,
        default=None,
        help="已有排序结果 JSON（跳过排序步骤）",
    )
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()

    # ── 读取候选池 ──────────────────────────────────────────────────────
    if args.candidates:
        candidates_path = args.candidates
    else:
        candidates_path = CANDIDATES_DIR / f"{target_date}_deduped.json"

    if not candidates_path.exists():
        print(f"[ERROR] 找不到候选池文件：{candidates_path}")
        print(f"请先运行：python scripts/run_pipeline.py")
        sys.exit(1)

    raw_candidates = load_candidates(candidates_path)
    print(f"[*] 读取 {len(raw_candidates)} 条候选")

    candidate_items = build_candidate_items(raw_candidates)

    # ── 排序 ────────────────────────────────────────────────────────────
    if args.ranked:
        ranking = load_candidates(args.ranked)
        print(f"[*] 使用已有排序结果：{args.ranked}")
    else:
        print(f"\n[*] Step 1: 构造排序 prompt...")
        rank_prompt_text = build_rank_prompt(candidate_items)

        rank_prompt_path = CANDIDATES_DIR / f"{target_date}_rank_prompt.txt"
        with open(rank_prompt_path, "w", encoding="utf-8") as f:
            f.write(rank_prompt_text)
        print(f"[*] Rank prompt → {rank_prompt_path}")
        print(f"\n{'='*60}")
        print("小龙虾：请处理这个 prompt")
        print(f"  1. 阅读 {rank_prompt_path}")
        print(f"  2. 生成 JSON 格式排序结果")
        print(f"  3. 保存到 {CANDITS_DIR := str(CANDIDATES_DIR / f'{target_date}_ranking.json')}")
        print(f"  4. 继续运行：python scripts/write_article.py --ranked {CANDITS_DIR}")
        print(f"{'='*60}")
        return

    print(f"\n[*] Step 2: 构造成稿 prompt...")
    write_prompt_text = build_write_prompt(candidate_items, ranking)

    write_prompt_path = CANDIDATES_DIR / f"{target_date}_write_prompt.txt"
    with open(write_prompt_path, "w", encoding="utf-8") as f:
        f.write(write_prompt_text)
    print(f"[*] Write prompt → {write_prompt_path}")
    print(f"\n{'='*60}")
    print("小龙虾：请处理这个 prompt")
    print(f"  1. 阅读 {write_prompt_path}")
    print(f"  2. 生成 Markdown 文章")
    print(f"  3. 保存标题到 {DRAFTS_DIR / f'{target_date}_title.txt'}")
    print(f"  4. 保存正文到 {DRAFTS_DIR / f'{target_date}.md'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
