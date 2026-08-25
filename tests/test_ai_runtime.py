import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
import providers


class FakeAdapter(providers.StructuredProvider):
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return {"project": "demo", "kind": "ui", "summary": "ok",
                "deletable": False, "confidence": .9}


class AIRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "screen.png").write_bytes(b"not-an-image")
        self.conn = engine.db(sqlite3.connect(":memory:"))
        self.db = patch.object(engine, "db", return_value=self.conn)
        self.db.start()

    def tearDown(self):
        self.db.stop()
        self.conn.close()
        self.temp.cleanup()

    def plan(self, method, provider="local", reason=None):
        config = providers.ProviderConfig(provider, "model", "key")
        status = providers.ExecutionStatus(provider, method, "model",
                                           method != providers.ExecutionMethod.LOCAL, reason)
        return providers.ExecutionPlan(method, config, status)

    def scan_with(self, plan, adapter):
        with patch.object(engine.providers, "resolve_execution", return_value=plan), \
             patch.object(engine.providers, "create_provider", return_value=adapter), \
             patch.object(engine, "ocr", return_value="text"):
            return engine.scan_images(self.root, provider="openai", model="model",
                                      api_consent=True)

    def test_schema_settings_consent_and_catalog_cache_round_trip(self):
        engine.save_ai_settings({"mode": "auto", "model": "gpt"}, conn=self.conn)
        engine.set_api_consent("openai", with_image=True, allowed=True, conn=self.conn)
        engine.save_model_catalog("openai", "api", ["gpt", "mini"], conn=self.conn)
        self.assertEqual(engine.load_ai_settings(conn=self.conn)["model"], "gpt")
        self.assertTrue(engine.has_api_consent("openai", with_image=True, conn=self.conn))
        catalog = engine.load_model_catalog("openai", "api", conn=self.conn)
        self.assertEqual(catalog["models"], ["gpt", "mini"])
        self.assertFalse(catalog["stale"])

    def test_cli_failure_retries_local_and_reports_actual_execution(self):
        result = self.scan_with(self.plan(providers.ExecutionMethod.CODEX_CLI, "codex"),
                                FakeAdapter(providers.ExecutionTimeout("late")))
        self.assertEqual(result.actual_provider, "local")
        self.assertEqual(result.actual_method, providers.ExecutionMethod.LOCAL)
        self.assertTrue(result.fallback_reason)
        self.assertTrue(result.external_transfer)
        self.assertEqual(result.new, 1)

    def test_consented_api_failure_only_retries_local(self):
        adapter = FakeAdapter(RuntimeError("rate limit"))
        result = self.scan_with(self.plan(providers.ExecutionMethod.API, "openai"), adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(result.actual_provider, "local")
        self.assertIn("rate", result.fallback_reason.lower())

    def test_unconsented_api_plan_is_local_and_never_creates_adapter(self):
        result = self.scan_with(self.plan(providers.ExecutionMethod.LOCAL, reason="no consent"), None)
        self.assertEqual(result.actual_provider, "local")
        self.assertFalse(result.external_transfer)
        self.assertEqual(result.new, 1)

    def test_error_classes_are_safe_and_distinct(self):
        self.assertEqual(engine.classify_provider_error(providers.ExecutionTimeout("x")), "timeout")
        self.assertEqual(engine.classify_provider_error(providers.AuthenticationError("x")), "authentication")
        self.assertEqual(engine.classify_provider_error(RuntimeError("network unreachable")), "network")
        self.assertEqual(engine.classify_provider_error(RuntimeError("rate limit")), "rate_limit")

    def test_cached_images_skip_but_consolidation_preserves_execution_state(self):
        path = self.root / "screen.png"
        sha = engine.file_sha(path)
        self.conn.execute("INSERT INTO images(path, sha) VALUES(?, ?)", (str(path), sha))
        self.conn.commit()
        result = self.scan_with(self.plan(providers.ExecutionMethod.LOCAL), None)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.actual_provider, "local")
        self.assertIsNone(result.consolidate_error)
