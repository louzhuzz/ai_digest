"""
generate_close_report.py — 生成收盘复盘并发送邮件
"""

import argparse, json, os, sys, time, urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from send_email import send_email


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

ETFS = [
    ("沪深300ETF",  "510300.SS"),
    ("中证500ETF",  "510500.SS"),
    ("红利低波ETF", "512480.SS"),
    ("纳指ETF",    "159941.SZ"),
]


def fetch_etf(name: str, symbol: str) -> dict:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=6d&interval=1d" % symbol
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read())

    result = data["chart"]["result"][0]
    quotes = result["indicators"]["quote"][0]
    closes = [c for c in quotes["close"] if c is not None]

    if not closes:
        return {"price": None, "error": "No data"}

    latest = closes[-1]
    prev   = closes[-2] if len(closes) > 1 else latest
    chg    = round((latest - prev) / prev * 100, 2)
    pct5   = round((closes[-1] - closes[0]) / closes[0] * 100, 2)

    return {
        "price":      round(latest, 3),
        "prev_close": round(prev, 3),
        "change_pct": chg,
        "pct_5d":     pct5,
        "closes_5d":  [round(c, 3) for c in closes[-5:]],
        "error":      None,
    }


def fetch_all() -> dict:
    results = {}
    for name, symbol in ETFS:
        print("  Fetching %s..." % name, end=" ", flush=True)
        try:
            r = fetch_etf(name, symbol)
            results[name] = r
            if r.get("error"):
                print("ERROR: %s" % r["error"][:50])
            else:
                print("OK: %.3f (%+.2f%%)" % (r["price"], r["change_pct"]))
        except Exception as e:
            results[name] = {"price": None, "error": str(e)}
            print("ERROR: %s" % str(e)[:50])
        time.sleep(1)
    return results


def build_close_report(today: str, data: dict) -> str:
    lines = [
        "# 指数基金收盘复盘（日期：%s）" % today,
        "",
        "## 一、今日市场表现总结",
        "",
    ]

    for name, symbol in ETFS:
        v = data.get(name, {})
        if v.get("error"):
            lines.append("### %s" % name)
            lines.append("- 数据获取失败：%s" % v["error"][:80])
            lines.append("")
            continue

        chg  = v.get("change_pct", 0)
        pct5 = v.get("pct_5d", 0)
        s    = "+" if chg >= 0 else ""

        abnormal = abs(chg) > 2

        lines.extend([
            "### %s" % name,
            "- 今日涨跌幅：%s%.2f%%" % (s, chg),
            "- 近5日涨跌：%s%.2f%%" % ("+" if pct5 >= 0 else "", pct5),
            "- 是否异常波动：%s" % ("**是**（|涨跌幅|>2%%）" if abnormal else "否"),
            "- 当前价格：%.3f（昨收：%.3f）" % (v["price"], v["prev_close"]),
            "",
        ])

    def is_good_day(d):
        if d.get("error"):
            return "数据不足，无法判断"
        chg = abs(d.get("change_pct", 0))
        if chg > 3:
            return "风险偏高，建议观望"
        return "正常定投日"

    all_normal = all(
        abs(d.get("change_pct", 0)) <= 2
        for d in data.values()
        if not d.get("error")
    )

    lines.extend([
        "## 二、纪律检查",
        "- 今日是否适合定投：%s" % ("是" if all_normal else "部分标的出现异常波动，请谨慎"),
        "- 是否存在追高风险：%s" % (
            "否，各标的无异常" if all_normal else "部分标的波动较大，需观察"
        ),
        "- 是否应避免操作：%s" % ("否，纪律执行正常" if all_normal else "建议观察为主"),
        "",
        "## 三、各标的评估",
    ])

    for name, _ in ETFS:
        v = data.get(name, {})
        chg = v.get("change_pct", 0)
        if v.get("error"):
            judgment = "数据不足，继续观察"
        elif chg > 3:
            judgment = "涨幅较大，谨慎追加"
        elif chg < -3:
            judgment = "出现回调，可执行定投策略"
        else:
            judgment = "正常波动，维持节奏"
        lines.append("- %s：**%s**" % (name, judgment))

    lines.extend([
        "",
        "## 四、今日结论",
        "%s" % (
            "今日整体正常，无异常信号，纪律执行良好。"
            if all_normal
            else "部分标的波动较大，建议明日观察后再操作，不盲目追高或恐慌。"
        ),
        "",
        "## 五、明日关注点",
        "- 关注今日异常波动标的的开盘表现",
        "- 纳指若连续强势，注意控制仓位",
        "- 国内宏观面有无新的政策或数据发布",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="生成收盘复盘")
    parser.add_argument("--dry-run", action="store_true", help="不发送邮件")
    args = parser.parse_args()

    today = date.today().isoformat()
    print("=== Close Report [%s] ===\n" % today)

    print("[1/3] Fetching data...\n")
    data = fetch_all()

    print("\n[2/3] Generating report...")
    report = build_close_report(today, data)

    draft_dir  = os.path.join(ROOT, "output", "drafts")
    draft_path = os.path.join(draft_dir, "%s_close_report.md" % today)
    os.makedirs(draft_dir, exist_ok=True)
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("[OK] Draft: %s" % draft_path)

    if args.dry_run:
        print("\n[DRY RUN] Preview:\n")
        print(report[:800])
        return

    print("\n[3/3] Sending email...")
    subject = "[收盘复盘] 指数基金 %s" % today
    ok = send_email(
        to_addr="liuyuyangxxx@163.com",
        subject=subject,
        body=report,
        from_addr="liuyuyangxxx@163.com",
        password="DEkFgXSgjrSi5ZVZ",
    )
    print("\n=== %s ===" % ("Done" if ok else "Failed"))


if __name__ == "__main__":
    main()
