"""
generate_weekly_report.py — 生成指数基金周报并发送邮件

数据源：Yahoo Finance（全天候稳定）
"""

import argparse, json, os, sys, time, urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from send_email import send_email


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

# Yahoo Finance 代码
ETFS = [
    ("沪深300ETF",  "510300.SS"),
    ("中证500ETF",  "510500.SS"),
    ("红利低波ETF", "512480.SS"),
    ("纳指ETF",    "159941.SZ"),   # A股场内纳指ETF
]


def fetch_etf_yahoo(name: str, symbol: str, days: int = 35) -> dict:
    """
    用 Yahoo Finance 获取近 N 天日线数据。
    """
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%dd&interval=1d" % (symbol, days)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())

    result = data["chart"]["result"][0]
    quotes = result["indicators"]["quote"][0]
    timestamps = result.get("timestamp", [])
    closes = [c for c in quotes["close"] if c is not None]

    if not closes:
        return {"price": None, "error": "No data"}

    latest  = closes[-1]
    prev    = closes[-2] if len(closes) > 1 else latest
    pct_1w  = round((closes[-1] - closes[-6]) / closes[-6] * 100, 2) if len(closes) >= 6 else 0.0
    pct_2w  = round((closes[-1] - closes[-11]) / closes[-11] * 100, 2) if len(closes) >= 11 else 0.0
    pct_1m  = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes else 0.0

    # 近5周每周收盘（每5个交易日一组）
    weekly_closes = []
    for i in range(0, min(len(closes), 35), 5):
        week_chunk = closes[i:i+5]
        if week_chunk:
            weekly_closes.append(round(week_chunk[-1], 3))

    return {
        "price":    round(latest, 3),
        "prev":     round(prev, 3),
        "change_pct": round((latest - prev) / prev * 100, 2),
        "pct_1w":   pct_1w,
        "pct_2w":   pct_2w,
        "pct_1m":   pct_1m,
        "weekly":   weekly_closes[-5:],
        "closes_5d": [round(c, 3) for c in closes[-5:]],
        "error":    None,
    }


def fetch_all_weekly() -> dict:
    results = {}
    for name, symbol in ETFS:
        print("  Fetching %s (%s)..." % (name, symbol), end=" ", flush=True)
        try:
            result = fetch_etf_yahoo(name, symbol)
            results[name] = result
            if result.get("error"):
                print("ERROR: %s" % result["error"][:60])
            else:
                print("OK price=%.3f 1w=%+.2f%% 2w=%+.2f%%" % (
                    result["price"], result["pct_1w"], result["pct_2w"]))
        except Exception as e:
            results[name] = {"price": None, "error": str(e)}
            print("ERROR: %s" % str(e)[:60])
        time.sleep(1)
    return results


def judgment_desc(name: str, v: dict) -> str:
    if v.get("error"):
        return "继续观察"
    pct1w = v.get("pct_1w", 0)
    pct2w = v.get("pct_2w", 0)
    if name == "纳指ETF":
        return "降低节奏（近2周强势）" if pct2w > 5 else "维持定投"
    if pct1w > 8 or pct2w > 12:
        return "暂停观望（连续强势）"
    if pct1w < -5:
        return "可小幅加仓（回调提供机会）"
    return "维持原定投计划"


def build_weekly_report(today: str, data: dict) -> str:
    week_end   = date.today()
    week_start = week_end - timedelta(days=6)
    week_label = "%s ~ %s" % (week_start.isoformat(), week_end.isoformat())

    lines = [
        "# 指数基金周报（%s）" % week_label,
        "",
        "## 一、本周市场总结",
        "- A股：本周整体震荡，沪深300窄幅波动，中证500偏强，红利低波防御属性凸显",
        "- 美股：纳指本周冲高后有所回调，整体仍处强势格局",
        "- 宏观：国内经济修复预期仍在，海外美联储降息预期反复",
        "",
        "## 二、各标的本周表现",
        "",
    ]

    for name, code in [("沪深300ETF","510300"), ("中证500ETF","510500"),
                       ("红利低波ETF","512480"), ("纳指ETF","159941")]:
        v = data.get(name, {})
        if v.get("error"):
            price_str = "数据获取失败"
            pct1w = pct2w = 0
        else:
            price_str = "%.3f" % v["price"]
            pct1w = v.get("pct_1w", 0)
            pct2w = v.get("pct_2w", 0)

        s1 = "+" if pct1w >= 0 else ""
        s2 = "+" if pct2w >= 0 else ""

        trend = "震荡上行" if pct2w > 3 else ("震荡下行" if pct2w < -3 else "区间震荡")
        remark = "防御属性持续发挥作用" if name == "红利低波ETF" else ("注意高波动风险" if name == "纳指ETF" else "估值提供支撑")
        valuation = {
            "沪深300ETF": "历史中位附近",
            "中证500ETF": "历史中低位",
            "红利低波ETF": "相对合理，高股息安全边际",
            "纳指ETF": "纳指整体PE偏高，美股高估值下波动加大",
        }

        lines.extend([
            "### %s（%s）" % (name, code),
            "- 当前价格：%s | 近1周：%s%.2f%% | 近2周：%s%.2f%%" % (price_str, s1, pct1w, s2, pct2w),
            "- 本周趋势：%s，%s" % (trend, remark),
            "- 估值位置：%s" % valuation.get(name, ""),
            "",
        ])

    j300   = judgment_desc("沪深300ETF", data.get("沪深300ETF", {}))
    j500   = judgment_desc("中证500ETF", data.get("中证500ETF", {}))
    jLow   = judgment_desc("红利低波ETF", data.get("红利低波ETF", {}))
    jNasdaq= judgment_desc("纳指ETF", data.get("纳指ETF", {}))

    lines.extend([
        "## 三、组合表现评估",
        "- 整体配置均衡，A股 + 海外组合分布合理",
        "- 红利低波作为防御仓位，本周表现稳健",
        "- 纳指仓位应控制比例，避免单一资产过度集中",
        "",
        "## 四、下周策略建议",
        "- 沪深300ETF：**%s**" % j300,
        "- 中证500ETF：**%s**" % j500,
        "- 红利低波ETF：**%s**" % jLow,
        "- 纳指ETF：**%s**" % jNasdaq,
        "",
        "## 五、风险提示",
        "- **宏观风险**：国内经济数据仍有反复，A股企业盈利改善需时间",
        "- **政策风险**：货币宽松预期若有变化，A股有阶段性调整压力",
        "- **海外风险**：美股高估值+鹰派预期反复，纳指短期波动可能加大",
        "- **仓位风险**：纳指若连续强势，警惕追高风险",
        "",
        "## 六、定投纪律提醒",
        "- 严格按照投资规则执行：不追高、不恐慌、不一把梭",
        "- 纳指单次最大投入不超过100元（规则限制）",
        "- 每月定投总额不超过1000元预算",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="生成周报并发送邮件")
    parser.add_argument("--dry-run", action="store_true", help="不发送邮件")
    args = parser.parse_args()

    today = date.today().isoformat()
    print("=== Weekly Report [%s] ===\n" % today)

    print("[1/3] Fetching weekly data (Yahoo Finance)...\n")
    data = fetch_all_weekly()

    print("\n[2/3] Generating report...")
    report = build_weekly_report(today, data)

    draft_dir  = os.path.join(ROOT, "output", "drafts")
    draft_path = os.path.join(draft_dir, "%s_weekly_report.md" % today)
    os.makedirs(draft_dir, exist_ok=True)
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("[OK] Draft: %s" % draft_path)

    if args.dry_run:
        print("\n[DRY RUN] Preview (first 800 chars):\n")
        print(report[:800])
        return

    print("\n[3/3] Sending email...")
    subject = "[周报] 指数基金 %s" % today
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
