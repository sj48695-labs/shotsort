"""Server-free contract checks for the AI controls in the NiceGUI app."""
import ast
from types import SimpleNamespace

import providers
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
            "providers.probe_cli_capabilities",
            "Claude CLI",
            "providers.resolve_execution",
            "actual_provider",
            "actual_method",
            "engine.refresh_model_catalog",
            "외부 전송",
            "캐시",
            "마지막 갱신",
        ):
            self.assertIn(marker, self.source)

    def test_api_transfer_requires_scoped_consent_dialog(self):
        self.assertIn("API 전송 동의", self.source)
        self.assertIn("engine.set_api_consent", self.source)
        self.assertIn("with_image=selected_with_image()", self.source)
        self.assertIn("await request_api_consent()", self.source)

    def test_credential_state_is_displayed_without_key_value(self):
        self.assertIn("engine.keychain_status", self.source)
        self.assertIn("Keychain/환경변수 상태", self.source)
        self.assertNotIn("ui.input(\"API Key", self.source)

    def test_direct_mode_uses_only_approved_settings(self):
        functions = [node for node in ast.walk(ast.parse(self.source))
                     if isinstance(node, ast.FunctionDef)
                     and node.name in {"selected_config", "selected_with_image", "selected_model"}]
        approved = providers.ProviderConfig("codex_cli", "approved-model")
        context = {
            "mode_in": SimpleNamespace(value="direct"),
            "model_settings": SimpleNamespace(config=approved, with_image=False),
            "provider_in": SimpleNamespace(value="openai"),
            "model_in": SimpleNamespace(value="draft-model"),
            "model_select": SimpleNamespace(value="__auto__"),
            "img_sw": SimpleNamespace(value=True),
            "providers": providers,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(APP), "exec"), context)
        self.assertIs(context["selected_config"](), approved)
        self.assertFalse(context["selected_with_image"]())
        context["mode_in"].value = "api"
        self.assertEqual(context["selected_config"]().provider, "openai")
        self.assertEqual(context["selected_config"]().model, "draft-model")
        self.assertTrue(context["selected_with_image"]())

    def test_saved_model_disappearance_needs_confirmation(self):
        self.assertIn("저장된 모델을 찾을 수 없습니다", self.source)
        self.assertIn("confirm_missing_saved_model", self.source)

    def test_saved_model_is_restored_to_the_input(self):
        self.assertIn('value=ai_settings.get("analysis_model", "")', self.source)

    def test_automatic_anthropic_model_is_used_for_api_consent_preflight(self):
        self.assertIn('engine.DEFAULT_MODEL if provider_in.value == "anthropic"', self.source)
        self.assertIn('mode_in.value not in {"auto", "cli"}', self.source)


if __name__ == "__main__":
    unittest.main()
