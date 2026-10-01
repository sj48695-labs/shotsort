"""GUI 프로젝트 관리 대화상자가 기존 규칙을 불러 고칠 수 있는지 소스 계약."""
from __future__ import annotations

import unittest
from pathlib import Path


APP = Path(__file__).parents[1] / "app.py"


class ProjectManageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = APP.read_text()

    def test_dialog_can_edit_an_existing_saved_project(self):
        self.assertIn("engine.update_project", self.app)
        self.assertIn("수정 저장", self.app)
        self.assertIn("{project['name']} 수정", self.app)
        self.assertIn("reset_form", self.app)
