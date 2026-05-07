# -*- coding: utf-8 -*-
"""公众号封面图生成器 — 杂志封面风，深色主题 + 半透明几何元素 + 自动字号

设计灵感：WIRED / MIT Technology Review 式编辑封面
- 深色渐变背景 + 半透明几何叠加
- 右半幅暖色圆形区域形成视觉重心
- 大字标题居中，自动适配
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── 画布（2.35:1，微信封面标准比例） ─────────────────
W, H = 900, 383

# ── 配色 ────────────────────────────────────────────────
BG_TOP    = (17,  24,  39)   # #111827 深石板灰
BG_BOT    = (30,  41,  59)   # #1E293B 浅石板灰
ACCENT_A  = (245, 158, 11)   # #F59E0B 暖琥珀色
ACCENT_B  = (6,   182, 212)  # #06B6D4 青色
TEXT_W    = (248, 250, 252)  # #F8FAFC 近白
TEXT_M    = (148, 163, 184)  # #94A3B8 银灰
TEXT_DIM  = (100, 116, 139)  # #64748B 更深灰

# ── 可用空间 ────────────────────────────────────────────
MAX_TEXT_W = W - 140          # 760px
TITLE_TOP  = 80
TITLE_BOT  = 320

FONT_CANDIDATES = [
    # 来自环境变量（最优先）
    os.environ.get("AI_DIGEST_FONT_PATH", ""),
    # Windows
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    # Linux/macOS
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "~/.fonts/NotoSansCJKsc-Bold.otf",
    "/System/Library/Fonts/PingFang.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (p for p in FONT_CANDIDATES if p):  # 跳过空路径
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _split_by_chars(text: str, max_chars: int) -> list[str]:
    chars = list(text.replace(" ", ""))
    lines = []
    for i in range(0, len(chars), max_chars):
        lines.append("".join(chars[i:i + max_chars]))
        if len(lines) >= 2:
            break
    return lines if lines else [text]


def _auto_size_title(
    title: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(64, 24, -4):
        font = _load_font(size)
        cpl = max(3, int(max_width / (size * 0.55)))
        lines = _split_by_chars(title, cpl)
        if len(lines) > 2:
            continue
        if all(font.getlength(l) <= max_width for l in lines):
            return font, lines, size
    font = _load_font(24)
    return font, _split_by_chars(title, int(max_width / 14)), 24


def _hex_to_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha


def _gradient_bg(draw, w: int, h: int) -> None:
    """绘制垂直渐变背景。"""
    for y in range(h):
        ratio = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def generate_cover_image(title: str, subtitle: str = "") -> bytes:
    # ── 基础画布（RGBA 以便 alpha 合成） ──────────────
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_base = ImageDraw.Draw(base)
    _gradient_bg(draw_base, W, H)

    # ── 几何装饰层 ────────────────────────────────────
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 大暖色椭圆（右半幅，低透明度形成光晕）
    od.ellipse([500, -100, 920, 350], fill=(*ACCENT_A, 16))

    # 中青色椭圆（叠加，增加层次）
    od.ellipse([560, -50, 860, 280], fill=(*ACCENT_B, 14))

    # 右上角小实心圆点（纯色点缀）
    od.ellipse([840, 20, 875, 55], fill=(*ACCENT_A, 200))

    # 右上角小方点
    od.rectangle([815, 30, 830, 45], fill=(*ACCENT_B, 180))

    # 左侧竖线装饰
    od.rectangle([18, 110, 20, 270], fill=(*ACCENT_A, 40))
    od.rectangle([26, 140, 28, 230], fill=(*TEXT_M, 60))

    base = Image.alpha_composite(base, overlay)

    # ── 转为 RGB（兼容性最好） ──────────────────────
    final = Image.new("RGB", (W, H), BG_TOP)
    final.paste(base, (0, 0), base)
    draw = ImageDraw.Draw(final)

    # ── 标签 ──────────────────────────────────────────
    tag_font = _load_font(12)
    draw.text((60, 30), "AI DAILY DIGEST", font=tag_font, fill=TEXT_M)
    # 标签下琥珀色短线
    draw.rectangle((60, 48, 135, 49), fill=ACCENT_A)

    # ── 标题 ──────────────────────────────────────────
    title_font, lines, font_size = _auto_size_title(title, MAX_TEXT_W)
    line_h = int(font_size * 1.22)
    total_h = len(lines) * line_h
    ty = TITLE_TOP + (TITLE_BOT - TITLE_TOP - total_h) // 2

    for line in lines:
        lw = title_font.getlength(line)
        draw.text(((W - lw) / 2, ty), line, font=title_font, fill=TEXT_W)
        ty += line_h

    # ── 副标题 ────────────────────────────────────────
    if subtitle:
        sub_font = _load_font(16)
        lw = sub_font.getlength(subtitle)
        draw.text(((W - lw) / 2, ty + 8), subtitle, font=sub_font, fill=TEXT_M)
        ty += 30

    # ── 底部 ──────────────────────────────────────────
    foot_y = max(ty + 18, 330)
    draw.rectangle((60, foot_y, W - 60, foot_y), fill=TEXT_DIM)
    date_str = datetime.now().strftime("%Y-%m-%d")
    src = f"码途日志  ·  {date_str}"
    foot_font = _load_font(12)
    draw.text((60, foot_y + 7), src, font=foot_font, fill=TEXT_M)

    # 底边装饰线
    draw.rectangle((24, H - 8, W - 24, H - 8), fill=(51, 65, 85))

    output = io.BytesIO()
    final.save(output, format="PNG")
    return output.getvalue()
