# ai_digest/cluster_tagger.py
from __future__ import annotations

import json
from dataclasses import replace
from urllib import request

TOPIC_TAG_PROMPT = """你是一个 AI 热点编辑。请为以下每个事件 cluster 生成一个简短的话题标签（最多 5 个字）。

候选标签池：
- 模型发布（指新模型、功能更新）
- 开源项目（指 GitHub 项目、库、工具）
- 代码能力（指编码、调试相关能力更新）
- 行业动态（指公司合作、投资、政策）
- 社区热点（指社区讨论、HackerNews 趋势）

输入：clusters 列表，每个含多条新闻标题
输出：JSON数组，每个元素 {cluster_index, topic_tag}

请直接输出 JSON，不要解释。"""


class ClusterTagger:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 30,
        transport=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or request.urlopen

    def tag_clusters(self, clusters: list) -> list:
        if not clusters:
            return clusters

        cluster_summaries = self._build_cluster_summaries(clusters)
        raw_tag_json = self._call_ark(cluster_summaries)

        tag_map = self._parse_tag_response(raw_tag_json, len(clusters))

        result = []
        for i, cluster in enumerate(clusters):
            tag = tag_map.get(i, "")
            result.append(replace(cluster, topic_tag=tag))
        return result

    def _build_cluster_summaries(self, clusters: list) -> str:
        lines = []
        for i, cluster in enumerate(clusters):
            titles = " | ".join(item.title for item in cluster.items)
            lines.append(f"[{i}] {cluster.category}: {titles}")
        return "\n".join(lines)

    def _call_ark(self, cluster_summaries: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": TOPIC_TAG_PROMPT},
                {"role": "user", "content": cluster_summaries},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.transport(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"ARK cluster tagging failed: {exc}") from exc

        choices = decoded.get("choices") or []
        if not choices:
            raise RuntimeError(f"ARK response missing choices: {decoded}")
        return str(choices[0].get("message", {}).get("content", "")).strip()

    def _parse_tag_response(self, raw: str, cluster_count: int) -> dict[int, str]:
        try:
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                raw_clean = "\n".join(line for line in lines if not line.strip().startswith("```"))
            tags = json.loads(raw_clean)
            if not isinstance(tags, list):
                return {}
            return {item["cluster_index"]: item["topic_tag"] for item in tags if "cluster_index" in item and "topic_tag" in item}
        except Exception:
            return {}