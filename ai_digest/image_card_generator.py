# -*- coding: utf-8 -*-
"""贴图卡片生成器 — 将结构化数据渲染为 HTML 并通过 Playwright 截图为 PNG。

卡片类型：cover | content | list | data | compare | closing
设计规范：白色圆角卡片 + 投影，900×1200px，deviceScaleFactor=2（Retina）
设计来源：参考素材目录中的 11 张卡片截图（产品陈大头风格）
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

CARD_TYPES = {"cover", "content", "list", "data", "compare", "closing"}


@dataclass
class CardData:
    """单张贴图卡片的结构化数据。"""

    card_type: str  # cover | content | list | data | compare | closing
    page_num: int = 0  # 右上角装饰页码，0 = 不显示
    title: str = ""
    subtitle: str = ""
    body: str = ""
    items: list[dict[str, str]] = field(default_factory=list)
    highlight_text: str = ""
    data_value: str = ""
    data_label: str = ""
    footer_note: str = ""

    def __post_init__(self) -> None:
        if self.card_type not in CARD_TYPES:
            raise ValueError(
                f"card_type must be one of {CARD_TYPES}, got {self.card_type!r}"
            )


# ---------------------------------------------------------------------------
# 设计规范常量（参考素材：产品陈大头风格）
# ---------------------------------------------------------------------------

# 配色（来自参考图片精确提取）
_COLOR_TEXT = "#333333"
_COLOR_SUB = "#666666"
_COLOR_LIGHT = "#999999"
_COLOR_ACCENT = "#ff6600"
_COLOR_ACCENT_BG = "#fff5eb"
_COLOR_CARD_NUM = "#e0e0e0"
_COLOR_WECHAT_GREEN = "#1aad19"
_COLOR_BG = "#f5f5f5"
_COLOR_QUOTE_BG = "#f5f5f5"
_COLOR_COVER_CIRCLE = "#fde8d8"

_FONT_FAMILY = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif"
)


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------

def _base_css() -> str:
    """返回全局 CSS 重置和通用样式。"""
    return f"""\
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    width: 900px; height: 1200px;
    background: {_COLOR_BG};
    font-family: {_FONT_FAMILY};
    color: {_COLOR_TEXT};
    -webkit-font-smoothing: antialiased;
}}
.card {{
    width: 900px; height: 1200px;
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    display: flex;
    flex-direction: column;
    position: relative;
    padding: 48px 48px 40px;
}}
/* 卡片编号 — 装饰性大号数字，右上角 */
.card-num {{
    position: absolute;
    top: 24px; right: 32px;
    font-size: 120px;
    font-weight: 700;
    color: {_COLOR_CARD_NUM};
    line-height: 1;
    z-index: 0;
    user-select: none;
    pointer-events: none;
    opacity: 0.5;
}}
/* 标题下橙色分隔条 */
.divider {{
    width: 40px; height: 3px;
    background: {_COLOR_ACCENT};
    border-radius: 2px;
    margin: 12px 0 24px;
}}
/* 底栏 — 分割线 + 绿点 + 署名 */
.footer {{
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid #e5e5e5;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: {_COLOR_LIGHT};
}}
.footer .green-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: {_COLOR_WECHAT_GREEN};
}}
/* 引用块 — 左侧橙色边框 */
.quote-box {{
    padding: 24px 24px;
    background: {_COLOR_QUOTE_BG};
    border-left: 4px solid {_COLOR_ACCENT};
    border-radius: 0 8px 8px 0;
    margin: 24px 0;
}}
.quote-title {{
    font-size: 22px;
    font-weight: 600;
    color: {_COLOR_ACCENT};
    margin: 0 0 10px;
}}
.quote-desc {{
    font-size: 20px;
    line-height: 1.6;
    color: {_COLOR_SUB};
    margin: 0;
}}
/* 引用行 — 左侧橙色边框 */
.quote-line {{
    border-left: 4px solid {_COLOR_ACCENT};
    padding-left: 20px;
    font-size: 22px;
    line-height: 1.6;
    color: {_COLOR_TEXT};
    margin-top: 20px;
}}
/* 高亮框 */
.highlight-box {{
    border-left: 4px solid {_COLOR_ACCENT};
    background: {_COLOR_ACCENT_BG};
    border-radius: 0 8px 8px 0;
    padding: 24px 28px;
    font-size: 22px;
    line-height: 1.6;
    color: {_COLOR_TEXT};
    margin-top: 24px;
}}
/* 提醒框 */
.alert-box {{
    background: {_COLOR_ACCENT_BG};
    border: 1px solid #ffd7bc;
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 15px;
    line-height: 1.6;
    color: {_COLOR_TEXT};
    margin-top: 16px;
}}
.alert-box .alert-title {{
    font-size: 16px;
    font-weight: 600;
    color: {_COLOR_ACCENT};
    margin-bottom: 6px;
}}
"""


def _orange_inline(text: str) -> str:
    """将 **xxx** 标记转为橙色 span，\\n 转为 <br>。"""
    text = text.replace("\n", "<br>")
    return re.sub(
        r"\*\*(.+?)\*\*",
        rf'<span style="color:{_COLOR_ACCENT}; font-weight:600;">\1</span>',
        text,
    )


# ---------------------------------------------------------------------------
# 各卡片类型 HTML 渲染（严格遵循参考素材布局）
# ---------------------------------------------------------------------------

def _render_cover(card: CardData) -> str:
    """封面卡片 — 极简轻奢风：居中布局，大标题，装饰圆形，底部分割线+署名。

    设计原则：居中布局，标签在标题上方，副标题在标题下方，底部署名。
    内容占满卡片75%空间，留白约25%。
    """
    title_html = _orange_inline(card.title) if card.title else ""
    return f"""\
<div class="card" style="
    align-items: center;
    text-align: center;
    padding: 56px 60px 48px;
">
    <!-- 装饰圆形：右上角双层 -->
    <div style="
        position: absolute; top: -120px; right: -80px;
        width: 500px; height: 500px;
        background: {_COLOR_COVER_CIRCLE};
        border-radius: 50%;
        z-index: 0;
    "></div>
    <div style="
        position: absolute; top: 80px; right: 60px;
        width: 200px; height: 200px;
        background: {_COLOR_ACCENT_BG};
        border-radius: 50%;
        z-index: 0;
    "></div>
    <!-- 内容区域：垂直分布 -->
    <div style="
        position: relative; z-index: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        width: 100%;
        height: 100%;
    ">
        <!-- 标签：圆角胶囊 -->
        <div style="
            display: inline-block;
            padding: 10px 24px;
            background: {_COLOR_ACCENT};
            color: #ffffff;
            border-radius: 24px;
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 2px;
            margin-top: 80px;
            width: fit-content;
        ">AI DAILY DIGEST</div>
        <!-- 弹性空间：标题前 -->
        <div style="flex: 1;"></div>
        <!-- 大标题：居中超大号 -->
        <div style="
            font-size: 64px;
            font-weight: 700;
            line-height: 1.15;
            color: {_COLOR_TEXT};
            margin: 0 40px;
            max-width: 700px;
            letter-spacing: -0.5px;
        ">{title_html}</div>
        <!-- 弹性空间：标题后 -->
        <div style="flex: 1;"></div>
        <!-- 副标题 -->
        <div style="
            font-size: 24px;
            line-height: 1.6;
            color: {_COLOR_SUB};
            margin: 0 0 40px;
            max-width: 600px;
            font-weight: 400;
        ">{card.subtitle}</div>
        <!-- 日期 -->
        <div style="
            font-size: 18px;
            color: {_COLOR_LIGHT};
            letter-spacing: 1px;
            margin-bottom: 32px;
        ">{card.body}</div>
        <!-- 底部分割线 -->
        <div style="
            width: 48px; height: 4px;
            background: {_COLOR_ACCENT};
            border-radius: 2px;
            margin-bottom: 16px;
        "></div>
        <!-- 底部公众号署名 -->
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 16px;
            color: {_COLOR_SUB};
            margin-bottom: 24px;
        ">
            <div style="
                width: 10px; height: 10px;
                border-radius: 50%;
                background: {_COLOR_WECHAT_GREEN};
            "></div>
            <span>{card.footer_note or "AI 开发者日报"}</span>
        </div>
    </div>
</div>"""


def _render_content(card: CardData) -> str:
    """内容卡片 — 编号 + 标题 + 橙色分隔条 + 正文要点 + 引用框。"""
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    quote_box = ""
    if card.highlight_text:
        quote_box = f'<div class="quote-box"><div class="quote-title">重点</div><div class="quote-desc">{card.highlight_text}</div></div>'
    body_html = _orange_inline(card.body) if card.body else ""
    return f"""\
<div class="card">
    {card_num}
    <h2 style="
        font-size: 48px;
        font-weight: 700;
        line-height: 1.2;
        color: {_COLOR_TEXT};
        margin: 0 0 16px;
        position: relative; z-index: 1;
    ">{card.title}</h2>
    <div class="divider"></div>
    <div style="
        font-size: 28px;
        line-height: 1.8;
        color: {_COLOR_TEXT};
        position: relative; z-index: 1;
        flex: 1;
    ">{body_html}</div>
    {quote_box}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>
</div>"""


def _render_list(card: CardData) -> str:
    """列表卡片 — 编号 + 标题 + 分隔条 + 大步骤圆圈列表 + 引用行。"""
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    items_html = ""
    for idx, item in enumerate(card.items, 1):
        keyword = item.get("keyword", "")
        desc = item.get("desc", "")
        items_html += f"""\
<div style="display: flex; gap: 24px; margin-bottom: 28px; align-items: flex-start;">
    <div style="
        width: 48px; height: 48px;
        border-radius: 50%;
        background: {_COLOR_ACCENT};
        color: #ffffff;
        font-size: 24px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    ">{idx}</div>
    <div style="flex: 1;">
        <div style="font-size: 28px; font-weight: 700; color: {_COLOR_TEXT}; line-height: 1.3;">{keyword}</div>
        <div style="font-size: 22px; color: {_COLOR_SUB}; line-height: 1.6; margin-top: 8px;">{desc}</div>
    </div>
</div>"""
    quote = ""
    if card.body:
        quote = f'<div class="quote-line">{card.body}</div>'
    return f"""\
<div class="card">
    {card_num}
    <h2 style="
        font-size: 48px;
        font-weight: 700;
        line-height: 1.2;
        color: {_COLOR_TEXT};
        margin: 0 0 16px;
        position: relative; z-index: 1;
    ">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1;">{items_html}</div>
    {quote}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>
</div>"""


def _render_data(card: CardData) -> str:
    """数据卡片 — 编号 + 标题 + 分隔条 + 超大数字 + 标签 + 引用行。"""
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    subtitle_html = ""
    if card.subtitle:
        subtitle_html = f'<div style="font-size:24px; color:{_COLOR_SUB}; margin-top:16px;">{card.subtitle}</div>'
    data_block = ""
    if card.data_value:
        data_block = f"""\
<div style="text-align: center; padding: 48px 0; margin: 32px 0;">
    <div style="
        font-size: 120px;
        font-weight: 700;
        color: {_COLOR_ACCENT};
        line-height: 1;
        margin-bottom: 16px;
    ">{card.data_value}</div>
    <div style="
        font-size: 28px;
        color: {_COLOR_SUB};
    ">{card.data_label}</div>
</div>"""

    quote = ""
    if card.body:
        quote = f'<div class="quote-line">{card.body}</div>'

    return f"""\
<div class="card">
    {card_num}
    <h2 style="
        font-size: 48px;
        font-weight: 700;
        line-height: 1.2;
        color: {_COLOR_TEXT};
        margin: 0 0 16px;
        position: relative; z-index: 1;
    ">{card.title}</h2>
    <div class="divider"></div>
    {subtitle_html}
    {data_block}
    {quote}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>
</div>"""


def _render_compare(card: CardData) -> str:
    """对比卡片 — 编号 + 标题 + 分隔条 + 大对比行。"""
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    rows_html = ""
    for item in card.items:
        name = item.get("name", "")
        tag = item.get("tag", "")
        value = item.get("value", "")
        desc = item.get("desc", "")
        is_highlight = item.get("highlight", "") == "true"
        bg = _COLOR_ACCENT_BG if is_highlight else _COLOR_QUOTE_BG
        name_color = _COLOR_ACCENT if is_highlight else _COLOR_TEXT
        tag_html = (
            f'<span style="font-size:16px; padding:4px 14px; border-radius:6px; '
            f'background:{_COLOR_ACCENT}; color:#fff; font-weight:600; margin-left:12px;">'
            f'{tag}</span>' if tag else ""
        )
        desc_html = f'<div style="font-size:20px; color:{_COLOR_SUB}; margin-top:6px;">{desc}</div>' if desc else ""
        rows_html += f"""\
<div style="
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 28px;
    border-radius: 12px;
    background: {bg};
    margin-bottom: 16px;
">
    <div>
        <div style="display: flex; align-items: center;">
            <span style="font-size: 28px; font-weight: 700; color: {name_color};">{name}</span>
            {tag_html}
        </div>
        {desc_html}
    </div>
    <div style="font-size: 36px; font-weight: 700; color: {_COLOR_ACCENT};">{value}</div>
</div>"""

    quote = ""
    if card.body:
        quote = f'<div class="quote-line">{card.body}</div>'

    return f"""\
<div class="card">
    {card_num}
    <h2 style="
        font-size: 48px;
        font-weight: 700;
        line-height: 1.2;
        color: {_COLOR_TEXT};
        margin: 0 0 16px;
        position: relative; z-index: 1;
    ">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1;">{rows_html}</div>
    {quote}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>
</div>"""


def _render_closing(card: CardData) -> str:
    """结尾卡片 — 标题 + 正文 + 高亮引导框。字大醒目。"""
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    highlight = ""
    if card.highlight_text:
        highlight = f'<div class="highlight-box">{card.highlight_text}</div>'

    return f"""\
<div class="card">
    {card_num}
    <h2 style="
        font-size: 48px;
        font-weight: 700;
        line-height: 1.2;
        color: {_COLOR_TEXT};
        margin: 0 0 12px;
        position: relative; z-index: 1;
    ">{card.title}</h2>
    <div class="divider"></div>
    <div style="
        font-size: 26px;
        line-height: 1.7;
        color: {_COLOR_SUB};
        position: relative; z-index: 1;
        flex: 1;
    ">{card.body}</div>
    {highlight}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>
</div>"""


_RENDERERS: dict[str, Any] = {
    "cover": _render_cover,
    "content": _render_content,
    "list": _render_list,
    "data": _render_data,
    "compare": _render_compare,
    "closing": _render_closing,
}


def render_html(card: CardData, account: str = "AI 开发者日报") -> str:
    """将单张 CardData 渲染为完整的 HTML 页面字符串。"""
    body_html = _RENDERERS[card.card_type](card)

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=900, initial-scale=1.0">
<style>
{_base_css()}
</style>
</head>
<body style="margin:0; padding:0; background:{_COLOR_BG};">
{body_html}
</body>
</html>"""


def render_image(card: CardData, output_path: str | Path) -> Path:
    """使用 Playwright 将 CardData 渲染为 PNG 截图。"""
    from playwright.sync_api import sync_playwright

    html = render_html(card)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        tmp_html = f.name

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
        page.goto(f"file:///{tmp_html.replace(chr(92), '/')}")
        page.wait_for_timeout(500)
        page.screenshot(path=str(output), type="png")
        browser.close()

    Path(tmp_html).unlink(missing_ok=True)
    return output


def _parse_card_data(data: dict[str, Any]) -> CardData:
    """从 JSON dict 构造 CardData。"""
    return CardData(
        card_type=data.get("card_type", "content"),
        page_num=int(data.get("page_num", 0)),
        title=data.get("title", ""),
        subtitle=data.get("subtitle", ""),
        body=data.get("body", ""),
        items=data.get("items", []),
        highlight_text=data.get("highlight_text", ""),
        data_value=data.get("data_value", ""),
        data_label=data.get("data_label", ""),
        footer_note=data.get("footer_note", ""),
    )


def generate_cards(json_path: str | Path, output_dir: str | Path) -> list[Path]:
    """批量生成卡片 PNG：读取 JSON 文件，输出到指定目录。"""
    json_path = Path(json_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        cards_data = json.load(f)

    results: list[Path] = []
    for idx, card_dict in enumerate(cards_data):
        card = _parse_card_data(card_dict)
        suffix = card.card_type
        page = card.page_num if card.page_num else idx
        filename = f"card_{idx:02d}_p{page}_{suffix}.png"
        out = render_image(card, output_dir / filename)
        results.append(out)

    return results


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m ai_digest.image_card_generator <input.json> <output_dir>")
        sys.exit(1)

    json_file = sys.argv[1]
    out_dir = sys.argv[2]
    paths = generate_cards(json_file, out_dir)
    for p in paths:
        print(p)
