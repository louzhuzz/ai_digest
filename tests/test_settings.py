from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_digest.settings import load_settings


class LoadSettingsTest(unittest.TestCase):
    def test_loads_ark_settings_from_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ARK_API_KEY": "ark-key",
                "ARK_BASE_URL": "https://ark.example.com/api/v3",
                "ARK_MODEL": "ep-model",
                "ARK_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.ark.api_key, "ark-key")
        self.assertEqual(settings.ark.base_url, "https://ark.example.com/api/v3")
        self.assertEqual(settings.ark.model, "ep-model")
        self.assertEqual(settings.ark.timeout_seconds, 45)

    def test_loads_wechat_credentials_from_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "WECHAT_APPID": "wx-test-appid",
                "WECHAT_APPSECRET": "secret-value",
                "WECHAT_DRY_RUN": "0",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.wechat.appid, "wx-test-appid")
        self.assertEqual(settings.wechat.appsecret, "secret-value")
        self.assertEqual(settings.wechat.thumb_media_id, "")
        self.assertFalse(settings.dry_run)
        self.assertTrue(settings.draft_mode)

    def test_defaults_to_dry_run_without_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True), patch("pathlib.Path.cwd", return_value=Path(tmpdir)):
                settings = load_settings()

        self.assertIsNone(settings.wechat)
        self.assertTrue(settings.dry_run)
        self.assertFalse(settings.draft_mode)
        self.assertEqual(settings.state_db_path, Path("data/state.db"))

    def test_loads_state_db_path_from_environment(self) -> None:
        with patch.dict("os.environ", {"AI_DIGEST_STATE_DB": "/tmp/custom-state.db"}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.state_db_path, Path("/tmp/custom-state.db"))

    def test_loads_dotenv_file_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "WECHAT_APPID=wx-from-file\nWECHAT_APPSECRET=file-secret\nWECHAT_DRY_RUN=0\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True), patch("pathlib.Path.cwd", return_value=Path(tmpdir)):
                settings = load_settings()

        self.assertEqual(settings.wechat.appid, "wx-from-file")
        self.assertEqual(settings.wechat.appsecret, "file-secret")
        self.assertEqual(settings.wechat.thumb_media_id, "")
        self.assertFalse(settings.dry_run)
        self.assertTrue(settings.draft_mode)

    def test_loads_thumb_media_id_when_configured(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "WECHAT_APPID": "wx-test-appid",
                "WECHAT_APPSECRET": "secret-value",
                "WECHAT_THUMB_MEDIA_ID": "thumb-123",
                "WECHAT_DRY_RUN": "0",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.wechat.thumb_media_id, "thumb-123")

    def test_publish_mode_can_exist_without_ark_but_runtime_will_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                "os.environ",
                {
                    "WECHAT_APPID": "wx-test-appid",
                    "WECHAT_APPSECRET": "secret-value",
                    "WECHAT_DRY_RUN": "0",
                },
                clear=True,
            ), patch("pathlib.Path.cwd", return_value=Path(tmpdir)):
                settings = load_settings()

        self.assertTrue(settings.draft_mode)
        self.assertIsNone(settings.ark)


if __name__ == "__main__":
    unittest.main()
