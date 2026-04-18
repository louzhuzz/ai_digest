with open("D:/AIcodes/openclaw/ai_digest_agent/output/drafts/2026-04-17_morning_report.md", encoding="utf-8") as f:
    content = f.read()
for line in content.split("\n"):
    if "数据获取失败" in line or "当前价格" in line:
        print(line)
