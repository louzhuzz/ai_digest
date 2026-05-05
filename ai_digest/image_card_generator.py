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

CARD_TYPES = {
    "cover", "content", "list", "data", "compare", "closing",
    "content-grid", "content-hero", "content-steps", "content-quote",
}


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
# 设计规范常量
# ---------------------------------------------------------------------------

# 配色体系（暖橙强调 + 深灰正文）
_COLOR_TEXT = "#1d1d1f"
_COLOR_SUB = "#6e6e73"
_COLOR_LIGHT = "#86868b"
_COLOR_ACCENT = "#ff6b21"
_COLOR_ACCENT_BG = "#fff5eb"
_COLOR_ACCENT_DARK = "#e55a1b"
_COLOR_CARD_NUM = "#f0f0f0"
_COLOR_WECHAT_GREEN = "#07c160"
_COLOR_BG = "#f5f5f7"
_COLOR_QUOTE_BG = "#fafafa"

# 封面专用色
_COLOR_COVER_GRADIENT_START = "#ff8c42"
_COLOR_COVER_GRADIENT_END = "#ff6b21"
_COLOR_COVER_PATTERN = "rgba(255,107,33,0.08)"

_FONT_FAMILY = (
    "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Segoe UI', "
    "'Helvetica Neue', Arial, sans-serif"
)
_FONT_MONO = "'SF Mono', 'Fira Code', 'Consolas', monospace"


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
    border-radius: 20px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.055);
    display: flex;
    flex-direction: column;
    position: relative;
    padding: 34px 42px 30px;
    overflow: hidden;
    /* Tier-based font sizes — defaults (tier2) */
    --title-size: 50px;
    --body-size: 34px;
    --data-value-size: 156px;
    --list-keyword-size: 34px;
    --list-desc-size: 26px;
    --grid-value-size: 58px;
    --quote-body-size: 48px;
    --hero-value-size: 156px;
    --cover-title-size: 84px;
    --highlight-size: 28px;
    --tag-size: 20px;
}}
/* tier1: 1-2 cards — largest sizes */
.card[data-tier="1"] {{
    --title-size: 56px;
    --body-size: 36px;
    --data-value-size: 168px;
    --list-keyword-size: 36px;
    --list-desc-size: 28px;
    --grid-value-size: 64px;
    --quote-body-size: 52px;
    --hero-value-size: 168px;
    --cover-title-size: 88px;
    --highlight-size: 30px;
    --tag-size: 22px;
}}
/* tier2: 3-4 cards — medium sizes (default) */
.card[data-tier="2"] {{
    --title-size: 50px;
    --body-size: 34px;
    --data-value-size: 156px;
    --list-keyword-size: 34px;
    --list-desc-size: 26px;
    --grid-value-size: 58px;
    --quote-body-size: 48px;
    --hero-value-size: 156px;
    --cover-title-size: 84px;
    --highlight-size: 28px;
}}
/* tier3: 5-6 cards — smallest sizes */
.card[data-tier="3"] {{
    --title-size: 44px;
    --body-size: 30px;
    --data-value-size: 140px;
    --list-keyword-size: 30px;
    --list-desc-size: 24px;
    --grid-value-size: 52px;
    --quote-body-size: 42px;
    --hero-value-size: 140px;
    --cover-title-size: 76px;
    --highlight-size: 26px;
    --tag-size: 17px;
}}
/* Typography classes using CSS variables */
.card-title {{
    font-size: var(--title-size);
    font-weight: 800;
    line-height: 1.14;
    color: {_COLOR_TEXT};
    letter-spacing: -0.5px;
}}
.card-body {{
    font-size: var(--body-size);
    line-height: 1.56;
    color: {_COLOR_TEXT};
}}
.card-data-value {{
    font-size: var(--data-value-size);
    font-weight: 800;
    color: {_COLOR_ACCENT};
    line-height: 1;
    letter-spacing: -3px;
}}
.card-list-keyword {{
    font-size: var(--list-keyword-size);
    font-weight: 800;
    color: {_COLOR_TEXT};
    line-height: 1.18;
}}
.card-list-desc {{
    font-size: var(--list-desc-size);
    color: {_COLOR_SUB};
    line-height: 1.46;
}}
.card-grid-value {{
    font-size: var(--grid-value-size);
    font-weight: 800;
    color: {_COLOR_ACCENT};
    line-height: 1.05;
    letter-spacing: -1px;
}}
.card-quote-body {{
    font-size: var(--quote-body-size);
    font-weight: 600;
    line-height: 1.34;
    color: {_COLOR_TEXT};
    letter-spacing: 0.5px;
}}
.card-hero-value {{
    font-size: var(--hero-value-size);
    font-weight: 800;
    color: {_COLOR_ACCENT};
    line-height: 1;
    letter-spacing: -3px;
}}
.card-cover-title {{
    font-size: var(--cover-title-size);
    font-weight: 800;
    line-height: 1.08;
    color: {_COLOR_TEXT};
    letter-spacing: -1px;
}}
.card-highlight-box {{
    border-left: 4px solid {_COLOR_ACCENT};
    background: {_COLOR_ACCENT_BG};
    border-radius: 0 12px 12px 0;
    padding: 22px 26px;
    font-size: var(--highlight-size);
    line-height: 1.48;
    color: {_COLOR_TEXT};
    margin-top: 16px;
}}
.card-tag {{
    font-size: var(--tag-size);
    color: #ffffff;
    font-weight: 600;
    letter-spacing: 1px;
}}
/* 卡片编号 — 装饰性大号数字，右上角 */
.card-num {{
    position: absolute;
    top: 14px; right: 24px;
    font-size: 78px;
    font-weight: 800;
    color: {_COLOR_CARD_NUM};
    line-height: 1;
    z-index: 0;
    user-select: none;
    pointer-events: none;
    opacity: 0.65;
}}
/* 标题下橙色分隔条 */
.divider {{
    width: 54px; height: 4px;
    background: linear-gradient(90deg, {_COLOR_ACCENT}, {_COLOR_COVER_GRADIENT_START});
    border-radius: 2px;
    margin: 10px 0 16px;
}}
/* 底栏 — 分割线 + 绿点 + 署名 */
.footer {{
    margin-top: auto;
    padding-top: 10px;
    border-top: 1px solid rgba(0,0,0,0.06);
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    color: {_COLOR_LIGHT};
    position: relative;
    z-index: 1;
}}
.footer .green-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: {_COLOR_WECHAT_GREEN};
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
# Font scale computation (continuous, based on total card count)
# ---------------------------------------------------------------------------

_MAX_CARDS = 10  # design ceiling for font interpolation


def compute_font_scales(total_cards: int) -> dict[str, str]:
    """Compute CSS custom property font sizes based on total card count.

    Linear interpolation between tier1 anchors (1-2 cards, largest)
    and tier3 anchors (5+ cards, smallest) for total_cards 1..10.
    Returns dict of "--var-name": "Npx" entries for inline style injection.
    """
    t = max(1, min(total_cards, _MAX_CARDS))
    scale = (t - 1) / (_MAX_CARDS - 1)  # 0.0..1.0 across cards 1..10

    anchors = {
        "--title-size":        (56, 44),
        "--body-size":         (36, 30),
        "--data-value-size":   (168, 140),
        "--list-keyword-size": (36, 30),
        "--list-desc-size":    (28, 24),
        "--grid-value-size":   (64, 52),
        "--quote-body-size":   (52, 42),
        "--hero-value-size":   (168, 140),
        "--cover-title-size":  (88, 76),
        "--highlight-size":    (30, 26),
        "--tag-size":          (20, 17),
    }

    result = {}
    for var, (v1, v3) in anchors.items():
        val = round(v1 + (v3 - v1) * scale)
        result[var] = f"{val}px"
    return result


# ---------------------------------------------------------------------------
# 各卡片类型 HTML 渲染（严格遵循参考素材布局）
# ---------------------------------------------------------------------------

def _render_cover(card: CardData) -> str:
    """封面卡片 — 杂志封面风。

    设计语言：不对称布局，背景几何纹理，左下角日期胶囊，
    超大标题居左，右侧装饰性几何元素，底部品牌签名。
    """
    title_html = _orange_inline(card.title.replace("\n", "<br>")) if card.title else ""
    tag_text = card.subtitle or "AI DAILY DIGEST"
    return f"""\
<!-- 封面背景层 -->
<div style="
    position: absolute; top: 0; right: 0;
    width: 400px; height: 400px;
    background: radial-gradient(circle at center, {_COLOR_COVER_PATTERN} 0%, transparent 70%);
    z-index: 0;
"></div>
<div style="
    position: absolute; top: 60px; right: 80px;
    width: 200px; height: 200px;
    border: 3px solid {_COLOR_COVER_PATTERN};
    border-radius: 50%;
    z-index: 0;
"></div>
<div style="
    position: absolute; bottom: 180px; right: 40px;
    width: 120px; height: 120px;
    border: 2px solid {_COLOR_COVER_PATTERN};
    border-radius: 50%;
    z-index: 0;
"></div>
<!-- 内容区域 -->
<div style="
    position: relative; z-index: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 48px 56px 38px;
    background: linear-gradient(160deg, #ffffff 60%, {_COLOR_ACCENT_BG} 100%);
    border-radius: 20px;
">
    <!-- 左上角日期胶囊 -->
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 20px;
        background: {_COLOR_ACCENT};
        color: #ffffff;
        border-radius: 24px;
        font-size: var(--tag-size);
        font-weight: 600;
        letter-spacing: 1px;
        width: fit-content;
    ">{tag_text}</div>
    <!-- 弹性空间 -->
    <div style="flex: 1;"></div>
    <!-- 超大标题 -->
    <div class="card-cover-title">{title_html}</div>
    <!-- 副标题/body -->
    {f'''<div style="
        font-size: var(--body-size);
        color: {_COLOR_SUB};
        margin-top: 22px;
        max-width: 680px;
        line-height: 1.42;
    ">{card.body}</div>''' if card.body else ''}
    <!-- 底部品牌签名 -->
    <div style="
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 34px;
    ">
        <div style="
            width: 32px; height: 3px;
            background: {_COLOR_ACCENT};
            border-radius: 2px;
        "></div>
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 16px;
            color: {_COLOR_SUB};
        ">
            <div style="
                width: 8px; height: 8px;
                border-radius: 50%;
                background: {_COLOR_WECHAT_GREEN};
            "></div>
            <span>{card.footer_note or "AI 开发者日报"}</span>
        </div>
    </div>
</div>"""


def _render_content(card: CardData) -> str:
    """内容卡片 — 编辑部风格。

    设计语言：左对齐大标题，橙色分隔条，正文区域充裕，
    右上角装饰页码，底部高亮框（如有），底栏签名。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    body_html = _orange_inline(card.body) if card.body else ""
    highlight = ""
    if card.highlight_text:
        highlight = f'<div class="card-highlight-box">{card.highlight_text}</div>'
    return f"""\
    {card_num}
    <!-- 标题区 -->
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <!-- 正文区 -->
    <div class="card-body" style="
        flex: 1;
        position: relative;
        z-index: 1;
    ">{body_html}</div>
    {highlight}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_list(card: CardData) -> str:
    """列表卡片 — 时间轴风。

    设计语言：左侧竖线 + 圆点连接，右侧内容垂直流动。
    每个条目是一个节点，橙色圆点标记序号，下方连接竖线。
    适合流程、要点列表、分步骤说明。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    items_html = ""
    total = min(len(card.items), 5)
    for idx, item in enumerate(card.items[:5], 1):
        keyword = item.get("keyword", "")
        desc = item.get("desc", "")
        is_last = idx == total
        connector = "" if is_last else f'<div style="width:3px; flex:1; background:linear-gradient(to bottom, {_COLOR_ACCENT}, {_COLOR_ACCENT_BG}); margin-top:8px;"></div>'
        items_html += f"""\
<div style="display: flex; gap: 22px; align-items: stretch;">
    <!-- 左侧时间轴 -->
    <div style="display: flex; flex-direction: column; align-items: center; width: 40px; flex-shrink: 0;">
        <div style="
            width: 44px; height: 44px;
            border-radius: 50%;
            background: {_COLOR_ACCENT};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(255,107,33,0.3);
        ">{idx}</div>
        {connector}
    </div>
    <!-- 右侧内容 -->
    <div style="flex: 1; padding-bottom: {28 if not is_last else 0}px;">
        <div class="card-list-keyword">{keyword}</div>
        <div class="card-list-desc" style="margin-top: 8px;">{desc}</div>
    </div>
</div>"""
    body_html = f'<div style="border-left: 4px solid {_COLOR_ACCENT}; padding-left: 20px; font-size: var(--body-size); line-height: 1.45; color: {_COLOR_TEXT}; margin-top: 14px; position: relative; z-index: 1;">{card.body}</div>' if card.body else ""
    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1;">{items_html}</div>
    {body_html}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_data(card: CardData) -> str:
    """数据卡片 — 仪表盘风。

    设计语言：网格卡片布局，强调数据视觉层次。
    数据值超大号居中，标签置于下方，可选多个数据点（items）。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""

    # 主数据块
    data_block = ""
    if card.data_value:
        data_block = f"""\
<div style="
    text-align: center;
    padding: 58px 0;
    margin: 18px 0;
    background: {_COLOR_QUOTE_BG};
    border-radius: 20px;
">
    <div class="card-data-value">{card.data_value}</div>
    <div style="
        font-size: var(--body-size);
        color: {_COLOR_SUB};
        margin-top: 12px;
        font-weight: 500;
    ">{card.data_label}</div>
</div>"""

    # 附加数据点（网格）
    extra_data = ""
    if card.items:
        cells = ""
        for item in card.items[:4]:
            cells += f"""\
<div style="
    background: {_COLOR_QUOTE_BG};
    border-radius: 16px;
    padding: 20px;
    text-align: center;
">
    <div style="font-size: var(--grid-value-size); font-weight: 800; color: {_COLOR_ACCENT};">{item.get('value', '')}</div>
    <div style="font-size: var(--list-desc-size); color: {_COLOR_SUB}; margin-top: 8px; line-height: 1.35;">{item.get('label', '')}</div>
</div>"""
        extra_data = f"""\
<div style="
    display: grid;
    grid-template-columns: repeat({min(len(card.items), 2)}, 1fr);
    gap: 16px;
    margin-top: 16px;
    position: relative; z-index: 1;
">{cells}</div>"""

    body_html = f'<div style="border-left: 4px solid {_COLOR_ACCENT}; padding-left: 20px; font-size: var(--body-size); line-height: 1.45; color: {_COLOR_TEXT}; margin-top: 14px; position: relative; z-index: 1;">{card.body}</div>' if card.body else ""

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; justify-content: center;">
        {data_block}
        {extra_data}
    </div>
    {body_html}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_compare(card: CardData) -> str:
    """对比卡片 — 对决风。

    设计语言：双栏/多行对决布局，橙色高亮胜出项，
    每行左侧名称 + 右侧数值，背景色区分高下。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    rows_html = ""
    for item in card.items:
        name = item.get("name", "")
        tag = item.get("tag", "")
        value = item.get("value", "")
        desc = item.get("desc", "")
        is_highlight = item.get("highlight", "") == "true"
        bg = "linear-gradient(135deg, {_COLOR_ACCENT_BG}, #fff8f0)".format_map({"_COLOR_ACCENT_BG": _COLOR_ACCENT_BG}) if is_highlight else _COLOR_QUOTE_BG
        border = f"2px solid {_COLOR_ACCENT}" if is_highlight else "2px solid transparent"
        name_color = _COLOR_ACCENT if is_highlight else _COLOR_TEXT
        tag_html = (
            f'<span style="font-size:14px; padding:4px 12px; border-radius:20px; '
            f'background:{_COLOR_ACCENT}; color:#fff; font-weight:700; margin-left:12px;">'
            f'{tag}</span>' if tag else ""
        )
        desc_html = f'<div style="font-size:var(--list-desc-size); color:{_COLOR_SUB}; line-height:1.35; margin-top:6px;">{desc}</div>' if desc else ""
        rows_html += f"""\
<div style="
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 25px 28px;
    border-radius: 16px;
    background: {bg};
    border: {border};
    margin-bottom: 16px;
">
    <div>
        <div style="display: flex; align-items: center;">
            <span style="font-size: 34px; font-weight: 800; color: {name_color}; line-height: 1.16;">{name}</span>
            {tag_html}
        </div>
        {desc_html}
    </div>
    <div style="font-size: var(--grid-value-size); font-weight: 800; color: {_COLOR_ACCENT}; line-height: 1;">{value}</div>
</div>"""

    body_html = f'<div style="border-left: 4px solid {_COLOR_ACCENT}; padding-left: 20px; font-size: var(--body-size); line-height: 1.45; color: {_COLOR_TEXT}; margin-top: 14px; position: relative; z-index: 1;">{card.body}</div>' if card.body else ""

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1;">{rows_html}</div>
    {body_html}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_closing(card: CardData) -> str:
    """结尾卡片 — 品牌收尾风。

    设计语言：大引言居中，品牌签名，行动号召。
    视觉上给人"结束但期待下一期"的感觉。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    body_html = _orange_inline(card.body.replace("\n", "<br>")) if card.body else ""
    highlight = ""
    if card.highlight_text:
        highlight = f'<div class="card-highlight-box" style="max-width: 680px;">{card.highlight_text}</div>'

    return f"""\
    {card_num}
    <!-- 装饰：顶部渐变 -->
    <div style="
        position: absolute; top: 0; left: 0; right: 0;
        height: 6px;
        background: linear-gradient(90deg, {_COLOR_ACCENT}, {_COLOR_COVER_GRADIENT_START});
        border-radius: 24px 24px 0 0;
    "></div>
    <!-- 内容 -->
    <div style="
        position: relative; z-index: 1;
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px 0;
    ">
        <h2 class="card-title" style="max-width: 700px;">{card.title}</h2>
        <div style="
            width: 48px; height: 4px;
            background: {_COLOR_ACCENT};
            border-radius: 2px;
            margin: 24px 0;
        "></div>
        <div style="
            font-size: var(--body-size);
            line-height: 1.48;
            color: {_COLOR_SUB};
            max-width: 720px;
        ">{body_html}</div>
        {highlight}
    </div>
    <!-- 底部品牌 -->
    <div style="
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 16px;
        color: {_COLOR_LIGHT};
        position: relative;
        z-index: 1;
    ">
        <div style="
            width: 8px; height: 8px;
            border-radius: 50%;
            background: {_COLOR_WECHAT_GREEN};
        "></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_content_grid(card: CardData) -> str:
    """四宫格卡片 — 网格仪表盘风。

    2×2 网格展示 4 个并列要点，每格一个数据/标签/说明。
    items 格式: [{"label": "标题", "value": "数值/关键词", "desc": "说明"}]
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    grid_cells = ""
    for idx, item in enumerate(card.items[:4]):
        label = item.get("label", "")
        value = item.get("value", "")
        desc = item.get("desc", "")
        grid_cells += f"""\
<div style="
    background: {_COLOR_QUOTE_BG};
    border-radius: 20px;
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    text-align: center;
    min-height: 260px;
">
    <div style="font-size: 23px; color: {_COLOR_LIGHT}; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 12px;">{label}</div>
    <div class="card-grid-value">{value}</div>
    <div style="font-size: var(--list-desc-size); color: {_COLOR_SUB}; line-height: 1.36; margin-top: 12px;">{desc}</div>
</div>"""

    highlight = ""
    if card.highlight_text:
        highlight = f'<div class="card-highlight-box">{card.highlight_text}</div>'

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <div style="
        position: relative; z-index: 1; flex: 1;
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-template-rows: 1fr 1fr;
        gap: 16px;
    ">{grid_cells}</div>
    {highlight}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_content_hero(card: CardData) -> str:
    """大字报卡片 — 冲击力表达。

    超大数字或关键词居中聚焦，适合关键数据/判断的强调。
    data_value: 超大数字，data_label: 说明，body: 补充文字。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    hero_value = ""
    if card.data_value:
        hero_value = f"""\
<div class="card-hero-value">{card.data_value}</div>"""
    elif card.body:
        hero_value = f"""\
<div class="card-body" style="
    font-size: var(--body-size);
    font-weight: 800;
    line-height: 1.3;
    max-width: 680px;
    letter-spacing: -1px;
">{_orange_inline(card.body.replace(chr(10), '<br>'))}</div>"""

    label_html = f'<div style="font-size: var(--body-size); color: {_COLOR_SUB}; margin-top: 16px; line-height: 1.35;">{card.data_label}</div>' if card.data_label else ""
    subtitle_html = f'<div style="font-size: var(--body-size); color: {_COLOR_LIGHT}; margin-top: 24px; max-width: 680px; line-height: 1.42;">{card.subtitle}</div>' if card.subtitle else ""
    highlight = f'<div class="card-highlight-box" style="max-width: 600px; margin-top: 32px;">{card.highlight_text}</div>' if card.highlight_text else ""

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider" style="margin: 12px auto 24px;"></div>
    <div style="
        position: relative; z-index: 1;
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    ">
        {hero_value}
        {label_html}
        {subtitle_html}
        {highlight}
    </div>
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_content_steps(card: CardData) -> str:
    """步骤流卡片 — 竖向时间轴/流程。

    左侧竖线 + 编号圆点，右侧内容。适合流程、时间线。
    items 格式: [{"label": "步骤标题", "desc": "说明"}]
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    steps_html = ""
    total = min(len(card.items), 5)
    for idx, item in enumerate(card.items[:5], 1):
        label = item.get("label", "")
        desc = item.get("desc", "")
        is_last = idx == total
        connector = "" if is_last else f'<div style="width:3px; flex:1; background:linear-gradient(to bottom, {_COLOR_ACCENT}, {_COLOR_ACCENT_BG}); margin-top:8px;"></div>'
        steps_html += f"""\
<div style="display: flex; gap: 22px; align-items: stretch;">
    <div style="display: flex; flex-direction: column; align-items: center; width: 36px; flex-shrink: 0;">
        <div style="
            width: 44px; height: 44px;
            border-radius: 50%;
            background: {_COLOR_ACCENT};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(255,107,33,0.3);
        ">{idx}</div>
        {connector}
    </div>
    <div style="flex: 1; padding-bottom: {28 if not is_last else 0}px;">
        <div class="card-list-keyword">{label}</div>
        <div class="card-list-desc" style="margin-top: 8px;">{desc}</div>
    </div>
</div>"""

    highlight = f'<div class="card-highlight-box">{card.highlight_text}</div>' if card.highlight_text else ""

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider"></div>
    <div style="position: relative; z-index: 1; flex: 1;">{steps_html}</div>
    {highlight}
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


def _render_content_quote(card: CardData) -> str:
    """引言卡片 — 名言/观点聚焦。

    大引言居中，来源署名，适合关键判断、观点表达。
    body: 主引言，subtitle: 来源，highlight_text: 补充说明。
    """
    card_num = f'<div class="card-num">{card.page_num:02d}</div>' if card.page_num else ""
    quote_text = _orange_inline(card.body.replace("\n", "<br>")) if card.body else ""
    source_html = f'<div style="font-size: 25px; color: {_COLOR_LIGHT}; margin-top: 22px; font-style: italic;">— {card.subtitle}</div>' if card.subtitle else ""
    highlight = f'<div class="card-highlight-box" style="max-width: 600px;">{card.highlight_text}</div>' if card.highlight_text else ""

    return f"""\
    {card_num}
    <h2 class="card-title">{card.title}</h2>
    <div class="divider" style="margin: 12px auto 24px;"></div>
    <div style="
        position: relative; z-index: 1;
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    ">
        <div style="
            font-size: 84px;
            color: {_COLOR_ACCENT};
            line-height: 1;
            margin-bottom: -16px;
            font-family: Georgia, serif;
            opacity: 0.3;
        ">"</div>
        <div class="card-quote-body" style="max-width: 720px;">{quote_text}</div>
        {source_html}
        <div style="
            width: 48px; height: 3px;
            background: {_COLOR_ACCENT};
            border-radius: 2px;
            margin-top: 28px;
        "></div>
        {highlight}
    </div>
    <div class="footer">
        <div class="green-dot"></div>
        <span>{card.footer_note or "AI 开发者日报"}</span>
    </div>"""


_RENDERERS: dict[str, Any] = {
    "cover": _render_cover,
    "content": _render_content,
    "list": _render_list,
    "data": _render_data,
    "compare": _render_compare,
    "closing": _render_closing,
    "content-grid": _render_content_grid,
    "content-hero": _render_content_hero,
    "content-steps": _render_content_steps,
    "content-quote": _render_content_quote,
}


def render_html(card: CardData, account: str = "AI 开发者日报", total_cards: int = 1) -> str:
    """将单张 CardData 渲染为完整的 HTML 页面字符串。

    Args:
        card: CardData 实例
        account: 底部品牌署名
        total_cards: 这叠卡片的总数量（用于计算 tier: 1-2=tier1, 3-4=tier2, 5+=tier3）
    """
    font_scales = compute_font_scales(total_cards)
    scale_style = "; ".join(f"{k}: {v}" for k, v in font_scales.items())

    # Compute tier from total card count
    if total_cards <= 2:
        tier = "1"
    elif total_cards <= 4:
        tier = "2"
    else:
        tier = "3"

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
<div class="card" data-tier="{tier}" style="{scale_style}">
{body_html}
</div>
</body>
</html>"""


def render_image(card: CardData, output_path: str | Path, total_cards: int = 1) -> Path:
    """使用 Playwright 将 CardData 渲染为 PNG 截图。"""
    from playwright.sync_api import sync_playwright

    html = render_html(card, total_cards=total_cards)
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

    total = len(cards_data)
    results: list[Path] = []
    for idx, card_dict in enumerate(cards_data):
        card = _parse_card_data(card_dict)
        suffix = card.card_type
        page = card.page_num if card.page_num else idx
        filename = f"card_{idx:02d}_p{page}_{suffix}.png"
        out = render_image(card, output_dir / filename, total_cards=total)
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
