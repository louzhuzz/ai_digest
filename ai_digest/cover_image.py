# -*- coding: utf-8 -*-
"""公众号封面图生成器 — Swiss Editorial 版

设计语言：极简编辑风，深色背景 + 大胆几何色块 + 干净大标题。
致敬 Swiss Design / 杂志封面：大面积色块对冲，克制留白，信息层级分明。
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ── 画布尺寸 ────────────────────────────────────────────────
COVER_SIZE = (640, 360)

# ── 字体候选 ────────────────────────────────────────────────
WINDOWS_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]
WSL_WINDOWS_FONT_CANDIDATES = [
    "/mnt/c/Windows/Fonts/msyh.ttc",
    "/mnt/c/Windows/Fonts/msyhbd.ttc",
    "/mnt/c/Windows/Fonts/simhei.ttf",
]
LINUX_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font_candidates() -> list[str]:
    if os.name == "nt":
        candidates = list(WINDOWS_FONT_CANDIDATES)
    else:
        candidates = list(WSL_WINDOWS_FONT_CANDIDATES) + list(LINUX_FONT_CANDIDATES)
    env_font = os.environ.get("WECHAT_COVER_FONT", "").strip()
    if env_font:
        candidates.insert(0, env_font)
    return candidates


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates():
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_title(title: str, max_chars: int = 13) -> list[str]:
    """按 max_chars 折行，保留语义尽量完整。"""
    compact = " ".join(title.split())
    if len(compact) <= max_chars:
        return [compact]

    lines: list[str] = []
    remaining = compact
    while remaining and len(lines) < 2:
        cut = remaining[:max_chars]
        # 避免在长词中间切断
        if len(remaining) > max_chars and "/" not in cut and "-" not in cut[-3:]:
            # 找最后一个空格
            last_space = cut.rfind(" ")
            if last_space > max_chars // 2:
                cut = cut[:last_space]
        lines.append(cut)
        remaining = remaining[len(cut):].lstrip()
    if remaining:
        lines[-1] = lines[-1][:-1] + "…"
    return lines





def generate_cover_image(title: str) -> bytes:
    """
    生成封面图 — 极简编辑杂志风 (Swiss Design)

    布局:
      ┌──────────────────────────────────────┐
      │  标签  ░░░░░░░░░░░░░░░░░░░░░░ (圆)   │  0
      │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
      │                                       │
      │  ──分隔线──                            │  ~140
      │  大标题（加粗，左对齐）                  │
      │  第二行标题                             │  ~250
      │                                       │
      │  ────────────────────────────── 细线  │  ~300
      │  日期 · 来源                           │
      └──────────────────────────────────────┘  360
    """
    W, H = COVER_SIZE
    char = (20, 20, 22)       # #141416 深炭
    cream = (30, 30, 35)      # #1e1e23（比全黑柔和的暗灰）
    accent = (180, 67, 47)    # #b4432f 赤陶色
    white = (240, 240, 242)   # #f0f0f2 暖白
    muted = (140, 140, 145)   # #8c8c91

    image = Image.new("RGB", COVER_SIZE, char)
    draw = ImageDraw.Draw(image)

    # ── 唯一装饰：右上赤陶大圆 ──────────────────────────
    # 只用一个几何元素，克制感
    draw.ellipse((460, -80, 720, 190), fill=accent)

    # ── 顶部标签 ──────────────────────────────────────
    tag_x0, tag_y0 = 34, 28
    tag_font = _load_font(15)
    draw.text((tag_x0, tag_y0), "AI DAILY DIGEST", font=tag_font, fill=muted)

    # ── 分隔线 ────────────────────────────────────────
    line_y = 52
    line_x1 = 200
    draw.rectangle((tag_x0, line_y, tag_x0 + line_x1, line_y + 1), fill=muted)

    # ── 大标题 ────────────────────────────────────────
    title_font = _load_font(48)
    lines = _wrap_title(title)
    x = 34
    y = 90
    for line in lines:
        # 文字阴影（微立体感）
        shadow_offset = 2
        draw.text((x + shadow_offset, y + shadow_offset), line,
                  font=title_font, fill=(10, 10, 12, 255))
        draw.text((x, y), line, font=title_font, fill=white)
        y += 60

    # ── 标题下方装饰细线 ─────────────────────────────
    deco_y = y + 16
    draw.rectangle((x, deco_y, x + 80, deco_y + 2), fill=accent)

    # ── 底部信息 ──────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    sub_font = _load_font(15)
    source_text = f"码途日志  ·  {date_str}"
    # 底部分隔线
    foot_y = H - 52
    draw.rectangle((x, foot_y, x + 420, foot_y + 1), fill=(50, 50, 55))
    draw.text((x, foot_y + 10), source_text, font=sub_font, fill=muted)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True, progressive=True)
    return output.getvalue()
