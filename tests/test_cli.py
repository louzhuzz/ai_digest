from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from ai_digest.cli import main


class FakeRunner:
    def run(self):
        class Result:
            status = "composed"
            error = None
            items_count = 4
            publisher_draft_id = None
            markdown = "# AI 每日新闻速递\n"

        return Result()


class CliTest(unittest.TestCase):
    def test_main_prints_markdown_in_dry_run_mode(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["--dry-run"], runner=FakeRunner())

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("状态: composed", output)
        self.assertIn("# AI 每日新闻速递", output)

    def test_main_prints_error_when_runner_fails(self) -> None:
        class FailedRunner:
            def run(self):
                class Result:
                    status = "failed"
                    error = "WECHAT_THUMB_MEDIA_ID is required for draft publishing"
                    items_count = 0
                    publisher_draft_id = None
                    markdown = None

                return Result()

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["--publish"], runner=FailedRunner())

        output = buffer.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("WECHAT_THUMB_MEDIA_ID", output)

    def test_main_does_not_print_markdown_after_publish(self) -> None:
        class PublishedRunner:
            def run(self):
                class Result:
                    status = "published"
                    error = None
                    items_count = 5
                    publisher_draft_id = "draft-123"
                    markdown = "# AI 每日新闻速递\n\n正文"

                return Result()

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["--publish"], runner=PublishedRunner())

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("状态: published", output)
        self.assertIn("草稿ID: draft-123", output)
        self.assertNotIn("# AI 每日新闻速递", output)


if __name__ == "__main__":
    unittest.main()
