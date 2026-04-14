from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COVER_SIZE = (640, 360)
MAX_TITLE_LINES = 2
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


def _wrap_title(title: str, max_chars: int = 12) -> list[str]:
    compact = " ".join(title.split())
    if len(compact) <= max_chars:
        return [compact]

    lines: list[str] = []
    remaining = compact
    while remaining and len(lines) < MAX_TITLE_LINES:
        lines.append(remaining[:max_chars])
        remaining = remaining[max_chars:]
    if remaining:
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def generate_cover_image(title: str) -> bytes:
    image = Image.new("RGB", COVER_SIZE, "#0f172a")
    draw = ImageDraw.Draw(image)

    # Build a simple layered background so the generated cover does not look flat.
    for idx, color in enumerate(["#0f172a", "#172554", "#1d4ed8"]):
        inset = idx * 28
        draw.rounded_rectangle(
            (inset, inset, COVER_SIZE[0] - inset, COVER_SIZE[1] - inset),
            radius=32,
            fill=color,
        )

    draw.ellipse((440, -30, 700, 220), fill="#22c55e")
    draw.ellipse((360, 150, 620, 420), fill="#38bdf8")

    tag_font = _load_font(24)
    title_font = _load_font(46)
    subtitle_font = _load_font(20)

    draw.rounded_rectangle((36, 34, 210, 76), radius=18, fill="#111827")
    draw.text((54, 44), "AI DAILY DIGEST", font=tag_font, fill="#f8fafc")

    lines = _wrap_title(title)
    y = 110
    for line in lines:
        draw.text((40, y), line, font=title_font, fill="#ffffff")
        y += 58

    today = datetime.now().strftime("%Y-%m-%d")
    subtitle = f"码途日志 · {today}"
    draw.text((42, 290), subtitle, font=subtitle_font, fill="#e2e8f0")

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=72, optimize=True, progressive=True)
    return output.getvalue()
