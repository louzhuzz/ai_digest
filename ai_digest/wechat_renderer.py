# ai_digest/wechat_renderer.py
from __future__ import annotations

import html
import re

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
ORDERED_LIST_PATTERN = re.compile(r"\d+\.\s+(.*)")

PARAGRAPH_STYLE = 'font-size:16px; line-height:1.8; color:#333; margin:1em 0;'
H1_STYLE = 'font-size:20px; font-weight:bold; color:#1a1a1a; margin:1.2em 0 0.6em;'
H2_STYLE = 'margin:1.4em 0 0.55em; font-size:22px; font-weight:700; line-height:1.45; color:#1f2937;'
H3_STYLE = 'margin:1em 0 0.45em; font-size:18px; font-weight:700; line-height:1.5; color:#334155;'
LINK_STYLE = 'color:#1a73e8; text-decoration:underline;'


def _render_inline(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in LINK_PATTERN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        label, url = match.groups()
        parts.append(f'<a href="{html.escape(url, quote=True)}" style="{LINK_STYLE}">{html.escape(label)}</a>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    rendered = "".join(parts)
    return BOLD_PATTERN.sub(lambda match: f"<strong>{html.escape(match.group(1))}</strong>", rendered)


def render_wechat_html(markdown: str) -> str:
    parts: list[str] = []
    in_unordered_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            continue

        if line.startswith("# "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[2:].strip())
            parts.append(f"<p style=\"{H1_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("## "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[3:].strip())
            parts.append(f"<p style=\"{H2_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("### "):
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            content = _render_inline(line[4:].strip())
            parts.append(f"<p style=\"{H3_STYLE}\"><strong>{content}</strong></p>")
            continue

        if line.startswith("- "):
            if not in_unordered_list:
                parts.append("<ul style=\"margin:1em 0; padding-left:1.5em;\">")
                in_unordered_list = True
            parts.append(f"<li style=\"margin-bottom:0.3em;\">{_render_inline(line[2:].strip())}</li>")
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(line.strip())
        if ordered_match:
            if in_unordered_list:
                parts.append("</ul>")
                in_unordered_list = False
            parts.append(f"<p style=\"{PARAGRAPH_STYLE}\">{_render_inline(line.strip())}</p>")
            continue

        if in_unordered_list:
            parts.append("</ul>")
            in_unordered_list = False
        parts.append(f"<p style=\"{PARAGRAPH_STYLE}\">{_render_inline(line)}</p>")

    if in_unordered_list:
        parts.append("</ul>")

    return "".join(parts)