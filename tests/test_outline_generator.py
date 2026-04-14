# tests/test_outline_generator.py
from __future__ import annotations
import unittest
import json
from ai_digest.outline_generator import OutlineGenerator, Outline, SectionSpec


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


class FakeTransport:
    def __init__(self, content: str):
        self.content = content

    def __call__(self, req, timeout=0):
        return _Response(json.dumps({"choices": [{"message": {"content": self.content}}]}).encode())

class OutlineGeneratorTest(unittest.TestCase):
    def test_generate_returns_outline_with_title_lede_sections(self):
        transport = FakeTransport(json.dumps({
            "title": "AI 热点日报",
            "lede": "今天有三条值得关注的动态。",
            "sections": [
                {"heading": "模型发布", "key_points": ["OpenAI 发布 GPT-5"], "source_hints": ["机器之心"]},
                {"heading": "开源项目", "key_points": ["Archon 框架更新"], "source_hints": ["GitHub"]},
            ]
        }))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is not None
        assert outline.title == "AI 热点日报"
        assert outline.lede == "今天有三条值得关注的动态。"
        assert len(outline.sections) == 2
        assert outline.sections[0].heading == "模型发布"

    def test_generate_returns_none_on_invalid_json(self):
        transport = FakeTransport("not json at all")
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None

    def test_generate_returns_none_on_missing_fields(self):
        transport = FakeTransport(json.dumps({"title": "Only Title"}))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None

    def test_generate_returns_none_on_empty_sections(self):
        transport = FakeTransport(json.dumps({"title": "T", "lede": "L", "sections": []}))
        gen = OutlineGenerator(api_key="test", base_url="https://ark.example.com", model="test", transport=transport)
        outline = gen.generate({"date": "2026-04-14", "items": []})
        assert outline is None