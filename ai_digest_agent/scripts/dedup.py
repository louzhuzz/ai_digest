"""
scripts/dedup.py — 去重脚本

复用 ai_digest/state_store.py 的 SqliteStateStore 做 simhash 去重。
读取当天候选池，输出去重后结果。

用法：
    python scripts/dedup.py
    python scripts/dedup.py --date 2026-04-17
    python scripts/dedup.py --dry-run
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.link import SqliteStateStore


# ── 路径 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CANDIDATES_DIR = ROOT / "output" / "candidates"
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = STATE_DIR / "digest.db"


def dedupe_items(items: list[dict], store: SqliteStateStore, days: int = 7, persist: bool = True) -> tuple[list[dict], list[dict]]:
    """
    对候选池做精确去重（基于 dedupe_key）。

    规则：
    - dedupe_key 已在 7 天内出现 -> 视为重复，去重
    - 首次出现 -> 保留

    Args:
        items: 候选条目列表
        store: SqliteStateStore 实例
        days: 去重时间窗口，默认 7 天
        persist: 是否写入 SQLite，默认 True

    Returns:
        (kept, dropped) — 保留的条目 和 被去重的条目
    """
    store.initialize()
    recent_keys: set[str] = set(
        store.load_recent_dedupe_keys(days=days, now=datetime.now(timezone.utc)).keys()
    )

    kept = []
    dropped = []
    new_items_to_upsert = []

    for item in items:
        dedupe_key = item.get("dedupe_key", "")
        if not dedupe_key:
            dedupe_key = item.get("url", "") or item.get("title", "")

        if dedupe_key in recent_keys:
            dropped.append(item)
        else:
            kept.append(item)
            recent_keys.add(dedupe_key)
            new_items_to_upsert.append(item)

    # 持久化新条目
    if persist and new_items_to_upsert:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "dedupe_key": item.get("dedupe_key", item.get("url", "")),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_at": _parse_datetime(item.get("published_at", "")),
                "seen_at": now,
            }
            for item in new_items_to_upsert
        ]
        try:
            store.upsert_items(rows)
        except Exception as e:
            print(f"[WARN] Failed to persist dedupe state: {e}")

    return kept, dropped


def _parse_datetime(value: str) -> datetime:
    """解析 ISO 字符串或 datetime 为 datetime 对象"""
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.now(timezone.utc)


def main():
    parser = argparse.ArgumentParser(description="AI Digest 去重")
    parser.add_argument(
        "--date",
        default=None,
        help="指定日期（默认今天）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示结果，不保存文件",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="不写入 SQLite（pipeline 内调用时使用，避免重复写入）",
    )
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()
    in_file = CANDIDATES_DIR / f"{target_date}.json"

    if not in_file.exists():
        print(f"[ERROR] 找不到候选池文件：{in_file}")
        print(f"请先运行：python scripts/collect.py")
        sys.exit(1)

    with open(in_file, encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"[*] 读取 {len(candidates)} 条候选（{target_date}）")
    print(f"[*] 精确去重：dedupe_key 在 7 天内已出现则视为重复")

    store = SqliteStateStore(DB_PATH)
    kept, dropped = dedupe_items(candidates, store, persist=not args.no_persist)

    print(f"\n结果：")
    print(f"  保留：{len(kept)} 条")
    print(f"  去重：{len(dropped)} 条")

    if dropped:
        print(f"\n被去重的条目（示例）：")
        for item in dropped[:5]:
            print(f"  - [{item.get('source')}] {item.get('title', '')[:60]}")

    if args.dry_run:
        print(f"\n[dry-run] 不保存结果")
        return

    out_file = CANDIDATES_DIR / f"{target_date}_deduped.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 去重后结果 → {out_file}")


if __name__ == "__main__":
    main()
