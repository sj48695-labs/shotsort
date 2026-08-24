"""DMG signing/notarization boundary contracts without invoking macOS tools."""
from __future__ import annotations

import unittest
from pathlib import Path


BUILD_SCRIPT = Path(__file__).parents[1] / "build_app.sh"
ENTITLEMENTS = Path(__file__).parents[1] / "packaging" / "entitlements.plist"
RELEASE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"
SMOKE_SCRIPT = Path(__file__).parents[1] / "scripts" / "release" / "smoke_install.sh"


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
            "xcrun notarytool submit",
            "xcrun stapler staple",
            "xcrun stapler validate",
            "spctl -a -vvv -t install",
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
        self.assertIn('NOTARY_KEYCHAIN: ${{ runner.temp }}/shotsort-signing.keychain-db', workflow)
        self.assertIn('security delete-keychain "$RUNNER_TEMP/shotsort-signing.keychain-db"', workflow)

    def test_smoke_validates_the_stapled_dmg_before_copying_the_app(self):
        smoke = SMOKE_SCRIPT.read_text()
        self.assertIn('xcrun stapler validate "$DMG_PATH"', smoke)
        self.assertNotIn('xcrun stapler validate "$INSTALLED_APP"', smoke)


if __name__ == "__main__":
    unittest.main()
