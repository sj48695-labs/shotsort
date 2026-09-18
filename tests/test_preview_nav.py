import unittest
from pathlib import Path

from preview_nav import PreviewNav, shortcut_action


def item(name: str) -> dict:
    return {"path": f"/shots/{name}.png", "grp": "demo", "kind": "ui", "summary": name}


class PreviewNavTests(unittest.TestCase):
    def setUp(self):
        self.items = [item("a"), item("b"), item("c")]

    def test_position_is_one_based_n_slash_n(self):
        nav = PreviewNav([item(str(i)) for i in range(63)], index=11)
        self.assertEqual(nav.position, "12 / 63")
        self.assertEqual(nav.current["path"], "/shots/11.png")

    def test_next_and_prev_move_within_the_group_order(self):
        nav = PreviewNav.for_item(self.items, item("b"))
        self.assertEqual(nav.position, "2 / 3")
        self.assertTrue(nav.next())
        self.assertEqual(nav.current["path"], item("c")["path"])
        self.assertTrue(nav.prev())
        self.assertTrue(nav.prev())
        self.assertEqual(nav.current["path"], item("a")["path"])

    def test_first_and_last_do_not_wrap(self):
        nav = PreviewNav.for_item(self.items, item("a"))
        self.assertFalse(nav.has_prev)
        self.assertFalse(nav.prev())
        self.assertEqual(nav.position, "1 / 3")

        nav = PreviewNav.for_item(self.items, item("c"))
        self.assertFalse(nav.has_next)
        self.assertFalse(nav.next())
        self.assertEqual(nav.position, "3 / 3")

    def test_uses_the_group_order_as_given(self):
        # list_groups already shows capture/display order; do not re-sort.
        later_first = [item("later"), item("earlier")]
        nav = PreviewNav.for_item(later_first, item("earlier"))
        self.assertEqual(nav.index, 1)
        self.assertEqual(nav.position, "2 / 2")

    def test_missing_current_item_falls_back_to_that_item_alone(self):
        nav = PreviewNav.for_item(self.items, item("ghost"))
        self.assertEqual(nav.total, 1)
        self.assertEqual(nav.current["path"], item("ghost")["path"])
        self.assertEqual(nav.position, "1 / 1")


class PreviewShortcutTests(unittest.TestCase):
    def test_arrows_navigate_instead_of_closing(self):
        self.assertEqual(shortcut_action("ArrowLeft", preview_open=True), "prev")
        self.assertEqual(shortcut_action("ArrowRight", preview_open=True), "next")
        self.assertNotEqual(shortcut_action("ArrowRight", preview_open=True), "close")
        self.assertEqual(shortcut_action("Escape", preview_open=True), "close")

    def test_delete_and_backspace_ask_before_trashing(self):
        self.assertEqual(shortcut_action("Delete", preview_open=True), "delete")
        self.assertEqual(shortcut_action("Backspace", preview_open=True), "delete")

    def test_space_and_enter_open_when_preview_is_closed(self):
        self.assertEqual(shortcut_action(" ", preview_open=False), "open")
        self.assertEqual(shortcut_action("Enter", preview_open=False), "open")
        self.assertIsNone(shortcut_action(" ", preview_open=True))
        self.assertIsNone(shortcut_action("Enter", preview_open=True))

    def test_shortcuts_are_ignored_while_typing_in_a_field(self):
        for tag in ("input", "textarea", "select", "INPUT"):
            with self.subTest(tag=tag):
                self.assertIsNone(
                    shortcut_action("ArrowRight", preview_open=True, focused_tag=tag)
                )
                self.assertIsNone(
                    shortcut_action("Enter", preview_open=False, focused_tag=tag)
                )


class PreviewWiringContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()

    def test_open_preview_shows_position_and_prev_next_controls(self):
        self.assertIn("from preview_nav import", self.src)
        self.assertIn("PreviewNav", self.src)
        self.assertIn("nav.position", self.src)
        self.assertIn("chevron_left", self.src)
        self.assertIn("chevron_right", self.src)

    def test_keyboard_handler_skips_editable_fields_and_reuses_confirm(self):
        self.assertIn("ui.keyboard", self.src)
        self.assertIn("'input'", self.src)
        self.assertIn("'textarea'", self.src)
        self.assertIn("'select'", self.src)
        self.assertIn("shortcut_action", self.src)
        self.assertIn("await _confirm(", self.src)


if __name__ == "__main__":
    unittest.main()
