import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_provider
import providers
import engine


SCHEMA = {"type": "object", "properties": {"project": {"type": "string"}},
          "required": ["project"], "additionalProperties": False}


class CLIProviderTests(unittest.TestCase):
    def test_scan_through_cli_process_stores_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "fake-claude"
            tag = {"project": "demo", "kind": "ui", "summary": "테스트 화면",
                   "deletable": False, "confidence": 0.8}
            executable.write_text(
                f"#!{sys.executable}\nimport json,sys\n"
                "assert '--tools' in sys.argv and sys.argv[sys.argv.index('--tools')+1] == ''\n"
                "assert 'OCR' in sys.stdin.read()\n"
                f"print({json.dumps({'structured_output': tag})!r})\n"
            )
            executable.chmod(0o700)
            image = root / "screen.png"
            image.write_bytes(b"test screenshot")
            with patch.object(cli_provider, "cli_executable", return_value=str(executable)), \
                 patch.object(engine, "STATE_DIR", root), \
                 patch.object(engine, "DB_PATH", root / "cache.db"), \
                 patch.object(engine, "ocr", return_value="OCR test"):
                result = engine.scan_images(root, provider="claude_cli", consolidate=False)
                self.assertEqual((result.new, result.errors), (1, []))
                self.assertEqual(engine.list_groups()["demo"][0]["summary"], "테스트 화면")

    def test_cli_configuration_never_uses_api_environment(self):
        config = providers.resolve_config("codex_cli", env={
            "SHOTSORT_AI_MODEL": "api-model", "OPENAI_API_KEY": "private",
            "SHOTSORT_AI_BASE_URL": "https://api.example.com"})
        self.assertEqual(config, providers.ProviderConfig("codex_cli"))
        providers.validate_config(config)

    @patch("cli_provider.cli_executable", return_value="/test/claude")
    @patch("cli_provider.subprocess.run")
    def test_login_status_and_recovery(self, run, executable):
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps({"loggedIn": True}))
        self.assertTrue(cli_provider.check_cli_login("claude_cli")[0])
        self.assertEqual(run.call_args.args[0][1:], ["auth", "status", "--json"])
        run.return_value = SimpleNamespace(returncode=1, stdout='{"loggedIn":false}')
        ready, message = cli_provider.check_cli_login("claude_cli")
        self.assertFalse(ready)
        self.assertIn("claude auth login", message)
        run.side_effect = subprocess.TimeoutExpired("claude", 15)
        self.assertFalse(cli_provider.check_cli_login("claude_cli")[0])

    @patch("cli_provider.cli_executable", return_value=None)
    def test_missing_cli_does_not_run_anything(self, executable):
        self.assertFalse(cli_provider.check_cli_login("codex_cli")[0])
        with self.assertRaisesRegex(ValueError, "설치"):
            providers.create_provider(providers.ProviderConfig("codex_cli"))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "private", "CODEX_API_KEY": "private"})
    @patch("cli_provider.cli_executable", return_value="/test/claude")
    @patch("cli_provider.subprocess.run")
    def test_claude_structured_response_and_no_tools(self, run, executable):
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps({
            "structured_output": {"project": "example"}}))
        adapter = providers.create_provider(providers.ProviderConfig("claude_cli", "chosen-model"))
        self.assertEqual(adapter.generate_json(system="classify", prompt="OCR text", schema=SCHEMA),
                         {"project": "example"})
        args = run.call_args.args[0]
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertIn("--safe-mode", args)
        self.assertIn("--no-session-persistence", args)
        self.assertEqual(args[args.index("--model") + 1], "chosen-model")
        self.assertEqual(run.call_args.kwargs["input"], "OCR text")
        self.assertNotIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
        self.assertNotIn("CODEX_API_KEY", run.call_args.kwargs["env"])
        self.assertFalse(Path(run.call_args.kwargs["cwd"]).exists())

    @patch("cli_provider.cli_executable", return_value="/test/codex")
    @patch("cli_provider.subprocess.run")
    def test_codex_uses_stdin_schema_readonly_and_final_output(self, run, executable):
        def response(args, **kwargs):
            self.assertEqual(args[-1], "-")
            self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
            self.assertIn("shell_tool", args)
            self.assertIn("--ignore-user-config", args)
            self.assertEqual(json.loads(Path(args[args.index("--output-schema") + 1]).read_text()), SCHEMA)
            Path(args[args.index("--output-last-message") + 1]).write_text('{"project":"codex"}')
            return SimpleNamespace(returncode=0)
        run.side_effect = response
        adapter = providers.create_provider(providers.ProviderConfig("codex_cli"))
        self.assertEqual(adapter.generate_json(system="classify", prompt="text", schema=SCHEMA),
                         {"project": "codex"})

    @patch("cli_provider.cli_executable", return_value="/test/claude")
    @patch("cli_provider.subprocess.run")
    def test_error_output_is_not_exposed_and_images_are_rejected(self, run, executable):
        adapter = providers.create_provider(providers.ProviderConfig("claude_cli"))
        with self.assertRaisesRegex(ValueError, "OCR"):
            adapter.generate_json(system="", prompt="", schema=SCHEMA, image_b64="private")
        run.assert_not_called()
        run.return_value = SimpleNamespace(returncode=1, stdout="private", stderr="private")
        with self.assertRaises(RuntimeError) as caught:
            adapter.generate_json(system="", prompt="", schema=SCHEMA)
        self.assertNotIn("private", str(caught.exception))
        run.return_value = SimpleNamespace(returncode=0, stdout="malformed")
        with self.assertRaisesRegex(RuntimeError, "응답"):
            adapter.generate_json(system="", prompt="", schema=SCHEMA)
        run.side_effect = subprocess.TimeoutExpired("claude", 120)
        with self.assertRaisesRegex(RuntimeError, "120초"):
            adapter.generate_json(system="", prompt="", schema=SCHEMA)
