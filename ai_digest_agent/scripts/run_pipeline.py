"""
scripts/run_pipeline.py — 一键运行 collect → dedup → 生成草稿

用法：
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --skip-collect   # 跳过收集，只处理现有候选池
    python scripts/run_pipeline.py --date 2026-04-17
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
CANDIDATES_DIR = ROOT / "output" / "candidates"
PROMPTS_DIR = ROOT / "output" / "prompts"

sys.path.insert(0, str(ROOT))
from lib.link import SqliteStateStore
from scripts.dedup import dedupe_items
from prompts import build_rank_prompt


def run_step(name: str, cmd: list[str], cwd: Path) -> bool:
    print(f"\n{'='*50}")
    print(f"[*] {name}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"[ERROR] {name} failed")
        print(result.stderr[-500:] if result.stderr else "")
        return False
    print(f"[OK] {name} done")
    return True


def main():
    parser = argparse.ArgumentParser(description="AI Digest Agent pipeline")
    parser.add_argument("--skip-collect", action="store_true", help="Skip collect step")
    parser.add_argument(
        "--date",
        default=None,
        help="Date (default: today)",
    )
    parser.add_argument(
        "--sources",
        default="github,hackernews,huggingface",
        help="Data sources (ignored when --skip-collect)",
    )
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()

    # Step 1: 收集
    if not args.skip_collect:
        ok = run_step(
            "Step 1: Collect",
            ["python", "scripts/collect.py", "--sources", args.sources],
            ROOT,
        )
        if not ok:
            sys.exit(1)
    else:
        print("[SKIP] Collect step")

    # Step 2: 去重（import 方式调用，同一进程，不重复 persist）
    candidates_file = CANDIDATES_DIR / f"{target_date}.json"
    deduped_file = CANDIDATES_DIR / f"{target_date}_deduped.json"

    if not candidates_file.exists():
        print(f"[ERROR] No candidates file: {candidates_file}")
        sys.exit(1)

    with open(candidates_file, encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"\n{'='*50}")
    print(f"[*] Step 2: Dedupe (in-process)")
    print(f"{'='*50}")

    store = SqliteStateStore(ROOT / "state" / "digest.db")
    kept, dropped = dedupe_items(candidates, store)

    print(f"Kept: {len(kept)}, Dropped: {len(dropped)}")

    with open(deduped_file, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    print(f"[OK] Deduped: {deduped_file}")

    # Step 3: 准备小龙虾 rank prompt
    if not kept:
        print("[ERROR] No candidates after dedup")
        sys.exit(1)

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    class C:
        def __init__(self, d):
            self.__dict__.update(d)
            self.metadata = d.get("metadata", {})

    rank_prompt_text = build_rank_prompt([C(c) for c in kept])
    rank_prompt_file = PROMPTS_DIR / f"{target_date}_rank_prompt.txt"
    with open(rank_prompt_file, "w", encoding="utf-8") as f:
        f.write(rank_prompt_text)

    print(f"\n{'='*50}")
    print(f"[*] Xiaolongxia: check {rank_prompt_file}")
    print(f"{'='*50}")
    print(f"[OK] Rank prompt saved: {rank_prompt_file}")
    print(f"[NEXT] After Xiaolongxia writes ranking to:")
    print(f"       {CANDIDATES_DIR / f'{target_date}_ranking.json'}")
    print(f"       Run: python scripts/write_article.py --date {target_date}")


if __name__ == "__main__":
    main()
