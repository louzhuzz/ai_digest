"""Check AI relevance per source and write results to file"""
import json

with open("data/items.json", "r", encoding="utf-8") as f:
    items = json.load(f)

ai_kw = ["ai", "大模型", "模型", "openai", "anthropic", "claude", "deepseek",
         "agent", "智能体", "gemini", "llm", "gpt", "多模态", "推理", "开源",
         "芯片", "gpu", "训练", "编程", "代码", "视觉", "语音", "图像", "视频生成",
         "豆包", "千问", "kimi", "生成", "对话", "智能化", "ai原生", "ai原"]

sources_to_check = ["36氪", "雷锋网", "爱范儿", "量子位"]

lines = []
total_all = 0
ai_all = 0
for src_name in sources_to_check:
    src_items = [i for i in items if i["source"] == src_name]
    total = len(src_items)
    total_all += total
    ai_count = sum(1 for i in src_items if any(k.lower() in i["title"].lower() for k in ai_kw))
    ai_all += ai_count
    pct = ai_count / total * 100 if total > 0 else 0
    lines.append(f"\n=== {src_name} ===")
    lines.append(f"Total: {total} | AI-related: {ai_count}/{total} ({pct:.0f}%)")
    for i in src_items:
        t = i["title"]
        is_ai = any(k.lower() in t.lower() for k in ai_kw)
        tag = "AI" if is_ai else "--"
        lines.append(f"  [{tag}] {t[:80]}")

lines.append(f"\n\n=== Summary ===")
pct = ai_all / total_all * 100 if total_all > 0 else 0
lines.append(f"Total AI items: {ai_all}/{total_all} ({pct:.0f}%)")

with open("data/ai_check.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Written to data/ai_check.txt")
