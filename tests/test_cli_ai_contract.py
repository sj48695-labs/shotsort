import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cli
import providers


class CliAiContractTest(unittest.TestCase):
    def parse(self, *argv):
        return cli.build_parser().parse_args(["scan", *argv])

    def test_parser_accepts_new_modes_and_legacy_vendor_shorthands(self):
        for provider in ("auto", "cli", "api", "direct", "local", "anthropic", "openai", "xai"):
            self.assertEqual(self.parse("--provider", provider).provider, provider)
        self.assertTrue(self.parse("--provider", "api", "--allow-api-transfer").allow_api_transfer)
        self.assertEqual(self.parse("--provider", "direct", "--direct-provider", "openai").direct_provider,
                         "openai")

    def test_api_without_explicit_transfer_consent_stays_local_and_explains_why(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.parse(directory, "--provider", "api", "--direct-provider", "openai", "--model", "m")
            result = SimpleNamespace(total=0, new=0, skipped=0, consolidate_error=None,
                                     actual_provider="local", actual_method=providers.ExecutionMethod.LOCAL,
                                     actual_model=None, external_transfer=False, catalog_from_cache=True,
                                     fallback_reason="API 외부 전송 동의가 없어 로컬 분석을 사용합니다")
            with patch.object(cli.engine, "scan_images", return_value=result) as scan, \
                 patch.object(cli.engine, "set_api_consent") as save:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    cli.cmd_scan(args)
        self.assertFalse(scan.call_args.kwargs["api_consent"])
        self.assertEqual(scan.call_args.kwargs["analysis_mode"], "api")
        save.assert_not_called()
        self.assertIn("fallback=API 외부 전송 동의", output.getvalue())

    def test_allow_api_transfer_saves_scoped_consent_and_passes_it_to_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.parse(directory, "--provider", "api", "--direct-provider", "openai", "--model", "m",
                              "--with-image", "--allow-api-transfer")
            result = SimpleNamespace(total=0, new=0, skipped=0, consolidate_error=None,
                                     actual_provider="openai", actual_method=providers.ExecutionMethod.API,
                                     actual_model="m", external_transfer=True, catalog_from_cache=False,
                                     fallback_reason=None)
            with patch.object(cli.engine, "scan_images", return_value=result) as scan, \
                 patch.object(cli.engine, "set_api_consent") as save:
                cli.cmd_scan(args)
        save.assert_called_once_with("openai", with_image=True, allowed=True)
        self.assertTrue(scan.call_args.kwargs["api_consent"])

    def test_auto_allow_api_transfer_also_saves_scoped_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.parse(directory, "--provider", "auto", "--allow-api-transfer")
            result = SimpleNamespace(total=0, new=0, skipped=0, consolidate_error=None,
                                     actual_provider="local", actual_method=providers.ExecutionMethod.LOCAL,
                                     actual_model=None, external_transfer=False, catalog_from_cache=False,
                                     fallback_reason=None)
            with patch.object(cli.engine, "scan_images", return_value=result), \
                 patch.object(cli.engine, "set_api_consent") as save:
                cli.cmd_scan(args)
        save.assert_called_once_with("anthropic", with_image=False, allowed=True)

    def test_auto_and_legacy_shorthand_keep_modes_for_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            result = SimpleNamespace(total=0, new=0, skipped=0, consolidate_error=None,
                                     actual_provider="local", actual_method=providers.ExecutionMethod.LOCAL,
                                     actual_model=None, external_transfer=False, catalog_from_cache=False,
                                     fallback_reason=None)
            with patch.object(cli.engine, "scan_images", return_value=result) as scan:
                cli.cmd_scan(self.parse(directory, "--provider", "auto"))
                self.assertEqual(scan.call_args.kwargs["analysis_mode"], "auto")
                cli.cmd_scan(self.parse(directory, "--provider", "openai", "--model", "m"))
                self.assertEqual(scan.call_args.kwargs["analysis_mode"], "direct")
                self.assertEqual(scan.call_args.kwargs["provider"], "openai")

    def test_scan_help_describes_claude_text_fallback(self):
        scan_parser = cli.build_parser()._subparsers._group_actions[0].choices["scan"]
        self.assertIn("Claude CLI(텍스트)", scan_parser.format_help())

    def test_status_output_uses_actual_result_and_masks_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.parse(directory, "--provider", "auto")
            result = SimpleNamespace(total=0, new=0, skipped=0, consolidate_error=None,
                                     actual_provider="local", actual_method=providers.ExecutionMethod.LOCAL,
                                     actual_model=None, external_transfer=False, catalog_from_cache=True,
                                     fallback_reason="CLI stderr: Bearer abcdef sk-secret-token")
            with patch.object(cli.engine, "scan_images", return_value=result):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    cli.cmd_scan(args)
        text = output.getvalue()
        self.assertIn("provider=local", text)
        self.assertIn("method=local", text)
        self.assertIn("external_transfer=no", text)
        self.assertIn("catalog=cache", text)
        self.assertNotIn("abcdef", text)
        self.assertNotIn("secret-token", text)


if __name__ == "__main__":
    unittest.main()

class CliEngineIntegrationTest(unittest.TestCase):
    def test_real_scan_resolver_adapter_database_and_preflight_order(self):
        import json
        import sqlite3
        import engine
        scenarios = (("auto", "codex", False, False), ("auto", "claude", False, False),
                     ("auto", "claude", True, False), ("api", None, False, False),
                     ("api", None, False, True), ("local", "codex", False, True))
        for mode, vendor, image, consent in scenarios:
            with self.subTest(mode=mode, vendor=vendor, image=image, consent=consent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "screen.png").write_bytes(b"image")
                conn = engine.db(sqlite3.connect(root / "state.db"))
                self.addCleanup(conn.close)
                capabilities = {
                    "codex": providers.ProviderCapability.codex_cli(available=vendor == "codex", logged_in=True),
                    "claude": providers.ProviderCapability.claude_cli(available=vendor == "claude", logged_in=True)}
                argv = ["scan", directory, "--provider", mode, "--direct-provider", "openai", "--model", "test-model"]
                if image:
                    argv.append("--with-image")
                if consent:
                    argv.append("--allow-api-transfer")
                args = cli.build_parser().parse_args(argv)
                output = io.StringIO()
                calls = []
                tag = {"project": "demo", "kind": "ui", "summary": "ok", "deletable": False, "confidence": .9}
                def runner(command, **kwargs):
                    self.assertIn("실행 예정:", output.getvalue())
                    self.assertIn("external_transfer=yes", output.getvalue())
                    calls.append(command[0])
                    # 2차 그룹화 응답도 같은 adapter 경계를 통과한다.
                    response = tag if "OCR 텍스트" in kwargs["input"] else {"assignments": [{"id": 1, "group": "demo"}]}
                    if command[0] == "codex":
                        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(response))
                        stdout = "progress"
                    else:
                        stdout = json.dumps({"structured_output": response})
                    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
                def create(config):
                    if config.provider == "local":
                        return None
                    if config.provider == "openai":
                        class FailedAPI:
                            def generate_json(self, **kwargs):
                                self_test.assertIn("실행 예정:", output.getvalue())
                                calls.append("openai")
                                raise RuntimeError("429 Bearer api-secret")
                        return FailedAPI()
                    adapter = providers.CodexCliProvider if config.provider == "codex" else providers.ClaudeCliProvider
                    return adapter(config, runner=runner)
                self_test = self
                with patch.object(engine, "db", return_value=conn), \
                     patch.dict("os.environ", {"OPENAI_API_KEY": "sk-not-displayed"}), \
                     patch.object(providers, "probe_codex_cli", return_value=capabilities["codex"]), \
                     patch.object(providers, "probe_claude_cli", return_value=capabilities["claude"]), \
                     patch.object(providers, "create_provider", side_effect=create) as factory, \
                     patch.object(engine, "ocr", return_value="screen text"), \
                     contextlib.redirect_stdout(output):
                    cli.cmd_scan(args)
                text = output.getvalue()
                self.assertIn("실행 예정:", text)
                self.assertIn("실행 결과:", text)
                self.assertNotIn("api-secret", text)
                self.assertNotIn("sk-not-displayed", text)
                self.assertEqual(conn.execute("SELECT count(*) FROM images").fetchone()[0], 1)
                if vendor and mode != "local" and not image:
                    self.assertIn(vendor, calls)
                    self.assertEqual(conn.execute("SELECT project FROM images").fetchone()[0], "demo")
                elif mode == "api" and consent:
                    self.assertEqual(calls, ["openai"])
                    self.assertIn("provider=local", text)
                else:
                    self.assertEqual(calls, [])
                self.assertEqual(factory.call_count, 1)
