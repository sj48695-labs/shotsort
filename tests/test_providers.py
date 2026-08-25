import json
import subprocess
import unittest
from types import SimpleNamespace

import providers


class ProviderConfigTest(unittest.TestCase):
    def test_local_is_safe_default(self):
        self.assertEqual(providers.resolve_config(env={}), providers.ProviderConfig("local"))

    def test_aliases_and_environment_precedence(self):
        cfg = providers.resolve_config("codex", env={
            "SHOTSORT_AI_MODEL": "chosen-model", "OPENAI_MODEL": "fallback",
            "OPENAI_API_KEY": "secret",
        })
        self.assertEqual((cfg.provider, cfg.model, cfg.api_key),
                         ("openai", "chosen-model", "secret"))
        self.assertEqual(providers.resolve_config("grok", env={"XAI_MODEL": "g",
                         "XAI_API_KEY": "x"}).provider, "xai")

    def test_remote_requires_explicit_model_and_key(self):
        with self.assertRaisesRegex(ValueError, "모델"):
            providers.validate_config(providers.ProviderConfig("openai", api_key="x"))
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            providers.validate_config(providers.ProviderConfig("openai", model="m"))


class ExecutionPolicyTest(unittest.TestCase):
    def test_auto_prefers_verified_codex_cli_over_consented_api(self):
        capability = providers.ProviderCapability.codex_cli(
            available=True, logged_in=True, supports_images=True,
            supports_structured_output=True)
        plan = providers.resolve_execution(
            providers.AnalysisMode.AUTO,
            providers.ProviderConfig("openai", "gpt-test", "secret"),
            api_consent=True, cli_capability=capability)
        self.assertEqual(plan.method, providers.ExecutionMethod.CODEX_CLI)
        self.assertEqual(plan.status.provider, "codex")
        self.assertTrue(plan.status.external_transfer)

    def test_auto_uses_only_consented_api_then_local(self):
        config = providers.ProviderConfig("openai", "gpt-test", "secret")
        unavailable = providers.ProviderCapability.codex_cli(
            available=False, reason="not installed")
        unconsented = providers.resolve_execution(
            "auto", config, api_consent=False, cli_capability=unavailable)
        self.assertEqual(unconsented.method, providers.ExecutionMethod.LOCAL)
        self.assertIn("동의", unconsented.status.fallback_reason)

        consented = providers.resolve_execution(
            "auto", config, api_consent=True, cli_capability=unavailable)
        self.assertEqual(consented.method, providers.ExecutionMethod.API)
        self.assertEqual(consented.status.provider, "openai")

    def test_api_mode_never_selects_a_different_paid_provider(self):
        plan = providers.resolve_execution(
            "api", providers.ProviderConfig("anthropic", "claude-test", "key"),
            api_consent=False)
        self.assertEqual(plan.method, providers.ExecutionMethod.LOCAL)
        self.assertNotIn("openai", plan.status.provider)


class CodexCliProviderTest(unittest.TestCase):
    def test_capability_probe_requires_installed_logged_in_image_and_schema(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            if command[1:] == ["exec", "--help"]:
                return SimpleNamespace(returncode=0, stdout="--image FILE --output-schema FILE", stderr="")
            return SimpleNamespace(returncode=0, stdout="Logged in", stderr="")

        capability = providers.probe_codex_cli(runner=runner)
        self.assertTrue(capability.ready)
        self.assertEqual(calls[0][0], ["codex", "exec", "--help"])
        self.assertEqual(calls[1][0], ["codex", "login", "status"])

    def test_capability_probe_rejects_cli_without_image_or_schema_flags(self):
        def runner(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout="--output-schema FILE", stderr="")

        capability = providers.probe_codex_cli(runner=runner)
        self.assertFalse(capability.ready)
        self.assertIn("이미지 입력", capability.reason)

    def test_cli_runs_read_only_ephemeral_with_image_schema_and_parses_json(self):
        seen = {}
        def runner(command, **kwargs):
            seen.update(command=command, kwargs=kwargs)
            return SimpleNamespace(returncode=0, stdout='{"project": "act"}', stderr="")

        adapter = providers.CodexCliProvider(providers.ProviderConfig("codex", "gpt-test"),
                                             runner=runner, timeout=12)
        result = adapter.generate_json(system="system", prompt="classify", schema={"type": "object"},
                                       image_b64="aGVsbG8=")
        self.assertEqual(result, {"project": "act"})
        self.assertIn("--sandbox", seen["command"])
        self.assertIn("read-only", seen["command"])
        self.assertIn("--ephemeral", seen["command"])
        self.assertIn("--image", seen["command"])
        self.assertIn("--output-schema", seen["command"])
        self.assertEqual(seen["kwargs"]["timeout"], 12)

    def test_cli_timeout_and_bad_json_are_classified_and_masked(self):
        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], stderr="Bearer abcdef")
        adapter = providers.CodexCliProvider(providers.ProviderConfig("codex"), runner=timeout_runner)
        with self.assertRaisesRegex(providers.ExecutionTimeout, "Bearer \\*\\*\\*"):
            adapter.generate_json(system="s", prompt="p", schema={"type": "object"})

        def malformed_runner(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout="not-json", stderr="sk-secret-token")
        adapter = providers.CodexCliProvider(providers.ProviderConfig("codex"), runner=malformed_runner)
        with self.assertRaises(providers.StructuredOutputError) as raised:
            adapter.generate_json(system="s", prompt="p", schema={"type": "object"})
        self.assertNotIn("sk-secret-token", str(raised.exception))

    def test_mask_secret_hides_keys_authorization_and_cli_stderr(self):
        message = "OPENAI_API_KEY=sk-secret-token Bearer abcdefghijkl -- sk-another-secret"
        masked = providers.mask_secret(message)
        self.assertNotIn("secret-token", masked)
        self.assertNotIn("abcdefghijkl", masked)
        self.assertIn("OPENAI_API_KEY=***", masked)


class ProviderCallTest(unittest.TestCase):
    def test_anthropic_structured_call_with_image(self):
        seen = {}
        class Messages:
            def create(self, **kwargs):
                seen.update(kwargs)
                return SimpleNamespace(content=[SimpleNamespace(
                    type="text", text=json.dumps({"project": "act"}))])
        adapter = providers.AnthropicProvider(
            providers.ProviderConfig("anthropic", "model-a", "key"),
            SimpleNamespace(messages=Messages()))
        result = adapter.generate_json(system="sys", prompt="hello", schema={"type": "object"},
                                       image_b64="abc")
        self.assertEqual(result, {"project": "act"})
        self.assertEqual(seen["model"], "model-a")
        self.assertEqual(seen["messages"][0]["content"][0]["type"], "image")

    def test_openai_responses_call(self):
        seen = {}
        class Responses:
            def create(self, **kwargs):
                seen.update(kwargs)
                return SimpleNamespace(output_text=json.dumps({"group": "act"}))
        adapter = providers.OpenAIProvider(
            providers.ProviderConfig("openai", "model-o", "key"),
            SimpleNamespace(responses=Responses()))
        result = adapter.generate_json(system="sys", prompt="hello", schema={"type": "object"})
        self.assertEqual(result, {"group": "act"})
        self.assertEqual(seen["model"], "model-o")
        self.assertEqual(seen["text"]["format"]["type"], "json_schema")

    def test_xai_compatible_chat_call(self):
        seen = {}
        class Completions:
            def create(self, **kwargs):
                seen.update(kwargs)
                message = SimpleNamespace(content=json.dumps({"group": "act"}))
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
        adapter = providers.XAIProvider(
            providers.ProviderConfig("xai", "model-x", "key", "https://api.x.ai/v1"),
            client)
        self.assertEqual(adapter.generate_json(system="sys", prompt="hello",
                         schema={"type": "object"}), {"group": "act"})
        self.assertEqual(seen["response_format"]["type"], "json_schema")


if __name__ == "__main__":
    unittest.main()
