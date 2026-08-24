"""Keep public landing promises and measurement links from drifting."""
from __future__ import annotations

import unittest
from pathlib import Path


LANDING = Path(__file__).parents[1] / "docs" / "landing"
PAGES_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "pages.yml"


class LandingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (LANDING / "index.html").read_text()
        cls.script = (LANDING / "app.js").read_text()

    def test_all_download_ctas_use_the_one_click_landing_source(self):
        url = "https://github.com/sj48695-labs/shotsort/releases/latest?source=landing"
        self.assertGreaterEqual(self.html.count('data-download-cta'), 3)
        self.assertGreaterEqual(self.html.count(url), 3)
        self.assertIn('const releaseUrl = "' + url + '"', self.script)

    def test_privacy_faq_and_feedback_measurement_are_explained(self):
        for required_text in ("로컬 OCR", "OCR 텍스트", "축소 이미지", "휴지통", "macOS 13 Ventura 이상", "feedback_submit", "install_success"):
            self.assertIn(required_text, self.html)

    def test_unsigned_release_is_not_presented_as_ready_for_installation(self):
        self.assertIn("공증 릴리스 준비 중", self.html)
        self.assertIn("공증 릴리스가 준비되면", self.html)

    def test_feedback_prefills_the_operational_signal_fields(self):
        self.assertIn('id="installed-version"', self.html)
        self.assertIn('id="installation-status"', self.html)
        self.assertIn("installed-version:", self.script)
        self.assertIn("installation-status:", self.script)
        self.assertIn("issues/new?", self.script)
        self.assertNotIn('labels: "feedback"', self.script)
        self.assertNotIn("labels=feedback", (Path(__file__).parents[1] / "README.md").read_text())

    def test_pages_deployment_enables_pages_and_publishes_the_landing_artifact(self):
        workflow = PAGES_WORKFLOW.read_text()
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("actions/configure-pages@v5", workflow)
        self.assertIn("enablement: true", workflow)
        self.assertIn("secrets.PAGES_SETUP_TOKEN || github.token", workflow)
        self.assertIn("actions/upload-pages-artifact@v3", workflow)
        self.assertIn("path: docs/landing", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)


if __name__ == "__main__":
    unittest.main()
