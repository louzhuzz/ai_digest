import sys, time
sys.path.insert(0, ".")
import akshare as ak

for name, code in [
    ("沪深300ETF",  "510300"),
    ("中证500ETF",  "510500"),
    ("红利低波ETF", "512480"),
    ("纳指ETF",    "159941"),
]:
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
        df = df.tail(2)
        print(name, "OK:", df["收盘"].tolist())
    except Exception as e:
        print(name, "ERROR:", str(e)[:200])
    time.sleep(2)
