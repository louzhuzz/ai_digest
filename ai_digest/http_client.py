from __future__ import annotations

import logging
import re
import time
from urllib import request, error


logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,text/html,application/xhtml+xml",
}

# ── 超时配置 ──────────────────────────────────────────────────────────────
CONNECT_TIMEOUT = 5       # TCP 连接建立超时（秒）
READ_TIMEOUT = 15         # 读取响应体超时（秒）

# ── 重试配置 ──────────────────────────────────────────────────────────────
MAX_RETRIES = 3           # 最大重试次数
BACKOFF_BASE = 1.0        # 退避基数（秒）
BACKOFF_FACTOR = 1.5      # 退避倍数
BACKOFF_MAX = 8.0         # 最大退避时间（秒）

# 可重试的 HTTP 状态码
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# ── 向后兼容别名 ──────────────────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS = READ_TIMEOUT


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否可重试。"""
    if isinstance(exc, error.HTTPError):
        return exc.code in _RETRYABLE_STATUS
    if isinstance(exc, error.URLError):
        # 连接失败、DNS 失败、超时等
        return True
    if isinstance(exc, TimeoutError, OSError):
        return True
    return False


def open_url(url: str, http_client: object | None = None, timeout: int = READ_TIMEOUT):
    """发起 HTTP 请求，自动重试可恢复错误。"""
    req = request.Request(url, headers=DEFAULT_HEADERS)
    opener = http_client or request.urlopen

    last_exc = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return opener(req, timeout=timeout)
        except Exception as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES or not _is_retryable(exc):
                raise
            delay = min(BACKOFF_BASE * (BACKOFF_FACTOR ** attempt), BACKOFF_MAX)
            logger.warning(
                "[http_client] %s attempt %d/%d failed: %s; retrying in %.1fs",
                url, attempt + 1, 1 + MAX_RETRIES, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # unreachable, but satisfies type checker


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
