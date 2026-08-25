"""Server-free contract checks for the AI controls in the NiceGUI app."""
from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1] / "app.py"


class AppAiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")

    def test_offers_the_five_execution_modes(self):
        for mode in ('"auto"', '"local"', '"cli"', '"api"', '"direct"'):
            self.assertIn(mode, self.source)
        self.assertIn("ANALYSIS_MODE_OPTIONS", self.source)

    def test_refresh_explains_the_selected_route_and_catalog(self):
        for marker in (
            "providers.probe_codex_cli",
            "providers.resolve_execution",
            "actual_provider",
            "actual_method",
            "engine.load_model_catalog",
            "외부 전송",
            "캐시",
        ):
            self.assertIn(marker, self.source)

    def test_api_transfer_requires_scoped_consent_dialog(self):
        self.assertIn("API 전송 동의", self.source)
        self.assertIn("engine.set_api_consent", self.source)
        self.assertIn("with_image=img_sw.value", self.source)
        self.assertIn("await request_api_consent()", self.source)

    def test_credential_state_is_displayed_without_key_value(self):
        self.assertIn("engine.keychain_status", self.source)
        self.assertIn("Keychain/환경변수 상태", self.source)
        self.assertNotIn("ui.input(\"API Key", self.source)

    def test_saved_model_disappearance_needs_confirmation(self):
        self.assertIn("저장된 모델을 찾을 수 없습니다", self.source)
        self.assertIn("confirm_missing_saved_model", self.source)

    def test_automatic_anthropic_model_is_used_for_api_consent_preflight(self):
        self.assertIn('engine.DEFAULT_MODEL if provider == "anthropic" and mode not in {"auto", "cli"}',
                      self.source)


if __name__ == "__main__":
    unittest.main()
