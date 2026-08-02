"""Similarity fingerprint cache tests."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import engine


class SimilarityFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        engine.db(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def test_file_sha_reads_content_after_two_megabytes(self):
        path = self.root / "large.bin"
        prefix = b"a" * (2 * 1024 * 1024)
        path.write_bytes(prefix + b"first")
        first = engine.file_sha(path)
        path.write_bytes(prefix + b"other")

        self.assertEqual(engine.file_sha(path), hashlib.sha256(prefix + b"other").hexdigest())
        self.assertNotEqual(engine.file_sha(path), first)

    def test_fingerprint_cache_hits_then_invalidates_when_file_changes(self):
        path = self.root / "image.png"
        Image.new("RGB", (24, 16), "red").save(path)

        with patch.object(engine, "_compute_image_fingerprint", wraps=engine._compute_image_fingerprint) as compute:
            first = engine.image_fingerprint(path, conn=self.conn)
            second = engine.image_fingerprint(path, conn=self.conn)
            self.assertEqual(compute.call_count, 1)
            self.assertEqual(second, first)

            Image.new("RGB", (25, 16), "blue").save(path)
            os.utime(path, None)
            changed = engine.image_fingerprint(path, conn=self.conn)

        self.assertEqual(compute.call_count, 2)
        self.assertNotEqual(changed.sha256, first.sha256)
        row = self.conn.execute("SELECT * FROM fingerprint_cache WHERE path = ?", (str(path),)).fetchone()
        self.assertEqual(row["sha256"], changed.sha256)
        self.assertEqual(row["algorithm_version"], engine.FINGERPRINT_ALGORITHM_VERSION)

    def test_phash_normalizes_exif_orientation(self):
        upright = self.root / "upright.jpg"
        rotated_with_exif = self.root / "rotated.jpg"
        image = Image.new("RGB", (20, 40), "white")
        for y in range(20):
            for x in range(8):
                image.putpixel((x, y), "black")
        image.save(upright)

        # The stored pixels are rotated clockwise; EXIF 6 restores the upright image.
        exif = Image.Exif()
        exif[274] = 6
        image.transpose(Image.Transpose.ROTATE_90).save(rotated_with_exif, exif=exif)

        self.assertEqual(
            engine.image_fingerprint(upright, conn=self.conn).phash,
            engine.image_fingerprint(rotated_with_exif, conn=self.conn).phash,
        )

    def test_decode_error_keeps_other_fingerprint_data_available(self):
        broken = self.root / "broken.png"
        broken.write_bytes(b"not an image")

        fingerprint = engine.image_fingerprint(broken, conn=self.conn)

        self.assertEqual(fingerprint.sha256, hashlib.sha256(b"not an image").hexdigest())
        self.assertIsNone(fingerprint.phash)


if __name__ == "__main__":
    unittest.main()
