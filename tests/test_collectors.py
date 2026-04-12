from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_digest.collectors.github import GitHubTrendingCollector
from ai_digest.collectors.rss import RSSCollector


class CollectorParserTest(unittest.TestCase):
    def test_rss_collector_parses_items(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>OpenAI Blog</title>
            <item>
              <title>New model release</title>
              <link>https://example.com/new-model</link>
              <pubDate>Wed, 10 Apr 2026 12:00:00 GMT</pubDate>
              <description>Model update</description>
            </item>
          </channel>
        </rss>"""

        collector = RSSCollector(source_name="OpenAI Blog", category="news")
        items = collector.parse_feed(xml, feed_url="https://example.com/rss")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "New model release")
        self.assertEqual(items[0].url, "https://example.com/new-model")
        self.assertEqual(items[0].source, "OpenAI Blog")
        self.assertEqual(items[0].category, "news")
        self.assertEqual(items[0].dedupe_key, "https://example.com/new-model")

    def test_github_trending_collector_parses_repository_metadata(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/openai/gpt-researcher"> openai / gpt-researcher </a>
          </h2>
          <p class="col-9 color-fg-muted my-1 pr-4">Agentic research assistant.</p>
          <span class="d-inline-block float-sm-right">1,234 stars today</span>
        </article>
        """

        collector = GitHubTrendingCollector()
        items = collector.parse_trending(html, page_url="https://github.com/trending")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "openai / gpt-researcher")
        self.assertEqual(items[0].url, "https://github.com/openai/gpt-researcher")
        self.assertEqual(items[0].metadata["stars_growth"], 1234)
        self.assertEqual(items[0].category, "github")
        expected_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(items[0].published_at, expected_day)

    def test_github_trending_collector_ignores_non_repo_links(self) -> None:
        html = """
        <article class="Box-row">
          <div>
            <a href="/login?return_to=%2Fopenai%2Fgpt-researcher">Star</a>
          </div>
          <h2 class="h3 lh-condensed">
            <a href="/openai/gpt-researcher"> openai / gpt-researcher </a>
          </h2>
          <p>Agentic research assistant.</p>
          <span class="d-inline-block float-sm-right">1,234 stars today</span>
        </article>
        """

        collector = GitHubTrendingCollector()
        items = collector.parse_trending(html, page_url="https://github.com/trending")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://github.com/openai/gpt-researcher")
        self.assertEqual(items[0].dedupe_key, "github:openai/gpt-researcher")

    def test_github_trending_collector_parses_anchor_when_href_is_not_first_attribute(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a data-hydro-click="x" href="/openai/gpt-researcher" data-view-component="true" class="Link">
              <svg></svg>
              <span class="text-normal">openai /</span>
              gpt-researcher
            </a>
          </h2>
          <p>LLM agent for autonomous research and report generation.</p>
          <span class="d-inline-block float-sm-right">1,234 stars today</span>
        </article>
        """

        collector = GitHubTrendingCollector()
        items = collector.parse_trending(html, page_url="https://github.com/trending")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "openai / gpt-researcher")
        self.assertEqual(items[0].url, "https://github.com/openai/gpt-researcher")
        self.assertEqual(items[0].metadata["stars_growth"], 1234)

    def test_github_trending_collector_filters_non_ai_projects(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/microsoft/markitdown"> microsoft / markitdown </a>
          </h2>
          <p>Python tool for converting files and office documents to Markdown.</p>
          <span class="d-inline-block float-sm-right">1,234 stars today</span>
        </article>
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/openai/gpt-researcher"> openai / gpt-researcher </a>
          </h2>
          <p>LLM agent for autonomous research and report generation.</p>
          <span class="d-inline-block float-sm-right">2,345 stars today</span>
        </article>
        """

        collector = GitHubTrendingCollector()
        items = collector.parse_trending(html, page_url="https://github.com/trending")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://github.com/openai/gpt-researcher")

    def test_github_trending_collector_strips_star_noise_from_summary(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/coleam00/Archon"> coleam00 / Archon </a>
          </h2>
          <p>Star coleam00 / Archon The first open-source harness builder for AI coding.</p>
          <span class="d-inline-block float-sm-right">756 stars today</span>
        </article>
        """

        collector = GitHubTrendingCollector()
        items = collector.parse_trending(html, page_url="https://github.com/trending")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].summary, "The first open-source harness builder for AI coding.")


if __name__ == "__main__":
    unittest.main()
