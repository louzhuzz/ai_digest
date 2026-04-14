from __future__ import annotations

import io
import unittest

from PIL import Image

from ai_digest.cover_image import _font_candidates, generate_cover_image


class CoverImageTest(unittest.TestCase):
    def test_font_candidates_include_windows_cjk_fonts_for_wsl(self) -> None:
        candidates = _font_candidates()

        self.assertIn("/mnt/c/Windows/Fonts/msyh.ttc", candidates)
        self.assertIn("/mnt/c/Windows/Fonts/simhei.ttf", candidates)
        self.assertLess(
            candidates.index("/mnt/c/Windows/Fonts/msyh.ttc"),
            candidates.index("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )

    def test_generate_cover_image_returns_small_jpeg(self) -> None:
        payload = generate_cover_image("AI 每日新闻速递")

        self.assertLess(len(payload), 64 * 1024)
        image = Image.open(io.BytesIO(payload))
        self.assertEqual(image.format, "JPEG")
        self.assertGreater(image.size[0], 0)
        self.assertGreater(image.size[1], 0)


if __name__ == "__main__":
    unittest.main()
