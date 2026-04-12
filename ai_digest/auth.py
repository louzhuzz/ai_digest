from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import parse, request

from .http_client import DEFAULT_TIMEOUT_SECONDS


@dataclass
class WeChatAccessTokenClient:
    appid: str
    appsecret: str
    http_client: object | None = None
    token_url: str = "https://api.weixin.qq.com/cgi-bin/token"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def get_access_token(self) -> str:
        query = parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.appsecret,
            }
        )
        url = f"{self.token_url}?{query}"
        opener = self.http_client or request.urlopen
        try:
            with opener(url, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"WeChat access token request failed: {exc}") from exc

        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"Failed to fetch access token: {payload}")
        return str(token)
