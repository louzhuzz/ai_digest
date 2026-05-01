# ai_digest/tool_run.py — Sisyphus 可调用的工具脚本 CLI
# -*- coding: utf-8 -*-
#
# 用法:
#   python -m ai_digest.tool_run collect                    # 收集全部来源
#   python -m ai_digest.tool_run dedup < items.json         # 去重（stdin→stdout）
#   python -m ai_digest.tool_run persist < items.json       # 持久化去重状态
#   cat article.md | python -m ai_digest.tool_run publish   # 发布公众号
#   python -m ai_digest.tool_run cover --title x --out x    # 生成封面图
#   python -m ai_digest.tool_run cards --input cards.json --output-dir data/cards

from __future__ import annotations

import argparse
import glob as glob_mod
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone

# cards 子命令在 cmd_cards 中延迟导入 image_card_generator

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


# ── access token 辅助 ────────────────────────────────────

def _get_access_token(settings) -> str:
    """从 settings 获取微信 access_token。"""
    from .auth import WeChatAccessTokenClient
    if not settings.wechat:
        raise RuntimeError("未配置 WECHAT_APPID/WECHAT_APPSECRET")
    client = WeChatAccessTokenClient(
        appid=settings.wechat.appid,
        appsecret=settings.wechat.appsecret,
    )
    token = client.get_access_token()
    if not token:
        raise RuntimeError("获取 access_token 失败")
    return token


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


def cmd_publish(title: str, file_path: str | None = None) -> None:
    """从文件或 stdin 读取 Markdown，发布到公众号，输出 JSON 结果。
    
    Args:
        title: 文章标题
        file_path: 可选，直接指定 markdown 文件路径（避免 PowerShell 管道编码问题）
    """
    settings = load_settings()
    
    if file_path:
        # 直接从文件读取，使用 UTF-8 编码（避免 PowerShell 管道编码问题）
        with open(file_path, "r", encoding="utf-8") as f:
            markdown = f.read()
    else:
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


def cmd_cards(input_path: str, output_dir: str) -> None:
    """从 JSON 生成贴图卡片 PNG。"""
    from .image_card_generator import generate_cards

    paths = generate_cards(input_path, output_dir)

    result = {"cards": [str(p) for p in paths], "count": len(paths)}
    _json_dump(result, sys.stdout)


# ── CLI 入口 ────────────────────────────────────────────

_COMMANDS = {
    "collect": ("收集多来源热点数据", cmd_collect),
    "dedup": ("跨运行去重（stdin → stdout JSON）", lambda: cmd_dedup()),
    "persist": ("持久化去重状态到 SQLite", lambda: cmd_persist()),
    "publish": ("发布公众号草稿（stdin markdown）", lambda: _publish_wrapper()),
    "cover": ("生成封面图", lambda: _cover_wrapper()),
    "cards": ("生成贴图卡片 PNG（从 JSON）", lambda: _cards_wrapper()),
    "publish-newspic": ("发布贴图（newspic）草稿", lambda: _publish_newspic_wrapper()),
}


def _publish_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="AI 每日新闻速递")
    parser.add_argument("--file", default=None, help="Markdown 文件路径（推荐，避免 PowerShell 编码问题）")
    args, _ = parser.parse_known_args()
    cmd_publish(args.title, file_path=args.file)


def _cover_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_known_args()[0]
    cmd_cover(args.title, args.output)


def _cards_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="卡片数据 JSON 文件路径")
    parser.add_argument("--output-dir", default="data/cards", help="输出目录（默认 data/cards）")
    args = parser.parse_known_args()[0]
    cmd_cards(args.input, args.output_dir)


def cmd_publish_newspic(title: str, images: list[str], content: str = "", dry_run: bool = False) -> None:
    """发布贴图（newspic）类型的公众号草稿。"""
    settings = load_settings()
    from .publishers.wechat import WeChatDraftPublisher
    pub = WeChatDraftPublisher(
        access_token=None if dry_run else _get_access_token(settings),
        dry_run=dry_run,
    )
    media_id = pub.publish_newspic(image_paths=images, title=title, content=content)
    _json_dump({"draft_id": media_id, "last_payload": pub.last_payload}, sys.stdout)


def _publish_newspic_wrapper() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="AI 每日新闻速递")
    parser.add_argument("--images", nargs="+", help="图片文件路径列表")
    parser.add_argument("--image-dir", help="图片目录（自动选取所有 .png/.jpg 文件）")
    parser.add_argument("--content", default="", help="正文内容（纯文本）")
    parser.add_argument("--content-file", help="从文件读取正文（UTF-8）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_known_args()[0]
    images = args.images or []
    if args.image_dir:
        patterns = [
            os.path.join(args.image_dir, "*.png"),
            os.path.join(args.image_dir, "*.jpg"),
            os.path.join(args.image_dir, "*.jpeg"),
        ]
        for pat in patterns:
            images.extend(sorted(glob_mod.glob(pat)))
    if not images:
        print("错误: 必须指定 --images 或 --image-dir", file=sys.stderr)
        sys.exit(1)
    content = args.content or ""
    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read()
    cmd_publish_newspic(args.title, images, content=content, dry_run=args.dry_run)


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
