from __future__ import annotations

import unittest
from unittest.mock import Mock

from ai_digest.collectors.rss import RSSCollector


class HttpHeaderTest(unittest.TestCase):
    def test_rss_collector_sends_browser_user_agent(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"""<?xml version='1.0'?><rss><channel></channel></rss>"""

        opener = Mock(return_value=response)
        collector = RSSCollector(source_name="OpenAI News", http_client=opener)

        collector.collect("https://openai.com/news/rss.xml")

        request_obj = opener.call_args.args[0]
        self.assertIn("User-agent", request_obj.headers)
        self.assertTrue(request_obj.headers["User-agent"].startswith("Mozilla/5.0"))


if __name__ == "__main__":
    unittest.main()
