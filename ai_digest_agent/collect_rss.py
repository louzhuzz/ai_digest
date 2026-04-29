"""
collect_rss.py — 纯 HTTP RSS 收集器（无需 ai_digest，云端可用）

用法：
    python collect_rss.py
    python collect_rss.py --sources github,hn,hf,jiqizhixin
"""

import argparse, feedparser, json, os, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html import unescape
import re


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Digest/1.0)"}

ROOT   = Path(__file__).parent
OUTDIR = ROOT / "output" / "candidates"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ── RSS 源配置 ────────────────────────────────────────────────────────────
RSS_SOURCES = {
    "github": {
        "name": "GitHub Trending",
        "url": "https://github.com/trending/ai.rss",      # 不存在，用备用
        "fallback": "https://github.com/trending.rss",
        "category": "github",
        "ai_keywords": ["ai", "llm", "model", "agent", "gpt", "claude", "deep learning"],
    },
    "hn": {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "category": "news",
        "ai_keywords": ["AI", "LLM", "GPT", "model", "language model", "agent", "deep learning"],
    },
    "hf": {
        "name": "HuggingFace",
        "url": "https://huggingface.co/api/articles?sort=latest&limit=20",
        "category": "project",
        "ai_keywords": [],
        "is_json": True,
    },
    "jiqizhixin": {
        "name": "机器之心",
        "url": "https://www.jiqizhixin.com/rss",
        "category": "news",
        "ai_keywords": ["AI", "大模型", "LLM", "模型", "智能体", "开源"],
    },
    "xinzhiyuan": {
        "name": "新智元",
        "url": "https://www.36kr.com/feed",
        "category": "news",
        "ai_keywords": ["AI", "大模型", "LLM", "智能", "ChatGPT"],
    },
    "qbitai": {
        "name": "量子位",
        "url": "https://www.qbitai.com/feed",
        "category": "news",
        "ai_keywords": ["AI", "大模型", "LLM", "模型", "开源"],
    },
}


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def is_ai_related(title: str, summary: str, keywords: list) -> bool:
    if not keywords:
        return True
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in keywords)


def fetch_rss(source_key: str, cfg: dict) -> list[dict]:
    """抓取单个 RSS 源，返回 DigestItem 风格字典列表"""
    url = cfg.get("fallback") or cfg["url"]
    name = cfg["name"]
    category = cfg["category"]
    keywords = cfg.get("ai_keywords", [])
    is_json = cfg.get("is_json", False)

    items = []

    try:
        if is_json:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            for article in data[:15]:
                title   = strip_tags(article.get("title", ""))
                summary = strip_tags(article.get("description", article.get("summary", "")))
                link    = article.get("url", article.get("link", ""))
                if not title or not link:
                    continue
                if not is_ai_related(title, summary, keywords):
                    continue
                items.append({
                    "title":     title[:200],
                    "url":       link,
                    "source":    name,
                    "category":  category,
                    "summary":   summary[:300],
                    "published_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                    "dedupe_key": link,
                    "metadata":  {"stars_growth": 0, "page_url": url},
                })
        else:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                feed = feedparser.parse(r.read())

            for entry in feed.entries[:15]:
                title   = strip_tags(entry.get("title", ""))
                summary = strip_tags(entry.get("summary", entry.get("description", "")))
                link    = entry.get("link", "")
                if not title:
                    continue
                if keywords and not is_ai_related(title, summary, keywords):
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                else:
                    pub_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

                items.append({
                    "title":     title[:200],
                    "url":       link,
                    "source":    name,
                    "category":  category,
                    "summary":   summary[:300],
                    "published_at": pub_dt.isoformat(),
                    "dedupe_key": link,
                    "metadata":  {"stars_growth": 0, "page_url": url},
                })

        print(f"  [{name}] -> {len(items)} items")
        return items

    except Exception as e:
        print(f"  [{name}] ERROR: {str(e)[:80]}")
        return []


def collect_all(source_keys: list[str]) -> list[dict]:
    """收集所有指定源"""
    all_items = []
    for key in source_keys:
        if key not in RSS_SOURCES:
            print(f"  [WARN] Unknown source: {key}")
            continue
        items = fetch_rss(key, RSS_SOURCES[key])
        all_items.extend(items)
        time.sleep(1)
    return all_items


def main():
    parser = argparse.ArgumentParser(description="收集 AI 热点 RSS")
    parser.add_argument(
        "--sources",
        default="hn,hf,jiqizhixin,qbitai",
        help="数据源（hn/hf/jiqizhixin/xinzhiyuan/qbitai），逗号分隔",
    )
    parser.add_argument("--dry-run", action="store_true", help="不保存")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]
    today   = datetime.now(timezone.utc).date().isoformat()

    print(f"=== Collect [{today}] Sources: {sources} ===\n")

    all_items = collect_all(sources)
    print(f"\nTotal: {len(all_items)} items")

    if not all_items:
        print("[WARN] No items collected, check network.")
        return

    if args.dry_run:
        print("[dry-run] Not saved")
        return

    out_file = OUTDIR / f"{today}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"Saved -> {out_file}")


if __name__ == "__main__":
    main()
