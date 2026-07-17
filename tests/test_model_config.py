import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literary_engineering_workbench.model_config import (
    default_config,
    get_model_settings,
    load_config,
    redacted_effective_config,
    resolve_model_provider,
    save_config,
)


class ModelConfigTests(unittest.TestCase):
    def test_default_config_is_created_at_config_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            with patch.dict("os.environ", {"LEW_CONFIG_PATH": str(path)}, clear=False):
                cfg = load_config()
                self.assertTrue(path.exists())
                self.assertEqual(cfg["active_profile"], "deepseek")
                self.assertEqual(cfg["profiles"]["deepseek"]["api_key_env"], "DEEPSEEK_API_KEY")

    def test_settings_use_profile_and_environment_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = default_config()
            cfg["profiles"]["deepseek"]["api_base"] = "https://example.test/v1"
            cfg["profiles"]["deepseek"]["model"] = "example-model"
            save_config(cfg, path=path)
            with patch.dict(
                "os.environ",
                {
                    "LEW_CONFIG_PATH": str(path),
                    "DEEPSEEK_API_KEY": "secret-value",
                    "LEW_MODEL_TEMPERATURE": "0.25",
                },
                clear=False,
            ):
                settings = get_model_settings()
                self.assertEqual(settings.api_base, "https://example.test/v1")
                self.assertEqual(settings.model, "example-model")
                self.assertEqual(settings.api_key, "secret-value")
                self.assertEqual(settings.temperature, 0.25)
                effective = redacted_effective_config()
                self.assertTrue(effective["api_key_available"])
                self.assertNotIn("secret-value", str(effective))

    def test_settings_can_use_saved_profile_api_key_without_leaking_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = default_config()
            cfg["profiles"]["deepseek"]["api_key"] = "stored-secret"
            save_config(cfg, path=path)
            with patch.dict(
                "os.environ",
                {
                    "LEW_CONFIG_PATH": str(path),
                    "DEEPSEEK_API_KEY": "",
                    "LEW_MODEL_API_KEY": "",
                },
                clear=False,
            ):
                settings = get_model_settings()
                self.assertEqual(settings.api_key, "stored-secret")
                effective = redacted_effective_config()
                self.assertTrue(effective["api_key_available"])
                self.assertTrue(effective["profiles"]["deepseek"]["api_key_set"])
                self.assertNotIn("stored-secret", str(effective))

    def test_auto_provider_resolves_only_when_real_llm_is_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = default_config()
            cfg["profiles"]["deepseek"]["api_key"] = "stored-secret"
            save_config(cfg, path=path)
            with patch.dict(
                "os.environ",
                {
                    "LEW_CONFIG_PATH": str(path),
                    "DEEPSEEK_API_KEY": "",
                    "LEW_MODEL_API_KEY": "",
                },
                clear=False,
            ):
                self.assertEqual(resolve_model_provider("auto", purpose="test"), "http-chat")


if __name__ == "__main__":
    unittest.main()
