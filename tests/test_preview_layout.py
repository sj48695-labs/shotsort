import unittest

from preview_layout import (
    PREVIEW_CARD_CLASSES,
    PREVIEW_HEADER_CLASSES,
    PREVIEW_IMAGE_CLASSES,
    PREVIEW_IMAGE_PROPS,
    PREVIEW_IMAGE_WRAPPER_CLASSES,
    PREVIEW_IMAGE_WRAPPER_STYLE,
    PREVIEW_METADATA_CLASSES,
    contained_size,
)


class PreviewLayoutTests(unittest.TestCase):
    def test_dialog_uses_a_bounded_non_scrolling_flex_layout(self):
        self.assertIn("flex-col", PREVIEW_CARD_CLASSES)
        self.assertIn("overflow-hidden", PREVIEW_CARD_CLASSES)
        self.assertIn("shrink-0", PREVIEW_HEADER_CLASSES)
        self.assertIn("shrink-0", PREVIEW_METADATA_CLASSES)

        self.assertIn("flex-1", PREVIEW_IMAGE_WRAPPER_CLASSES)
        self.assertIn("min-h-0", PREVIEW_IMAGE_WRAPPER_CLASSES)
        self.assertIn("w-full", PREVIEW_IMAGE_WRAPPER_CLASSES)
        self.assertIn("overflow-hidden", PREVIEW_IMAGE_WRAPPER_CLASSES)
        self.assertIn("100vh", PREVIEW_IMAGE_WRAPPER_STYLE)
        self.assertIn("calc(", PREVIEW_IMAGE_WRAPPER_STYLE)

    def test_qimg_explicitly_contains_the_whole_image(self):
        self.assertIn("w-full", PREVIEW_IMAGE_CLASSES)
        self.assertIn("h-full", PREVIEW_IMAGE_CLASSES)
        self.assertEqual(PREVIEW_IMAGE_PROPS, "fit=contain")

    def test_contain_preserves_wide_portrait_and_square_aspect_ratios(self):
        viewport = (1000, 700)

        for source in ((1182, 230), (230, 1182), (800, 800)):
            with self.subTest(source=source):
                rendered = contained_size(source, viewport)
                self.assertLessEqual(rendered[0], viewport[0])
                self.assertLessEqual(rendered[1], viewport[1])
                self.assertAlmostEqual(
                    rendered[0] / rendered[1], source[0] / source[1], places=7
                )


if __name__ == "__main__":
    unittest.main()
