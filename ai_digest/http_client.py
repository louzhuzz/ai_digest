from __future__ import annotations

import re
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


def decode_response(response) -> str:
    """Decode HTTP response body to string, auto-detecting charset.

    Checks, in order: Content-Type charset, XML declaration encoding,
    HTML <meta charset>, then falls back to utf-8.
    """
    raw = response.read()
    charset = None
    # 1) Try Content-Type header
    if hasattr(response, "headers"):
        ct = response.headers.get_content_charset()
        if ct:
            charset = ct
    # 2) Try <?xml encoding="..."?> declaration
    if not charset:
        head = raw[:512].decode("ascii", errors="replace")
        m = re.search(r'<\?xml\s+[^>]*encoding=["\']([\w.-]+)', head, re.I)
        if m:
            charset = m.group(1)
    # 3) Try HTML <meta charset=""> or <meta http-equiv="Content-Type">
    if not charset:
        head = raw[:8192].decode("ascii", errors="replace")
        m = re.search(r'<meta\s+charset=["\']?([\w-]+)', head, re.I)
        if m:
            charset = m.group(1)
        else:
            m = re.search(
                r'<meta\s+http-equiv=["\']Content-Type["\'][^>]+content=["\'][^;]+;\s*charset=([\w-]+)',
                head, re.I,
            )
            if m:
                charset = m.group(1)
    # 4) Fallback
    if not charset:
        charset = "utf-8"
    errors = "replace" if charset.lower() in ("utf-8", "utf8") else "strict"
    return raw.decode(charset, errors=errors)
