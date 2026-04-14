# tests/test_cluster_tagger.py
from __future__ import annotations
import json
import unittest
from datetime import datetime, timezone
from ai_digest.cluster_tagger import ClusterTagger
from ai_digest.models import DigestItem, EventCluster

class MockArkTransport:
    def __init__(self, response_content: str):
        self.response_content = response_content
        self.last_request = None

    def __call__(self, req, timeout=None):
        import io, json
        self.last_request = req
        # MockArkTransport receives the content that goes in choices[0].message.content
        response = {"choices": [{"message": {"content": self.response_content}}]}
        return io.BytesIO(json.dumps(response, ensure_ascii=False).encode("utf-8"))

class ClusterTaggerTest(unittest.TestCase):
    def test_tag_clusters_returns_clusters_with_topic_tag(self):
        transport = MockArkTransport(
            '[{"cluster_index":0,"topic_tag":"模型发布"},{"cluster_index":1,"topic_tag":"开源项目"}]'
        )
        tagger = ClusterTagger(
            api_key="test",
            base_url="https://ark.example.com",
            model="test-model",
            transport=transport,
        )
        item1 = DigestItem(title="OpenAI GPT-5", url="https://a.com", source="A", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.9, dedupe_key="a")
        item2 = DigestItem(title="Archon framework", url="https://b.com", source="B", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="github", score=0.8, dedupe_key="b")
        clusters = [
            EventCluster(canonical_title="OpenAI GPT-5", canonical_url="https://a.com", sources=["A"], items=[item1], score=0.9, category="event", topic_tag=""),
            EventCluster(canonical_title="Archon", canonical_url="https://b.com", sources=["B"], items=[item2], score=0.8, category="project", topic_tag=""),
        ]
        result = tagger.tag_clusters(clusters)
        assert result[0].topic_tag == "模型发布"
        assert result[1].topic_tag == "开源项目"

    def test_tag_clusters_falls_back_to_empty_on_parse_error(self):
        transport = MockArkTransport("not valid json")
        tagger = ClusterTagger(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        item = DigestItem(title="Test", url="https://x.com", source="X", published_at=datetime(2026,4,14,tzinfo=timezone.utc), category="news", score=0.5, dedupe_key="x")
        cluster = EventCluster(canonical_title="Test", canonical_url="https://x.com", sources=["X"], items=[item], score=0.5, category="event", topic_tag="")
        result = tagger.tag_clusters([cluster])
        assert result[0].topic_tag == ""