from __future__ import annotations

from urllib import request


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenClawDigest/1.0; +https://openai.com)",
    "Accept": "application/xml,text/xml,text/html,application/xhtml+xml",
}
DEFAULT_TIMEOUT_SECONDS = 15


def open_url(url: str, http_client: object | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    req = request.Request(url, headers=DEFAULT_HEADERS)
    opener = http_client or request.urlopen
    return opener(req, timeout=timeout)
