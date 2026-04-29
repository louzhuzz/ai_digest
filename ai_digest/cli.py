"""CLI 入口 — 指向 tool_run 工具脚本。"""
from __future__ import annotations

import sys
from typing import Sequence

from .tool_run import main as tool_main


def main(argv: Sequence[str] | None = None) -> int:
    return tool_main(list(argv) if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
