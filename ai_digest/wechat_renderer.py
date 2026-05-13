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
            "box-shadow": "0 2px 8px rgba(0,0,0,0.08)",
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
            "background": "#1e293b",
            "color": "#e2e8f0",
            "padding": "16px 20px",
            "border-radius": "8px",
            "overflow-x": "auto",
            "margin": "16px 0",
            "font-size": "13px",
            "line-height": "1.6",
        },
        "pre": {"margin": "0", "padding": "0", "background": "transparent"},
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
        extensions=["tables", "fenced_code", "nl2br"],
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
    """Convert external <a href> links to footnote superscripts."""
    links: list[tuple[str, str]] = []

    def _collect_links(m: re.Match) -> str:
        url = m.group(1)
        label = m.group(2)
        if _HTTP_RE.search(url):
            idx = len(links) + 1
            links.append((url, label))
            return f'{html.escape(label)}<sup style="font-size:12px;color:#3b82f6;vertical-align:super">[{idx}]</sup>'
        return m.group(0)

    processed = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', _collect_links, html_text)

    if not links:
        return processed

    footnote_items = ""
    for i, (url, label) in enumerate(links, 1):
        footnote_items += (
            f'<div style="line-height:1.8">'
            f'[{i}] <a href="{html.escape(url, quote=True)}" style="color:#3b82f6">'
            f"{html.escape(label)}</a></div>"
        )

    footnotes_html = (
        f'<hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb">'
        f'<div style="font-size:12px;color:#9ca3af;margin-top:8px">'
        f'<div style="font-weight:700;margin-bottom:4px">参考来源：</div>'
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


# ── F8: Regex-based Code Syntax Highlighting ──────────────────────────────────


_CODE_KW = (
    r"\b(import|from|def|class|return|if|else|elif|for|while|with|as|in|not|and|"
    r"or|is|None|True|False|try|except|finally|raise|async|await|lambda|yield|"
    r"global|nonlocal|pass|break|continue|assert|del|and|or|not|in|is)\b"
)


def _highlight_code(code: str, lang: str) -> str:
    """Apply regex-based syntax highlighting to code content."""
    # Keywords (blue, bold)
    code = re.sub(_CODE_KW, r'<span style="color:#3b82f6;font-weight:600">\1</span>', code)
    # Strings (orange) — handle triple-quoted and single/double quoted
    code = re.sub(
        r'(["\']{3})(.*?)(\1)',
        r'<span style="color:#f97316">\1\2\3</span>',
        code,
        flags=re.DOTALL,
    )
    code = re.sub(
        r'(["\'])(?:(?=(\\?))\2.)*?\1',
        r'<span style="color:#f97316">\0</span>',
        code,
    )
    # Comments (gray, italic)
    code = re.sub(
        r"(#.*)$",
        r'<span style="color:#9ca3af;font-style:italic">\1</span>',
        code,
        flags=re.MULTILINE,
    )
    # Numbers (green)
    code = re.sub(
        r"\b(\d+\.?\d*)\b",
        r'<span style="color:#22c55e">\1</span>',
        code,
    )
    return code


_CODE_BLOCK_RE = re.compile(
    r"<pre><code(?:\s+class=[^>]*)?>(.*?)</code></pre>",
    re.DOTALL | re.IGNORECASE,
)


def process_code_blocks(html_text: str) -> str:
    """Apply regex-based syntax highlighting inside <pre><code> blocks."""

    def _replace(m: re.Match) -> str:
        code_content = m.group(1)
        # Unescape HTML entities from markdown processing
        code_content = html.unescape(code_content)
        # Detect language from class attribute
        lang_match = re.search(
            r'class=["\']?[^"\']*language-([a-z0-9]+)[^"\']*["\']?',
            m.group(0),
            re.IGNORECASE,
        )
        lang = lang_match.group(1) if lang_match else ""
        highlighted = _highlight_code(code_content, lang)
        # Re-escape for HTML output
        highlighted = html.escape(highlighted)
        return f"<pre style=\"{build_style_string(THEME['styles']['pre'])}\"><code>{highlighted}</code></pre>"

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

        # F8: Inline style injection
        text = inject_inline_styles(text)

        # F9: Code syntax highlighting
        text = process_code_blocks(text)

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
