from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_digest.defaults import build_default_runner
from ai_digest.settings import AppSettings, ArkCredentials, WeChatCredentials


class DefaultRunnerArkTest(unittest.TestCase):
    def test_build_default_runner_uses_ark_writer_when_settings_include_ark(self) -> None:
        settings = AppSettings(
            wechat=WeChatCredentials(appid="wx-appid", appsecret="wx-secret"),
            ark=ArkCredentials(
                api_key="ark-key",
                base_url="https://ark.example.com/api/v3",
                model="ep-model",
                timeout_seconds=30,
            ),
            dry_run=False,
            draft_mode=True,
            llm_enabled=True,
        )

        with patch("ai_digest.defaults.build_default_publisher", return_value=object()):
            runner = build_default_runner(settings=settings)

        self.assertIsNotNone(runner.writer)


if __name__ == "__main__":
    unittest.main()
