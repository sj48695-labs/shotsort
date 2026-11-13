"""DMG signing/notarization boundary contracts without invoking macOS tools."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


BUILD_SCRIPT = Path(__file__).parents[1] / "build_app.sh"
ENTITLEMENTS = Path(__file__).parents[1] / "packaging" / "entitlements.plist"
RELEASE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"
SMOKE_SCRIPT = Path(__file__).parents[1] / "scripts" / "release" / "smoke_install.sh"
CHECKSUM_SCRIPT = SMOKE_SCRIPT.with_name("verify_dmg.sh")


class BuildAppContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = BUILD_SCRIPT.read_text()

    def test_signing_inputs_must_be_provided_together(self):
        self.assertIn('SIGN_IDENTITY="${SIGN_IDENTITY:-}"', self.script)
        self.assertIn('NOTARY_PROFILE="${NOTARY_PROFILE:-}"', self.script)
        self.assertIn('SIGN_IDENTITY와 NOTARY_PROFILE은 함께 설정해야 합니다', self.script)

    def test_signed_release_follows_sign_dmg_notarize_staple_verify_order(self):
        commands = (
            "codesign --force --deep --options runtime --timestamp",
            "hdiutil create",
            'codesign --force --timestamp --sign "$SIGN_IDENTITY" dist/shotsort.dmg',
            "xcrun notarytool submit",
            "xcrun stapler staple",
            "xcrun stapler validate",
            "spctl -a -vvv -t open --context context:primary-signature",
        )
        positions = [self.script.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("packaging/entitlements.plist", self.script)
        self.assertIn("codesign --verify --deep --strict --verbose=2", self.script)
        self.assertIn('NOTARY_ARGS+=(--keychain "$NOTARY_KEYCHAIN")', self.script)

    def test_unsigned_build_is_explicitly_not_for_distribution(self):
        self.assertIn("무서명 빌드", self.script)
        self.assertIn("배포 불가", self.script)

    def test_no_signing_secrets_are_hard_coded(self):
        self.assertNotIn("APPLE_APP_SPECIFIC_PASSWORD", self.script)
        self.assertNotIn("APPLE_CERTIFICATE_PASSWORD", self.script)

    def test_entitlements_are_limited_to_pyinstaller_runtime_requirements(self):
        entitlements = ENTITLEMENTS.read_text()
        self.assertIn("allow-unsigned-executable-memory", entitlements)
        self.assertIn("disable-library-validation", entitlements)
        self.assertNotIn("network.client", entitlements)
        self.assertNotIn("camera", entitlements)

    def test_release_prepares_its_venv_and_uses_macos_base64_syntax(self):
        workflow = RELEASE_WORKFLOW.read_text()
        self.assertIn("python3 -m venv .venv", workflow)
        self.assertIn(".venv/bin/pip install -q -r requirements.txt", workflow)
        self.assertIn("base64 -D", workflow)
        self.assertNotIn("base64 --decode", workflow)

    def test_release_keeps_notary_credentials_in_the_temporary_keychain(self):
        workflow = RELEASE_WORKFLOW.read_text()
        self.assertIn('store-credentials "$NOTARY_PROFILE"', workflow)
        self.assertIn('--keychain "$RELEASE_KEYCHAIN"', workflow)
        job_environment = workflow.split('    env:\n', 1)[1].split('    steps:', 1)[0]
        self.assertNotIn('runner.temp', job_environment)
        build_step = workflow.split('      - name: Build signed and notarized DMG', 1)[1].split('      - name:', 1)[0]
        self.assertIn('          NOTARY_KEYCHAIN: ${{ runner.temp }}/shotsort-signing.keychain-db', build_step)
        self.assertIn('security delete-keychain "$RUNNER_TEMP/shotsort-signing.keychain-db"', workflow)

    def test_smoke_validates_the_stapled_dmg_before_copying_the_app(self):
        smoke = SMOKE_SCRIPT.read_text()
        self.assertIn('xcrun stapler validate "$DMG_PATH"', smoke)
        self.assertNotIn('xcrun stapler validate "$INSTALLED_APP"', smoke)

    def test_gatekeeper_assesses_the_installed_app_as_executable_code(self):
        smoke = SMOKE_SCRIPT.read_text()
        self.assertIn('spctl -a -vvv -t execute "$INSTALLED_APP"', smoke)
        self.assertNotIn('-t install', smoke)
        self.assertNotIn('-t install', self.script)

    def test_workflow_release_scripts_are_executable(self):
        for script in (BUILD_SCRIPT, SMOKE_SCRIPT, CHECKSUM_SCRIPT):
            with self.subTest(script=script.name):
                self.assertTrue(os.access(script, os.X_OK), f"실행 권한이 없습니다: {script}")

    def test_checksum_verifies_from_the_dmg_directory_and_rejects_modified_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            dmg = root / "dist" / "shotsort.dmg"
            dmg.write_bytes(b"shotsort")
            for checksum in ("dist/shotsort.dmg.sha256", "custom.sha256"):
                with self.subTest(checksum=checksum):
                    command = ["bash", str(CHECKSUM_SCRIPT), "dist/shotsort.dmg", checksum]
                    generated = subprocess.run(command, cwd=root, capture_output=True, text=True)
                    self.assertEqual(generated.returncode, 0, generated.stderr)
                    environment = dict(os.environ, VERIFY_CHECKSUM="1")
                    verified = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
                    self.assertEqual(verified.returncode, 0, verified.stderr)
                    dmg.write_bytes(b"changed")
                    rejected = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0)
                    dmg.write_bytes(b"shotsort")


if __name__ == "__main__":
    unittest.main()
