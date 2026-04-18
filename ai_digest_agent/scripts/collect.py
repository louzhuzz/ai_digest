"""
scripts/collect.py — 收集当天 AI 热点候选池

复用 ai_digest/collectors，将结果写入 output/candidates/YYYY-MM-DD.json

用法：
    python scripts/collect.py
    python scripts/collect.py --sources github,hackernews,huggingface
    python scripts/collect.py --dry-run
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# ── 导入 ai_digest collectors ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.link import (
    GitHubTrendingCollector,
    HNFrontPageCollector,
    HFTrendingCollector,
    WebNewsIndexCollector,
)

# ── 路径 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output" / "candidates"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def collect_all(sources: list[str], dry_run: bool = False) -> list[dict]:
    """按指定来源收集，返回 DigestItem 字典列表"""
    collectors = {
        "github": GitHubTrendingCollector(),
        "hackernews": HNFrontPageCollector(),
        "huggingface": HFTrendingCollector(),
        "jiqizhixin": WebNewsIndexCollector("机器之心", category="news"),
        "xinzhiyuan": WebNewsIndexCollector("新智元", category="news"),
        "量子位": WebNewsIndexCollector("量子位", category="news"),
    }

    all_items = []

    for src in sources:
        if src not in collectors:
            print(f"[WARN] Unknown source: {src}, skipping.")
            continue
        collector = collectors[src]
        print(f"[*] Collecting from {src}...")
        try:
            if src == "github":
                items = collector.collect()
            elif src == "hackernews":
                items = collector.collect()
            elif src == "huggingface":
                items = collector.collect()
            else:
                # WebNewsIndexCollector 需要 page_url
                page_urls = {
                    "jiqizhixin": "https://www.jiqizhixin.com/",
                    "xinzhiyuan": "https://www.36kr.com/",
                    "量子位": "https://www.qbitai.com/",
                }
                items = collector.collect(page_urls[src])
        except Exception as e:
            print(f"[ERROR] Failed to collect from {src}: {e}")
            continue

        for item in items:
            all_items.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "category": item.category,
                    "summary": item.summary or "",
                    "published_at": (
                        item.published_at.isoformat()
                        if hasattr(item.published_at, "isoformat")
                        else str(item.published_at)
                    ),
                    "dedupe_key": item.dedupe_key,
                    "metadata": item.metadata,
                }
            )
        print(f"    → Got {len(items)} items from {src}")

    return all_items


def main():
    parser = argparse.ArgumentParser(description="收集当天 AI 热点候选池")
    parser.add_argument(
        "--sources",
        default="github,hackernews,huggingface",
        help="数据源，逗号分隔（github/hackernews/huggingface/jiqizhixin/xinzhiyuan/量子位）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只收集不保存",
    )
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]
    today = date.today().isoformat()

    print(f"=== AI Digest Agent — Collect [{today}] ===")
    print(f"Sources: {sources}")

    items = collect_all(sources, dry_run=args.dry_run)
    print(f"\nTotal: {len(items)} items collected")

    if args.dry_run:
        print("[dry-run] 不保存")
        return

    out_file = OUTPUT_DIR / f"{today}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved → {out_file}")


if __name__ == "__main__":
    main()
