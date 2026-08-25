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
