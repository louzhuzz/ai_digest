import urllib.request, json, time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_yahoo(symbol, name, range_="5d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval=1d"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    result = data["chart"]["result"][0]
    meta = result["meta"]
    quotes = result["indicators"]["quote"][0]
    closes = [c for c in quotes["close"] if c is not None]
    timestamps = result["timestamp"]

    prev = meta.get("previousClose") or (closes[-2] if len(closes) >= 2 else None)
    latest = closes[-1] if closes else None
    change_pct = None
    if prev and latest:
        change_pct = (latest - prev) / prev * 100

    # 近5日涨跌
    recent5 = closes[-5:] if len(closes) >= 5 else closes
    pct5 = None
    if len(recent5) >= 2:
        pct5 = (recent5[-1] - recent5[0]) / recent5[0] * 100

    print(f"【{name}】({symbol})")
    print(f"  最新价: {latest:.3f}" if latest else "  最新价: N/A")
    print(f"  昨收: {prev:.3f}" if prev else "  昨收: N/A")
    if change_pct is not None:
        print(f"  今日涨跌: {change_pct:+.2f}%")
    print(f"  近5日: {[round(c,2) for c in recent5]}")
    if pct5 is not None:
        print(f"  近5日涨跌: {pct5:+.2f}%")
    print()
    return {"name": name, "symbol": symbol, "price": latest,
            "prev": prev, "change_pct": change_pct,
            "recent5": recent5, "pct5": pct5}

etfs = [
    ("510300.SS", "沪深300ETF"),
    ("510500.SS", "中证500ETF"),
    ("512480.SS", "红利低波ETF"),
    ("QQQ", "纳指ETF"),
]

results = []
for symbol, name in etfs:
    try:
        r = fetch_yahoo(symbol, name)
        results.append(r)
    except Exception as e:
        print(f"【{name}】({symbol}): ERROR {e}")
    time.sleep(2)

print("=== 数据获取完成 ===")
