from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from ai_digest.auth import WeChatAccessTokenClient


class WeChatAccessTokenClientTest(unittest.TestCase):
    def test_fetches_access_token_from_official_endpoint(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({"access_token": "token-123"}).encode("utf-8")

        opener = Mock(return_value=response)
        client = WeChatAccessTokenClient(
            appid="wx-appid",
            appsecret="wx-secret",
            http_client=opener,
        )

        token = client.get_access_token()

        self.assertEqual(token, "token-123")
        called_url = opener.call_args.args[0]
        self.assertIn("https://api.weixin.qq.com/cgi-bin/token", called_url)
        self.assertIn("appid=wx-appid", called_url)
        self.assertIn("secret=wx-secret", called_url)
        self.assertIn("grant_type=client_credential", called_url)

    def test_wraps_timeout_with_context(self) -> None:
        opener = Mock(side_effect=TimeoutError("The read operation timed out"))
        client = WeChatAccessTokenClient(
            appid="wx-appid",
            appsecret="wx-secret",
            http_client=opener,
        )

        with self.assertRaisesRegex(RuntimeError, "WeChat access token request failed"):
            client.get_access_token()


if __name__ == "__main__":
    unittest.main()
