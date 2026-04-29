from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..http_client import decode_response, open_url
from ..models import DigestItem


class RSSCollector:
    def __init__(self, source_name: str, category: str = "news", http_client: object | None = None) -> None:
        self.source_name = source_name
        self.category = category
        self.http_client = http_client

    def collect(self, feed_url: str) -> list[DigestItem]:
        with open_url(feed_url, http_client=self.http_client) as response:
            xml = decode_response(response)
        return self.parse_feed(xml, feed_url=feed_url)

    def parse_feed(self, xml: str, feed_url: str) -> list[DigestItem]:
        root = ET.fromstring(xml)
        items: list[DigestItem] = []
        for node in root.findall(".//item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = self._parse_pub_date(node.findtext("pubDate"))
            items.append(
                DigestItem(
                    title=title,
                    url=link or feed_url,
                    source=self.source_name,
                    published_at=pub_date,
                    category=self.category,
                    summary=description,
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
