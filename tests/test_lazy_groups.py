import unittest

from lazy_groups import GroupPage


class GroupPageTests(unittest.TestCase):
    def test_collapsed_group_reveals_nothing(self):
        page = GroupPage(total=388, page_size=24)

        self.assertEqual(page.reveal(expanded=False), range(0, 0))
        self.assertEqual(page.rendered, 0)
        self.assertEqual(page.remaining, 388)

    def test_expansion_reveals_only_first_page(self):
        page = GroupPage(total=388, page_size=24)

        self.assertEqual(page.reveal(expanded=True), range(0, 24))
        self.assertEqual(page.rendered, 24)
        self.assertEqual(page.remaining, 364)

    def test_more_returns_only_new_items_and_stops_at_total(self):
        page = GroupPage(total=50, page_size=24)

        self.assertEqual(page.reveal(expanded=True), range(0, 24))
        self.assertEqual(page.more(), range(24, 48))
        self.assertEqual(page.more(), range(48, 50))
        self.assertEqual(page.more(), range(0, 0))
        self.assertEqual(page.remaining, 0)

    def test_repeated_expansion_does_not_render_duplicate_cards(self):
        page = GroupPage(total=30, page_size=24)

        self.assertEqual(page.reveal(expanded=True), range(0, 24))
        self.assertEqual(page.reveal(expanded=False), range(0, 0))
        self.assertEqual(page.reveal(expanded=True), range(0, 0))
        self.assertEqual(page.rendered, 24)


if __name__ == "__main__":
    unittest.main()
