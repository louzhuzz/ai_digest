# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
import markdown

# ── Theme ────────────────────────────────────────────────────────────────────────

THEME = {
    "colors": {
        "primary": "#111111",
        "accent": "#3b82f6",
        "background": "#ffffff",
        "blockquote_bg": "#f8fafc",
        "blockquote_border": "#3b82f6",
        "code_bg": "#f1f5f9",
        "code_color": "#1e293b",
        "hr_color": "#e5e7eb",
        "footnote_bg": "#f9fafb",
    },
    "styles": {
        "wrapper": {
            "font-family": "'PingFang SC', 'Helvetica Neue', Arial, sans-serif",
            "font-size": "16px",
            "line-height": "1.8",
            "color": "#333333",
            "max-width": "100%",
        },
        "h1": {
            "font-size": "22px",
            "font-weight": "700",
            "color": "#111111",
            "line-height": "1.4",
            "margin-top": "28px",
            "margin-bottom": "14px",
            "border-bottom": "3px solid #2563eb",
            "padding-bottom": "10px",
        },
        "h2": {
            "font-size": "18px",
            "font-weight": "700",
            "color": "#ffffff",
            "background": "#2563eb",
            "display": "inline-block",
            "padding": "6px 16px 4px",
            "border-radius": "4px",
            "line-height": "1.5",
            "margin-top": "24px",
            "margin-bottom": "14px",
        },
        "h3": {
            "font-size": "16px",
            "font-weight": "700",
            "color": "#1e293b",
            "border-left": "4px solid #2563eb",
            "padding-left": "12px",
            "line-height": "1.5",
            "margin-top": "20px",
            "margin-bottom": "10px",
        },
        "p": {
            "font-size": "15px",
            "color": "#374151",
            "line-height": "1.8",
            "margin-top": "0",
            "margin-bottom": "12px",
        },
        "strong": {"font-weight": "700", "color": "#111111"},
        "em": {"font-style": "italic"},
        "a": {
            "color": "#2563eb",
            "text-decoration": "none",
            "border-bottom": "1px solid #93c5fd",
        },
        "img": {
            "max-width": "90%",
            "height": "auto",
            "display": "block",
            "margin": "16px auto",
            "border-radius": "6px",
            "border": "1px solid #e5e7eb",
        },
        "blockquote": {
            "border-left": "4px solid #2563eb",
            "background": "#f0f4ff",
            "margin": "16px 0",
            "padding": "14px 18px",
            "border-radius": "0 8px 8px 0",
        },
        "blockquote_p": {
            "font-size": "15px",
            "color": "#475569",
            "line-height": "1.7",
            "margin": "0",
            "font-style": "italic",
        },
        "code": {
            "background": "#f0f4ff",
            "color": "#2563eb",
            "padding": "1px 6px",
            "border-radius": "4px",
            "font-size": "13px",
            "font-family": "'SF Mono', Consolas, 'Courier New', monospace",
        },
        "code_block": {
            "background": "#f8fafc",
            "color": "#1e293b",
            "padding": "4px 20px 16px",
            "border-radius": "8px",
            "overflow-x": "auto",
            "margin": "16px 0",
            "font-size": "14px",
            "line-height": "1.7",
        },
        "pre": {"margin": "16px 0", "padding": "0", "background": "#f8fafc", "border-radius": "8px", "overflow-x": "auto", "font-size": "14px", "font-family": "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace", "line-height": "1.7"},
        "table": {
            "width": "100%",
            "border-collapse": "collapse",
            "margin": "16px 0",
            "font-size": "14px",
            "overflow-x": "auto",
            "display": "block",
        },
        "th": {
            "background": "#2563eb",
            "padding": "10px 14px",
            "text-align": "left",
            "font-weight": "600",
            "color": "#ffffff",
            "font-size": "14px",
            "border": "none",
        },
        "td": {
            "padding": "10px 14px",
            "color": "#374151",
            "font-size": "14px",
            "border-bottom": "1px solid #e5e7eb",
        },
        "hr": {"margin": "24px 0", "border": "none", "border-top": "1px solid #e5e7eb"},
        "ol": {"padding-left": "24px", "margin": "12px 0"},
        "ul": {"padding-left": "24px", "margin": "12px 0"},
        "li": {"margin-bottom": "2px", "line-height": "1.7", "color": "#374151"},
        "sup": {"font-size": "12px", "color": "#3b82f6", "vertical-align": "super"},
        "footnote_ref": {
            "font-size": "12px",
            "color": "#3b82f6",
            "vertical-align": "super",
        },
    },
}

# ── Callout colour map ───────────────────────────────────────────────────────

CALLOUT_COLORS = {
    "tip": ("#10b981", "#f0fdf4", "#166534"),
    "note": ("#3b82f6", "#eff6ff", "#1e40af"),
    "important": ("#8b5cf6", "#f5f3ff", "#5b21b6"),
    "warning": ("#f59e0b", "#fffbeb", "#92400e"),
    "caution": ("#ef4444", "#fef2f2", "#991b1b"),
    "callout": ("#6b7280", "#f9fafb", "#374151"),
}

# ── Protected-region placeholders ───────────────────────────────────────────

_PROTECT_RE = re.compile(
    r"(?P<open>(?:```|``?|~~?).*?\n)|"
    r"(?P<img>\!\[.*?\]\(.*?\))|"
    r"(?P<url><https?://[^>]+>)|"
    r"(?P<link>\[[^\]]+\]\([^)]+\))",
    re.DOTALL | re.IGNORECASE,
)


def _protectRegions(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace code blocks / images / URLs / links with null-byte placeholders."""
    protections: list[tuple[str, str]] = []

    def replacer(m: re.Match) -> str:
        full = m.group(0)
        pid = f"\x00P{len(protections)}\x00"
        protections.append((pid, full))
        return pid

    protected = _PROTECT_RE.sub(replacer, text)
    return protected, protections


def _restoreRegions(text: str, protections: list[tuple[str, str]]) -> str:
    """Restore previously protected regions."""
    for pid, original in protections:
        text = text.replace(pid, original)
    return text


# ── F1: CJK English Spacing ───────────────────────────────────────────────────


def fix_cjk_spacing(text: str) -> str:
    """Add space between CJK and Latin characters."""
    protected, protections = _protectRegions(text)

    def _add_space(s: str) -> str:
        s = re.sub(r"([\u4e00-\u9fff])([a-zA-Z])", r"\1 \2", s)
        s = re.sub(r"([a-zA-Z])([\u4e00-\u9fff])", r"\1 \2", s)
        return s

    result = _add_space(protected)
    return _restoreRegions(result, protections)


# ── F2: Bold Punctuation Fix ─────────────────────────────────────────────────


_CJK_PUNCT = "，。！？；：""''（）【】《》"


def fix_cjk_bold_punctuation(text: str) -> str:
    """Move Chinese punctuation outside ** / * bold markers."""
    for punct in _CJK_PUNCT:
        escaped = "\\" + punct if punct in r"\^$.*+?{}[]()|\-#" else punct
        # **text，** → **text**，
        text = re.sub(
            rf"\*\*(.+?)({re.escape(punct)})\*\*",
            rf"**\1**\2",
            text,
        )
        # *text，* → *text*，(for single-asterisk italic)
        text = re.sub(
            rf"(?<!\*)\*(?!\*)(.+?)({re.escape(punct)})(?<!\*)\*(?!\*)",
            rf"*\1*\2",
            text,
        )
    return text


# ── F3: Callout Blocks ────────────────────────────────────────────────────────


_BLOCKQUOTE_CALLouts = re.compile(
    r"^> \[!(tip|note|important|warning|caution|callout)\]\s*(.*?)\n"
    r"((?:>.*?\n)*)",
    re.MULTILINE,
)


def process_callouts(text: str) -> str:
    """Convert [!callout] blockquotes to styled divs."""

    def _replace(m: re.Match) -> str:
        kind = m.group(1)
        title = m.group(2).strip()
        body_lines = m.group(3).rstrip("\n")
        accent, bg, text_color = CALLOUT_COLORS.get(kind, CALLOUT_COLORS["callout"])

        icon_map = {
            "tip": "💡",
            "note": "📝",
            "important": "⭐",
            "warning": "⚠️",
            "caution": "🚨",
            "callout": "ℹ️",
        }
        icon = icon_map.get(kind, "ℹ️")

        body = re.sub(r"^>\s*", "", body_lines)
        body = re.sub(r"\n", "<br>", body)

        if title:
            title_html = f'<div style="font-weight:700;color:{accent};margin-bottom:6px">{icon} {html.escape(title)}</div>'
        else:
            title_html = f'<div style="font-weight:700;color:{accent};margin-bottom:6px">{icon}</div>'

        return (
            f'<div style="border-left:4px solid {accent};'
            f"background:{bg};padding:12px 16px;margin:16px 0;"
            f'border-radius:0 8px 8px 0">'
            f"{title_html}"
            f'<div style="color:{text_color}">{body}</div>'
            f"</div>"
        )

    return _BLOCKQUOTE_CALLouts.sub(_replace, text)


# ── F4: Fenced Containers ────────────────────────────────────────────────────


_FENCED_CONTAINERS = re.compile(
    r"^:::(dialogue|compare|quote|stat)(\[.*?\])?\n(.*?)^:::", re.MULTILINE | re.DOTALL
)


def process_fenced_containers(text: str) -> str:
    """Convert :::container_type[title] blocks to styled HTML."""

    def _replace(m: re.Match) -> str:
        ctype = m.group(1)
        title = m.group(2)
        body = m.group(3).rstrip()

        if title:
            title_text = title.group(1) if title else ""
            title_html = (
                f'<div style="font-weight:700;font-size:14px;'
                f"color:#374151;margin-bottom:10px;border-bottom:1px solid #e5e7eb;"
                f'padding-bottom:6px">{html.escape(title_text)}</div>'
            )
        else:
            title_html = ""

        if ctype == "dialogue":
            return _render_dialogue(body, title_html)
        elif ctype == "compare":
            return _render_compare(body, title_html)
        elif ctype == "quote":
            return _render_quote(body, title_html)
        elif ctype == "stat":
            return _render_stat(body, title_html)
        return body

    return _FENCED_CONTAINERS.sub(_replace, text)


def _render_dialogue(body: str, title_html: str) -> str:
    accent = "#3b82f6"
    lines = body.splitlines()
    bubbles: list[str] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if ":" in line:
            speaker, content = line.split(":", 1)
            content = content.strip()
            alignment = "right" if i % 2 == 1 else "left"
            bg = "#dbeafe" if alignment == "right" else "#f0fdf4"
            side = "right" if alignment == "right" else "left"
            text_align = "right" if alignment == "right" else "left"
            bubble = (
                f'<div style="text-align:{text_align};margin-bottom:10px">'
                f'<span style="display:inline-block;'
                f"background:{bg};padding:8px 14px;border-radius:12px;"
                f'max-width:80%;color:#1e293b;font-size:14px;line-height:1.6">'
                f"<strong style='display:block;font-size:12px;color:#6b7280;"
                f"margin-bottom:2px'>{html.escape(speaker.strip())}</strong>"
                f"{html.escape(content)}"
                f"</span></div>"
            )
            bubbles.append(bubble)
    inner = "".join(bubbles)
    return (
        f'<section data-container="dialogue" style="margin:16px 0">'
        f"{title_html}"
        f"{inner}</section>"
    )


def _render_compare(body: str, title_html: str) -> str:
    lines = [l for l in body.splitlines() if l.strip() and "|" in l]
    cards: list[str] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 2:
            left = parts[0].strip()
            right = parts[1].strip()
            card = (
                f'<div style="flex:1;min-width:0;padding:12px 16px;'
                f"background:#f8fafc;border-radius:8px;border:1px solid #e5e7eb\">"
                f'<div style="font-size:12px;color:#6b7280;margin-bottom:4px">'
                f"{html.escape(left)}</div>"
                f'<div style="font-size:14px;color:#1e293b;line-height:1.6">'
                f"{html.escape(right)}</div></div>"
            )
            cards.append(card)
    if not cards:
        return f'<section data-container="compare">{title_html}{body}</section>'
    return (
        f'<section data-container="compare" style="margin:16px 0">'
        f'{title_html}<div style="display:flex;gap:12px;flex-wrap:wrap">'
        f"{"".join(cards)}</div></section>"
    )


def _render_quote(body: str, title_html: str) -> str:
    lines = body.splitlines()
    quote_text = " ".join(html.escape(l.strip()) for l in lines if l.strip())
    return (
        f'<section data-container="quote" style="margin:16px 0">'
        f"{title_html}"
        f'<div style="border-left:4px solid #3b82f6;'
        f"padding:12px 20px;background:#f8fafc;border-radius:0 8px 8px 0\">"
        f'<div style="font-size:16px;color:#374151;line-height:1.8;font-style:italic">'
        f'&#8220;{quote_text}&#8221;</div></div></section>'
    )


def _render_stat(body: str, title_html: str) -> str:
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    number = lines[0] if lines else "0"
    label = lines[1] if len(lines) > 1 else ""
    return (
        f'<section data-container="stat" style="margin:16px 0;text-align:center">'
        f"{title_html}"
        f'<div style="font-size:48px;font-weight:700;color:#3b82f6;'
        f"line-height:1.2;letter-spacing:-2px\">{html.escape(number)}</div>"
        f'<div style="font-size:13px;color:#6b7280;margin-top:4px">{html.escape(label)}</div>'
        f"</section>"
    )


# ── F5: Markdown to HTML ──────────────────────────────────────────────────────


def md_to_html(text: str) -> str:
    """Convert Markdown to HTML using the markdown package."""
    try:
        import markdown
    except ImportError:
        raise ImportError(
            "markdown package is required for md_to_html(). "
            "Install via: pip install markdown"
        )
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code"],
    )


# ── F6: Flatten ordered/unordered lists to plain paragraphs ───────────────────
# WeChat 草稿箱编辑器在打开 HTML 草稿时，会自动将 <ol>/<ul> 识别为列表块。
# 如果列表项之间有空白段落，编辑器会打断自动编号（1. (空) 2. (内容) 3. (空) 4. (内容)）。
# 将列表全部拍平为带手动标号的段落 <p>，彻底规避此问题。


def _flatten_ordered_list(match: re.Match) -> str:
    """将 <ol> 替换为手动编号的段落。"""
    items = re.findall(r"<li>(.*?)</li>", match.group(0), re.DOTALL)
    result_parts: list[str] = []
    for idx, item_content in enumerate(items, 1):
        # 去除 li 内部可能由 nl2br 引入的 <p> 标签
        item_content = re.sub(r"</?p[^>]*>", "", item_content)
        item_content = item_content.strip()
        result_parts.append(
            f'<p><strong style="font-weight:700;color:#111">{idx}.</strong> '
            f"{item_content}</p>"
        )
    return "\n".join(result_parts)


def _flatten_unordered_list(match: re.Match) -> str:
    """将 <ul> 替换为 bullet 段落。"""
    items = re.findall(r"<li>(.*?)</li>", match.group(0), re.DOTALL)
    result_parts: list[str] = []
    for item_content in items:
        item_content = re.sub(r"</?p[^>]*>", "", item_content)
        item_content = item_content.strip()
        result_parts.append(
            f'<p><strong style="font-weight:700;color:#111;margin-right:6px">'
            f"\u2022</strong> {item_content}</p>"
        )
    return "\n".join(result_parts)


_OL_RE = re.compile(r"<ol[^>]*>(.*?)</ol>", re.DOTALL | re.IGNORECASE)
_UL_RE = re.compile(r"<ul[^>]*>(.*?)</ul>", re.DOTALL | re.IGNORECASE)


def flatten_lists(html_text: str) -> str:
    """Convert all <ol> and <ul> lists to plain paragraphs to avoid WeChat auto-numbering."""
    html_text = _OL_RE.sub(_flatten_ordered_list, html_text)
    html_text = _UL_RE.sub(_flatten_unordered_list, html_text)
    return html_text


# ── F7: External Links → Footnotes ───────────────────────────────────────────


_HTTP_RE = re.compile(r"https?://", re.IGNORECASE)


def extract_links_as_footnotes(html_text: str) -> str:
    """Convert external <a href> links to footnote superscripts.
    微信发布后外链不可点击，转为 [n] 上标索引并附文末来源列表。"""

    # 对同一 URL 去重
    links: list[tuple[str, str]] = []       # (url, label)
    link_index: dict[str, int] = {}          # url → index

    def _collect_links(m: re.Match) -> str:
        url = m.group(1)
        label = m.group(2)
        if _HTTP_RE.search(url):
            # 去重
            if url in link_index:
                idx = link_index[url]
            else:
                idx = len(links) + 1
                link_index[url] = idx
                links.append((url, label))
            return (
                f'{html.escape(label)}'
                f'<sup style="font-size:12px;color:#3b82f6;vertical-align:super">'
                f"[{idx}]</sup>"
            )
        return m.group(0)

    processed = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', _collect_links, html_text)

    if not links:
        return processed

    footnote_items = ""
    for i, (url, label) in enumerate(links, 1):
        footnote_items += (
            f'<div style="line-height:1.8;font-size:13px;color:#6b7280">'
            f'<span style="color:#3b82f6;font-weight:600">[{i}]</span> '
            f'{html.escape(label)}: '
            f'<span style="color:#9ca3af;word-break:break-all">{html.escape(url)}</span>'
            f"</div>"
        )

    footnotes_html = (
        f'<hr style="margin:24px 0;border:none;border-top:2px solid #2563eb">'
        f'<div style="font-size:13px;color:#6b7280;margin-top:8px">'
        f'<div style="font-weight:700;color:#374151;margin-bottom:8px">📎 参考来源</div>'
        f"{footnote_items}</div>"
    )
    return processed + footnotes_html


# ── Helper: build_style_string ────────────────────────────────────────────────


def build_style_string(props: dict) -> str:
    """Convert a style dict to an inline style string."""
    parts: list[str] = []
    for key, value in props.items():
        css_key = key.replace("_", "-")
        parts.append(f"{css_key}:{value}")
    return ";".join(parts)


# ── F7: Inline Style Injection ────────────────────────────────────────────────


_TAG_STYLE_MAP = {
    "h1": "h1",
    "h2": "h2",
    "h3": "h3",
    "h4": "h4",
    "h5": "h5",
    "h6": "h6",
    "p": "p",
    "strong": "strong",
    "em": "em",
    "a": "a",
    "img": "img",
    "blockquote": "blockquote",
    "code": "code",
    "pre": "pre",
    "table": "table",
    "thead": "table",
    "tbody": "table",
    "tr": "table",
    "th": "th",
    "td": "td",
    "hr": "hr",
    "ol": "ol",
    "ul": "ul",
    "li": "li",
    "sup": "sup",
    "div": "div",
    "section": "section",
    "span": "span",
}


def inject_inline_styles(html_text: str) -> str:
    """Apply hardcoded theme styles as inline style="" attributes."""
    styles = THEME["styles"]

    def _apply(m: re.Match) -> str:
        tag = m.group(1).lower()
        rest = m.group(2)
        inner = m.group(3)

        style_key = _TAG_STYLE_MAP.get(tag)
        existing_style = ""
        existing_match_for_replace: re.Match | None = None
        if rest:
            style_match = re.search(r'style="([^"]*)"', rest)
            if style_match:
                existing_style = style_match.group(1)
                existing_match_for_replace = style_match

        additional: str = ""
        if style_key and style_key in styles:
            theme_style = build_style_string(styles[style_key])
            additional = theme_style
        elif tag == "blockquote":
            additional = build_style_string(styles["blockquote"])

        if existing_match_for_replace is not None:
            merged_style = existing_style.rstrip(";") + ";" + additional
            new_rest = rest.replace(existing_match_for_replace.group(0), f'style="{merged_style}"')
        elif additional:
            new_rest = rest + f' style="{additional}"'
        else:
            new_rest = rest

        return f"<{tag}{new_rest}>{inner}</{tag}>"

    # Process void elements and block elements
    html_text = re.sub(
        r"<(\w+)([^>]*?)>(.*?)</\1>",
        _apply,
        html_text,
        flags=re.DOTALL,
    )

    # Handle self-closing void elements (img, br, hr)
    def _apply_void(m: re.Match) -> str:
        tag = m.group(1).lower()
        attrs = m.group(2)
        style_key = _TAG_STYLE_MAP.get(tag)
        existing_match = re.search(r'style="([^"]*)"', attrs)
        existing_style = existing_match.group(1) if existing_match else ""

        additional = ""
        if style_key and style_key in styles:
            additional = build_style_string(styles[style_key])

        if existing_style and additional:
            merged = existing_style.rstrip(";") + ";" + additional
            new_attrs = re.sub(r'style="[^"]*"', f'style="{merged}"', attrs)
            if not new_attrs:
                new_attrs = attrs + f' style="{merged}"'
        elif additional:
            new_attrs = attrs + f' style="{additional}"'
        else:
            new_attrs = attrs

        return f"<{tag}{new_attrs}>"

    html_text = re.sub(
        r"<(\w+)([^>]*?)/>",
        _apply_void,
        html_text,
    )

    return html_text


# ── F8: Pygments Code Syntax Highlighting ──────────────────────────────────────
# 使用 pygments 替代手写 regex 高亮，避免嵌套 span / 空字节 / 注释误伤等 bug


_PYGMENTS_LANG_MAP: dict[str, str] = {
    # Python
    "python": "python3",
    "py": "python3",
    "python3": "python3",
    # JavaScript/TypeScript
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "jsx": "jsx",
    "tsx": "tsx",
    "json": "json",
    "jsonc": "json",  # JSONC is close enough to JSON
    # Web
    "html": "html",
    "css": "css",
    "xml": "xml",
    "svg": "xml",
    # Shell
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "powershell": "ps1",
    "ps1": "ps1",
    # C family
    "c": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    "cs": "csharp",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "rs": "rust",
    "swift": "swift",
    "kotlin": "kotlin",
    "kt": "kotlin",
    # Data
    "sql": "sql",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "ini": "ini",
    "dockerfile": "docker",
    "makefile": "makefile",
    # Diff
    "diff": "diff",
    "patch": "diff",
}


def _highlight_code(code: str, lang: str) -> str:
    """使用 pygments 语法高亮，返回带内联样式的 HTML。"""
    if not lang:
        return html.escape(code)
    from pygments import highlight as pyg_highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter

    lexer_name = _PYGMENTS_LANG_MAP.get(lang.lower(), lang.lower())
    try:
        lexer = get_lexer_by_name(lexer_name, stripnl=False, stripall=False)
    except Exception:
        # 找不到对应 lexer，当作纯文本
        return html.escape(code)

    formatter = HtmlFormatter(noclasses=True, style="friendly", nowrap=True)
    try:
        highlighted = pyg_highlight(code, lexer, formatter)
    except Exception:
        return html.escape(code)
    # pygments 在 noclasses=True 时会自动转义文本内容，
    # but 偶尔会输出多余换行，trim 一下
    return highlighted.strip("\n")


_CODE_BLOCK_RE = re.compile(
    r"<pre[^>]*><code(?:\s+class=[^>]*)?>(.*?)</code></pre>",
    re.DOTALL | re.IGNORECASE,
)


def process_code_blocks(html_text: str) -> str:
    """Apply pygments syntax highlighting, then hardcode whitespace for WeChat.
    微信不尊重 <pre> 的 white-space，必须用 <br>+&nbsp; 硬编码格式。"""

    # macOS 三色圆点 SVG
    _MAC_DOTS = (
        '<span style="display:block;padding:12px 16px 4px">'
        '<svg width="52" height="12" viewBox="0 0 52 12" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="6" cy="6" r="6" fill="#FF5F56"/>'
        '<circle cx="26" cy="6" r="6" fill="#FFBD2E"/>'
        '<circle cx="46" cy="6" r="6" fill="#27C93F"/>'
        "</svg></span>"
    )

    def _code_whitespace(highlighted: str) -> str:
        """将换行符替换为 <br>，文本内空格替换为 Unicode NBSP（\xa0）。
        微信编辑器会剥离 <span> 标签和 &nbsp; 实体，但 Unicode NBSP
        作为纯文本字符可穿透 ProseMirror 转换保留缩进。"""
        # 1. 换行 → <br>
        highlighted = highlighted.replace("\n", "<br>")
        # 2. 用正则分割 HTML 标签和文本段，仅文本段内的空格转为 \xa0
        parts = re.split(r"(<[^>]+>)", highlighted)
        for i, part in enumerate(parts):
            if not part.startswith("<"):
                # 使用 Unicode NBSP（\xa0）而非 HTML 实体 &nbsp;
                parts[i] = part.replace(" ", "\xa0")
        return "".join(parts)

    def _replace(m: re.Match) -> str:
        raw_html = m.group(1)
        plain_text = html.unescape(raw_html)
        lang_match = re.search(
            r'class=["\']?[^"\']*language-([a-z0-9]+)[^"\']*["\']?',
            m.group(0),
            re.IGNORECASE,
        )
        lang = lang_match.group(1) if lang_match else ""
        highlighted = _highlight_code(plain_text, lang)
        # 微信硬编码空白（br + &nbsp;）
        highlighted = _code_whitespace(highlighted)
        # 移除末尾可能多余的 <br>
        if highlighted.endswith("<br>"):
            highlighted = highlighted[: -len("<br>")]
        # 使用 <span> 包裹高亮内容（避开 inject_inline_styles 对 <code>
        # 的行内样式注入），加 white-space:pre-wrap 兜底让微信保留空格
        return f"<pre>{_MAC_DOTS}<span style=\"display:block;padding:0 20px 16px;white-space:pre-wrap\">{highlighted}</span></pre>"

    return _CODE_BLOCK_RE.sub(_replace, html_text)


# ── F9: Table Wrapper ─────────────────────────────────────────────────────────


_TABLE_RE = re.compile(r"(<table[^>]*>)(.*?)(</table>)", re.DOTALL | re.IGNORECASE)


def _wrap_tables(html_text: str) -> str:
    """Wrap tables in a scrollable section."""
    wrapper_start = (
        '<section style="overflow-x:auto;max-width:100%;margin:16px 0">'
    )

    def _replace(m: re.Match) -> str:
        return wrapper_start + m.group(1) + m.group(2) + m.group(3) + "</section>"

    return _TABLE_RE.sub(_replace, html_text)


# ── F10: Multi-level Blockquote Styling ──────────────────────────────────────


_BLOCKQUOTE_NESTED_RE = re.compile(
    r"<blockquote>(.*?)</blockquote>",
    re.DOTALL | re.IGNORECASE,
)


def _style_blockquotes(html_text: str) -> str:
    """Apply multi-level border colours to nested blockquotes."""

    def _replace(m: re.Match) -> str:
        inner = m.group(1)
        # Detect nesting level by counting ancestor blockquotes
        level_match = re.search(
            r'<blockquote[^>]*>(?:(?!</blockquote>).)*?<blockquote',
            inner,
            re.DOTALL,
        )
        if level_match:
            # Nested
            border_color = "#8b5cf6"
            bg_color = "#f5f3ff"
        elif re.search(r"<blockquote[^>]*>.*?<blockquote", inner, re.DOTALL):
            border_color = "#10b981"
            bg_color = "#f0fdf4"
        else:
            border_color = "#2563eb"
            bg_color = "#f0f4ff"

        blockquote_style = (
            f"border-left:4px solid {border_color};"
            f"background:{bg_color};margin:16px 0;"
            f"padding:14px 18px;border-radius:0 8px 8px 0"
        )
        return f'<blockquote style="{blockquote_style}">{inner}</blockquote>'

    return _BLOCKQUOTE_NESTED_RE.sub(_replace, html_text)


# ── Main render pipeline ──────────────────────────────────────────────────────


def render(markdown_text: str) -> str:
    """
    Render Markdown to WeChat-compatible inline-style HTML.
    All CSS as inline style="" attributes. WeChat-friendly.
    """
    if not markdown_text or not markdown_text.strip():
        return ""

    try:
        text = markdown_text
        # Strip BOM if present (PowerShell Set-Content with UTF8 encoding adds BOM)
        if text.startswith('\ufeff'):
            text = text[1:]

        # F1: CJK English spacing
        text = fix_cjk_spacing(text)

        # F2: Bold punctuation fix
        text = fix_cjk_bold_punctuation(text)

        # F3: Callout blocks
        text = process_callouts(text)

        # F4: Fenced containers
        text = process_fenced_containers(text)

        # F5: Markdown → HTML
        text = md_to_html(text)

        # F6: Flatten lists to plain paragraphs（规避微信编辑器自动编号打断）
        text = flatten_lists(text)

        # F7: External links → footnotes
        text = extract_links_as_footnotes(text)

        # F8: Code syntax highlighting（先于 inject_inline_styles 执行，
        #     确保能匹配到 <pre><code> 尚未被注入 style 属性的原始状态）
        text = process_code_blocks(text)

        # F9: Inline style injection
        text = inject_inline_styles(text)

        # F10: Table wrapper
        text = _wrap_tables(text)

        # F11: Multi-level blockquote styling
        text = _style_blockquotes(text)

        return text

    except Exception:
        # Regex errors or unexpected failures — return original
        return markdown_text


def render_html(markdown_text: str) -> str:
    """Alias for render()."""
    return render(markdown_text)
