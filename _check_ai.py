"""Check AI relevance of each new source"""
import json, re
from datetime import datetime, timezone

with open("data/items.json", "r", encoding="utf-8") as f:
    items = json.load(f)

ai_kw = ["ai", "大模型", "模型", "openai", "anthropic", "claude", "deepseek", "agent",
         "智能体", "gemini", "llm", "gpt", "vllm", "hugging", "github", "代码", "编程",
         "多模态", "推理", "开源", "芯片", "gpu", "训练", "数据", "安全", "编程",
         "gpt-image", "sam", "diffusion", "transformer", "神经网络", "深度学习",
         "机器学习", "自然语言", "计算机视觉", "强化学习", "rss", "feed", "generative",
         "生成", "对话", "语音", "图像", "视频生成", "豆包", "千问", "kimi", "元智能",
         "ai原生", "ai原生", "大模型上车", "智能化"]

sources_to_check = ["36氪", "雷锋网", "爱范儿", "量子位"]

now = datetime.now(timezone.utc)
today = now.date()

for src_name in sources_to_check:
    src_items = [i for i in items if i["source"] == src_name]
    total = len(src_items)
    
    # Count AI-related
    ai_count = 0
    ai_titles = []
    for i in src_items:
        t = i["title"]
        if any(k.lower() in t.lower() for k in ai_kw):
            ai_count += 1
            if len(ai_titles) < 10:
                ai_titles.append(t[:80])
    
    # Today only
    today_items = 0
    for i in src_items:
        try:
            dt = datetime.fromisoformat(i["published_at"])
            if dt.date() == today:
                today_items += 1
        except:
            pass
    
    print(f"\n=== {src_name} ===")
    print(f"Total items in pool: {total}")
    print(f"Today items: {today_items}")
    print(f"AI-related: {ai_count}/{total} ({ai_count/total*100:.0f}%)")
    if ai_titles:
        print("AI titles:")
        for t in ai_titles:
            print(f"  {t}")
