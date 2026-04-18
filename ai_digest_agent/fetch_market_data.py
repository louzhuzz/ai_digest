"""
fetch_market_data.py — 用 AkShare 获取指数基金实时+历史数据

用法：
    python fetch_market_data.py
"""

import sys, json, time, os
from datetime import date

try:
    import akshare as ak
except ImportError:
    print("请先安装：pip install akshare")
    sys.exit(1)


# A股ETF纯数字代码
ETFS = [
    ("沪深300ETF",  "510300"),
    ("中证500ETF",  "510500"),
    ("红利低波ETF", "512480"),
    ("纳指ETF",    "159941"),
]


def fetch_etf(name: str, code: str) -> dict:
    """
    用 fund_etf_hist_em 获取近6天日线。
    """
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
        if df is None or df.empty:
            return {"name": name, "code": code, "error": "no data"}

        df = df.tail(6).reset_index(drop=True)
        closes = df["收盘"].tolist()
        dates  = [str(d) for d in df["日期"].tolist()]

        latest   = closes[-1]
        prev     = closes[-2] if len(closes) > 1 else latest
        chg_pct  = round((latest - prev) / prev * 100, 2) if prev else 0.0
        pct_5d   = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else 0.0

        return {
            "name":      name,
            "code":      code,
            "price":     round(latest, 3),
            "prev_close":round(prev, 3),
            "change_pct": chg_pct,
            "pct_5d":    pct_5d,
            "closes_5d": [round(c, 3) for c in closes[-5:]],
            "dates_5d":  dates[-5:],
            "error":     None,
        }
    except Exception as e:
        return {"name": name, "code": code, "error": str(e)}


def main():
    today = date.today().isoformat()
    out_dir = "output/market_data"
    os.makedirs(out_dir, exist_ok=True)

    print(f"=== Market Data [{today}] ===\n")
    all_data = {}

    for name, code in ETFS:
        print(f"[*] {name} ({code})...", end=" ", flush=True)
        result = fetch_etf(name, code)
        all_data[name] = result

        if result.get("error"):
            print(f"ERROR: {result['error']}")
        else:
            print(f"Price={result['price']}, Chg={result['change_pct']:+.2f}%, 5d={result['pct_5d']:+.2f}%")

        time.sleep(0.5)

    out_file = f"{out_dir}/{today}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "etfs": all_data}, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Saved -> {out_file}")

    print("\n=== Summary ===")
    for name, d in all_data.items():
        if d.get("error"):
            print(f"  {name}: ERROR {d['error']}")
        else:
            print(f"  {name}: {d['price']} ({d['change_pct']:+.2f}%), 5d: {d['pct_5d']:+.2f}%")

    return all_data


if __name__ == "__main__":
    main()
