from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..http_client import decode_response, open_url
from ..models import DigestItem


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


class RSSCollector:
    def __init__(self, source_name: str, category: str = "news", http_client: object | None = None) -> None:
        self.source_name = source_name
        self.category = category
        self.http_client = http_client

    def collect(self, feed_url: str) -> list[DigestItem]:
        with open_url(feed_url, http_client=self.http_client) as response:
            xml = decode_response(response)
        return self.parse_feed(xml, feed_url=feed_url)

    def _find_link(self, node: ET.Element, feed_url: str) -> str:
        """Extract the article link, handling Atom and RSS 2.0 formats."""
        # RSS 2.0: <link> directly under item
        link = (node.findtext("link") or "").strip()
        if link and not link.startswith("http"):
            link = ""
        if link:
            return link
        # Atom: <link href="..." rel="alternate"/> under item
        for atom_link in node.findall("link"):
            rel = atom_link.get("rel", "alternate")
            href = atom_link.get("href", "")
            if rel == "alternate" and href.startswith("http"):
                return href
        return feed_url

    def _find_summary(self, node: ET.Element) -> str:
        """Extract best-effort summary: content:encoded > description > empty."""
        # Try content:encoded first (may contain full HTML, strip it)
        for child in node:
            tag = child.tag
            if tag.endswith("}content") or tag == "content:encoded" or tag == "encoded":
                raw = child.text or ""
                return _strip_html(raw)[:2000]
        # Fallback to description
        desc = (node.findtext("description") or "").strip()
        if desc:
            return _strip_html(desc)[:2000]
        return ""

    def parse_feed(self, xml: str, feed_url: str) -> list[DigestItem]:
        root = ET.fromstring(xml)
        items: list[DigestItem] = []
        for node in root.findall(".//item"):
            title = _strip_html(node.findtext("title") or "").strip()
            link = self._find_link(node, feed_url)
            summary = self._find_summary(node)
            pub_date = self._parse_pub_date(node.findtext("pubDate"))
            items.append(
                DigestItem(
                    title=title,
                    url=link or feed_url,
                    source=self.source_name,
                    published_at=pub_date,
                    category=self.category,
                    summary=summary,
                    dedupe_key=link or feed_url,
                )
            )
        return items

    @staticmethod
    def _parse_pub_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # Try RFC 2822 first
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass
        # Fallback: ISO-like format with space-separated tz, e.g. "2026-04-29 20:44:39 +0800"
        try:
            normalized = value.replace(" +", "+").replace(" -", "-")
            normalized = normalized.replace("T", " ")
            parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S%z")
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass
        # Give up
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
