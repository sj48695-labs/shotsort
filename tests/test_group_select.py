"""그룹 내부 선택 — 아직 그리지 않은 카드도 선택·삭제 대상에 포함."""
from __future__ import annotations

import unittest

from group_select import apply_select, range_paths, selected_bytes, selected_in_group


class GroupSelectTests(unittest.TestCase):
    def test_selected_in_group_keeps_group_order_and_ignores_other_groups(self):
        selected = {"/b.png", "/other.png", "/a.png"}
        self.assertEqual(
            selected_in_group(["/a.png", "/b.png", "/c.png"], selected),
            ["/a.png", "/b.png"],
        )

    def test_apply_select_includes_paths_without_rendered_checkboxes(self):
        selected: set[str] = set()
        apply_select(selected, ["/a.png", "/b.png", "/c.png"], True)
        self.assertEqual(selected, {"/a.png", "/b.png", "/c.png"})
        apply_select(selected, ["/b.png"], False)
        self.assertEqual(selected, {"/a.png", "/c.png"})

    def test_range_paths_covers_unrendered_members_between_anchor_and_current(self):
        order = ["/a.png", "/b.png", "/c.png", "/d.png"]
        self.assertEqual(range_paths(order, "/a.png", "/d.png"), order)
        self.assertEqual(range_paths(order, "/c.png", "/b.png"), ["/b.png", "/c.png"])

    def test_selected_bytes_sums_only_chosen_paths(self):
        sizes = {"/a.png": 1_048_576, "/b.png": 2_097_152, "/c.png": 10}
        self.assertEqual(selected_bytes(sizes, ["/a.png", "/c.png"]), 1_048_586)
        self.assertEqual(selected_bytes(sizes, ["/missing.png"]), 0)


class GroupSelectWiringContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.src = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()

    def test_each_group_has_a_select_delete_action(self):
        self.assertIn("from group_select import", self.src)
        self.assertIn("선택 삭제", self.src)
        self.assertIn("do_trash_group_selected", self.src)
        self.assertIn("selected_in_group", self.src)
