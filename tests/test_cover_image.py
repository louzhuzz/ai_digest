from __future__ import annotations

import io
import unittest

from PIL import Image

from ai_digest.cover_image import generate_cover_image


class CoverImageTest(unittest.TestCase):
    def test_generate_cover_image_returns_small_jpeg(self) -> None:
        payload = generate_cover_image("AI 每日新闻速递")

        self.assertLess(len(payload), 64 * 1024)
        image = Image.open(io.BytesIO(payload))
        self.assertEqual(image.format, "JPEG")
        self.assertGreater(image.size[0], 0)
        self.assertGreater(image.size[1], 0)


if __name__ == "__main__":
    unittest.main()
