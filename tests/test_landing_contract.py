"""Keep public landing promises and measurement links from drifting."""
from __future__ import annotations

import unittest
from pathlib import Path


LANDING = Path(__file__).parents[1] / "docs" / "landing"


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

    def test_feedback_prefills_the_operational_signal_fields(self):
        self.assertIn('id="installed-version"', self.html)
        self.assertIn('id="installation-status"', self.html)
        self.assertIn("installed-version:", self.script)
        self.assertIn("installation-status:", self.script)
        self.assertIn("issues/new?", self.script)


if __name__ == "__main__":
    unittest.main()
