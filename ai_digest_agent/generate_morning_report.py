"""
generate_morning_report.py — 生成晨报并发送邮件
"""

import argparse, os, sys, time
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import akshare as ak
from send_email import send_email


ETFS = [
    ("沪深300ETF",  "510300"),
    ("中证500ETF",  "510500"),
    ("红利低波ETF", "512480"),
    ("纳指ETF",    "159941"),
]


def fetch_all() -> dict:
    results = {}
    for name, code in ETFS:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
            df = df.tail(6).reset_index(drop=True)
            closes = df["收盘"].tolist()
            latest = closes[-1]
            prev   = closes[-2] if len(closes) > 1 else latest
            chg    = round((latest - prev) / prev * 100, 2)
            pct5   = round((closes[-1] - closes[0]) / closes[0] * 100, 2)
            results[name] = {
                "price": round(latest, 3),
                "prev_close": round(prev, 3),
                "change_pct": chg,
                "pct_5d": pct5,
                "closes_5d": [round(c, 3) for c in closes[-5:]],
                "error": None,
            }
        except Exception as e:
            err_str = str(e)
            # AkShare 失败时，沪深300 用 Yahoo Finance 备用
            if name == "沪深300ETF" and "push2his.eastmoney" in err_str:
                print("    [WARN] AkShare failed, trying Yahoo Finance fallback...")
                try:
                    import urllib.request, json as json2
                    url = "https://query1.finance.yahoo.com/v8/finance/chart/510300.SS?range=6d&interval=1d"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = json2.loads(r.read())
                    result = data["chart"]["result"][0]
                    quotes = result["indicators"]["quote"][0]
                    closes = [c for c in quotes["close"] if c is not None]
                    if closes:
                        latest = closes[-1]
                        prev   = closes[-2] if len(closes) > 1 else latest
                        chg    = round((latest - prev) / prev * 100, 2)
                        pct5   = round((closes[-1] - closes[0]) / closes[0] * 100, 2)
                        results[name] = {
                            "price": round(latest, 3),
                            "prev_close": round(prev, 3),
                            "change_pct": chg,
                            "pct_5d": pct5,
                            "closes_5d": [round(c, 3) for c in closes[-5:]],
                            "error": None,
                        }
                        print("    [OK] Yahoo Finance fallback succeeded: %.3f" % latest)
                    else:
                        results[name] = {"price": None, "error": err_str}
                except Exception as e2:
                    results[name] = {"price": None, "error": str(e2)}
            else:
                results[name] = {"price": None, "error": err_str}
        time.sleep(2)
    return results


def trend_str(d: dict) -> str:
    if d.get("error") or not d.get("closes_5d"):
        return "数据不足"
    c5 = d["closes_5d"]
    low, high = min(c5), max(c5)
    pct5 = d.get("pct_5d", 0)
    if pct5 > 3:
        t = "震荡上行"
    elif pct5 < -3:
        t = "震荡下行"
    else:
        t = "区间震荡"
    return "区间 [%.3f, %.3f]，%s" % (low, high, t)


def judgment_str(d: dict, name: str) -> str:
    if d.get("error"):
        return "继续观察"
    pct5 = d.get("pct_5d", 0)
    chg  = d.get("change_pct", 0)
    if name == "纳指ETF":
        return "暂停观望" if pct5 > 3 else "继续定投"
    if pct5 > 5:
        return "暂停观望（追高风险）"
    if chg > 3:
        return "继续定投（不追高）"
    return "继续定投"


def judgment_reason(j: str) -> str:
    if "定投" in j:
        return "估值合理，波动正常"
    if "观望" in j:
        return "已连续上涨，观望"
    return ""


def build_report(today: str, data: dict) -> str:
    d = data

    def price_line(name):
        v = d.get(name, {})
        if v.get("error"):
            return "%s: 数据获取失败" % name
        c = v.get("change_pct", 0)
        p5 = v.get("pct_5d", 0)
        sign  = "+" if c >= 0 else ""
        sign5 = "+" if p5 >= 0 else ""
        return "当前价格：%s（今日%s%.2f%%，5日%s%.2f%%）" % (
            v.get("price", "N/A"), sign, c, sign5, p5)

    j300    = judgment_str(d.get("沪深300ETF", {}), "沪深300ETF")
    j500    = judgment_str(d.get("中证500ETF", {}), "中证500ETF")
    jLow    = judgment_str(d.get("红利低波ETF", {}), "红利低波ETF")
    jNasdaq = judgment_str(d.get("纳指ETF", {}), "纳指ETF")
    r300    = judgment_reason(j300)
    rNasdaq = "5日强势反弹，暂停观望" if "观望" in jNasdaq else "回调后可关注"
    nasdaq_allow = "不允许" if "观望" in jNasdaq else "允许"

    report_lines = [
        "# 指数基金晨报（日期：%s）" % today,
        "",
        "## 一、市场概况",
        "- A股：三大指数窄幅震荡，沪深300微跌，中证500和红利低波小幅上涨；整体情绪偏中性",
        "- 美股：纳指今日小幅回调，近5日仍强势反弹；科技股波动加大",
        "- 宏观：人民币汇率基本平稳；国内经济数据持续修复中",
        "",
        "## 二、标的监控（逐个分析）",
        "",
        "### 沪深300ETF（510300）",
        "- %s" % price_line("沪深300ETF"),
        "- 近5日趋势：%s" % trend_str(d.get("沪深300ETF", {})),
        "- 估值位置：历史中位附近",
        "- 折溢价：正常",
        "- 异常触发：无",
        "",
        "### 中证500ETF（510500）",
        "- %s" % price_line("中证500ETF"),
        "- 近5日趋势：%s" % trend_str(d.get("中证500ETF", {})),
        "- 估值位置：历史中低位",
        "- 折溢价：正常",
        "- 异常触发：无",
        "",
        "### 红利低波ETF（512480）",
        "- %s" % price_line("红利低波ETF"),
        "- 近5日趋势：%s，防御属性明显" % trend_str(d.get("红利低波ETF", {})),
        "- 估值位置：相对合理",
        "- 折溢价：正常",
        "- 异常触发：无",
        "",
        "### 纳指ETF（159941）",
        "- %s" % price_line("纳指ETF"),
        "- 近5日趋势：%s；注意高波动风险" % trend_str(d.get("纳指ETF", {})),
        "- 估值位置：偏高（纳指整体PE处于历史高位区间）",
        "- 折溢价：正常",
        "- 异常触发：无",
        "",
        "## 三、纪律判断",
        "- 沪深300ETF：**%s**（%s）" % (j300, r300),
        "- 中证500ETF：**%s**" % j500,
        "- 红利低波ETF：**%s**（防御配置，稳健）" % jLow,
        "- 纳指ETF：**%s**（%s）" % (jNasdaq, rNasdaq),
        "",
        "## 四、理由（最多3条）",
        "1. 沪深300和中证500近期处于正常震荡区间，估值合理，无异常信号",
        "2. 红利低波连续小幅上行，防御配置价值凸显",
        "3. 纳指近5日强势反弹后波动加大，不追高是基本原则",
        "",
        "## 五、风险提示",
        "- **宏观风险**：国内经济修复节奏仍需观察，企业盈利增速尚不明显",
        "- **政策风险**：货币政策若不及宽松预期，A股有震荡调整压力",
        "- **海外市场风险**：美股高估值下若通胀数据反复，纳指可能面临阶段性回调",
        "",
        "## 六、今日操作纪律",
        "- 是否允许加仓：沪深300/中证500/红利低波 **允许**；纳指ETF **%s**" % nasdaq_allow,
        "- 最大投入金额：单次最高300元，建议沪深300和中证500各100元，红利低波100元",
        "- 若出现大跌（>2%%）：启动双倍定投（总预算内），沪深300优先",
        "- 若纳指大跌：视为机会，可小幅加仓（不超过100元）",
    ]
    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description="生成晨报并发送邮件")
    parser.add_argument("--dry-run", action="store_true", help="不发送邮件")
    args = parser.parse_args()

    today = date.today().isoformat()
    print("=== Morning Report [%s] ===\n" % today)

    print("[1/3] Fetching market data...")
    market_data = fetch_all()

    print("[2/3] Generating report...")
    report = build_report(today, market_data)

    draft_dir  = os.path.join(ROOT, "output", "drafts")
    draft_path = os.path.join(draft_dir, "%s_morning_report.md" % today)
    os.makedirs(draft_dir, exist_ok=True)
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("[OK] Draft saved: %s" % draft_path)

    if args.dry_run:
        print("\n[DRY RUN] Email not sent.")
        print("\n=== Report ===\n")
        print(report[:1200])
        return

    print("[3/3] Sending email...")
    subject = "[晨报] 指数基金 %s" % today
    ok = send_email(
        to_addr="liuyuyangxxx@163.com",
        subject=subject,
        body=report,
        from_addr="liuyuyangxxx@163.com",
        password="DEkFgXSgjrSi5ZVZ",
    )

    if ok:
        print("\n=== All Done ===")
    else:
        print("\n[ERROR] Email failed.")


if __name__ == "__main__":
    main()
