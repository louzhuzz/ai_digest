from __future__ import annotations

import unittest
from unittest.mock import Mock

from ai_digest.http_client import open_url


class TimeoutTest(unittest.TestCase):
    def test_open_url_uses_default_timeout(self) -> None:
        opener = Mock()

        open_url("https://example.com/feed.xml", http_client=opener)

        self.assertEqual(opener.call_args.kwargs["timeout"], 15)


if __name__ == "__main__":
    unittest.main()
