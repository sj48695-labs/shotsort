import json
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
