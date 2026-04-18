"""
fetch_hs300.py — 沪深300 ETF 专用数据获取（Yahoo Finance 备用）
"""

import json, urllib.request, time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def fetch_hs300_yahoo() -> dict:
    """
    用 Yahoo Finance 获取沪深300ETF（510300.SS）近6日数据。
    备用方案，当 AkShare push2his.eastmoney.com 超时时使用。
    """
    url = "https://query1.finance.yahoo.com/v8/finance/chart/510300.SS?range=6d&interval=1d"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quotes = result["indicators"]["quote"][0]
    closes = [c for c in quotes["close"] if c is not None]

    if not closes:
        raise ValueError("No close data")

    latest = closes[-1]
    prev   = closes[-2] if len(closes) > 1 else latest
    chg    = round((latest - prev) / prev * 100, 2)
    pct5   = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if len(closes) >= 2 else 0

    return {
        "price":      round(latest, 3),
        "prev_close": round(prev, 3),
        "change_pct": chg,
        "pct_5d":     pct5,
        "closes_5d":  [round(c, 3) for c in closes[-5:]],
        "error": None,
    }


if __name__ == "__main__":
    print("Testing Yahoo Finance fallback for 沪深300ETF...")
    result = fetch_hs300_yahoo()
    print("Result:", result)
