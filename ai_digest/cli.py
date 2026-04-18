from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .defaults import build_default_runner
from .settings import AppSettings, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 每日新闻速递")
    parser.add_argument("--publish", action="store_true", help="提交到公众号草稿箱")
    parser.add_argument("--dry-run", action="store_true", help="只生成内容，不调用公众号接口")
    parser.add_argument("--output", type=Path, help="把生成的正文写入文件")
    return parser


def main(argv: Sequence[str] | None = None, runner=None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if runner is None:
        settings = load_settings()
        if args.dry_run:
            settings = AppSettings(
                wechat=settings.wechat,
                ark=settings.ark,
                dry_run=True,
                draft_mode=False,
                llm_enabled=settings.llm_enabled,
                state_db_path=settings.state_db_path,
            )
        elif args.publish and settings.wechat:
            settings = AppSettings(
                wechat=settings.wechat,
                ark=settings.ark,
                dry_run=False,
                draft_mode=True,
                llm_enabled=settings.llm_enabled,
                state_db_path=settings.state_db_path,
            )
        runner = build_default_runner(settings=settings)

    result = runner.run()

    print(f"状态: {result.status}")
    if result.error:
        print(f"错误: {result.error}")
    if result.publisher_draft_id:
        print(f"草稿ID: {result.publisher_draft_id}")

    if result.markdown:
        if args.output:
            args.output.write_text(result.markdown, encoding="utf-8")
            print(f"已写入: {args.output}")
        should_print_markdown = bool(not args.output and (args.dry_run or not args.publish))
        if should_print_markdown:
            print(result.markdown, end="" if result.markdown.endswith("\n") else "\n")

    return 0 if result.status in {"composed", "published", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
