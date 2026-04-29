# ai_digest/tool_run.py — Sisyphus 可调用的工具脚本 CLI
# -*- coding: utf-8 -*-
#
# 用法:
#   python -m ai_digest.tool_run collect                    # 收集全部来源
#   python -m ai_digest.tool_run dedup < items.json         # 去重（stdin→stdout）
#   python -m ai_digest.tool_run persist < items.json       # 持久化去重状态
#   cat article.md | python -m ai_digest.tool_run publish   # 发布公众号
#   python -m ai_digest.tool_run cover --title x --out x    # 生成封面图

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from .cover_image import generate_cover_image
from .defaults import build_default_collector, build_default_publisher
from .dedupe import RecentDedupeFilter
from .models import DigestItem
from .settings import load_settings
from .state_store import SqliteStateStore


# ── 序列化辅助 ──────────────────────────────────────────

def _serialize_item(item: DigestItem) -> dict:
    d = asdict(item)
    if isinstance(d.get("published_at"), datetime):
        d["published_at"] = d["published_at"].isoformat()
    return d


def _deserialize_item(d: dict) -> DigestItem:
    published = d.get("published_at")
    if isinstance(published, str):
        d["published_at"] = datetime.fromisoformat(published)
    return DigestItem(**d)


def _json_dump(obj, fp) -> None:
    # Windows: ensure UTF-8 to console / file pipe
    if hasattr(fp, "reconfigure"):
        try:
            fp.reconfigure(encoding="utf-8")
        except Exception:
            pass
    json.dump(obj, fp, ensure_ascii=False, default=str)


def _json_load(fp) -> list:
    return json.load(fp)


# ── 子命令实现 ──────────────────────────────────────────

def cmd_collect() -> None:
    """收集全部来源的热点数据，输出 JSON 到 stdout。"""
    collector = build_default_collector()
    items = collector.collect()
    if collector.errors:
        print("收集器错误:", "; ".join(collector.errors), file=sys.stderr)
    _json_dump([_serialize_item(item) for item in items], sys.stdout)


def cmd_dedup() -> None:
    """从 stdin 读取 JSON items，去重后输出到 stdout。"""
    settings = load_settings()
    store = SqliteStateStore(settings.state_db_path)
    store.initialize()
    deduper = RecentDedupeFilter(state_store=store)

    raw_items = _json_load(sys.stdin)
    items = [_deserialize_item(item) for item in raw_items]

    now = datetime.now(timezone.utc)
    filtered = deduper.filter(items, now=now)
    _json_dump([_serialize_item(item) for item in filtered], sys.stdout)


def cmd_persist() -> None:
    """从 stdin 读取 JSON items，持久化去重状态。"""
    settings = load_settings()
    store = SqliteStateStore(settings.state_db_path)
    store.initialize()
    deduper = RecentDedupeFilter(state_store=store)

    raw_items = _json_load(sys.stdin)
    items = [_deserialize_item(item) for item in raw_items]

    now = datetime.now(timezone.utc)
    deduper.persist(items, now=now)


def cmd_publish(title: str) -> None:
    """从 stdin 读取 Markdown，发布到公众号，输出 JSON 结果。"""
    settings = load_settings()
    markdown = sys.stdin.read()

    publisher = build_default_publisher(settings)
    try:
        draft_id = publisher.publish(markdown, title=title)
        result = {"draft_id": draft_id or ""}
    except Exception as exc:
        result = {"error": str(exc)}

    _json_dump(result, sys.stdout)


def cmd_cover(title: str, output: str) -> None:
    """生成公众号封面图。"""
    data = generate_cover_image(title)
    with open(output, "wb") as f:
        f.write(data)


# ── CLI 入口 ────────────────────────────────────────────

_COMMANDS = {
    "collect": ("收集多来源热点数据", cmd_collect),
    "dedup": ("跨运行去重（stdin → stdout JSON）", lambda: cmd_dedup()),
    "persist": ("持久化去重状态到 SQLite", lambda: cmd_persist()),
    "publish": ("发布公众号草稿（stdin markdown）", lambda: _publish_wrapper()),
    "cover": ("生成封面图", lambda: _cover_wrapper()),
}


def _publish_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="AI 每日新闻速递")
    args, _ = parser.parse_known_args()
    cmd_publish(args.title)


def _cover_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_known_args()[0]
    cmd_cover(args.title, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Digest 工具脚本")
    parser.add_argument("command", nargs="?", choices=list(_COMMANDS), help="子命令")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, remainder = parser.parse_known_args(argv)

    if not args.command:
        _print_help()
        return 0

    try:
        _COMMANDS[args.command][1]()
        return 0
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def _print_help() -> None:
    print("AI Digest 工具脚本 — Sisyphus 可用命令:\n", file=sys.stderr)
    for name, (desc, _) in _COMMANDS.items():
        print(f"  {name:<12} {desc}", file=sys.stderr)
    print(file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
