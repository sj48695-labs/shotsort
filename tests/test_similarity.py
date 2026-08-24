"""유사 이미지 지문 캐시 테스트."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

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
                image.putpixel((x, y), (0, 0, 0))
        image.save(upright, quality=100, subsampling=0)

        # 저장된 픽셀은 시계 방향으로 회전했고, EXIF 6이 세로 방향으로 복원한다.
        exif = Image.Exif()
        exif[274] = 6
        image.transpose(Image.Transpose.ROTATE_90).save(
            rotated_with_exif, exif=exif, quality=100, subsampling=0
        )

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

    def test_exact_duplicates_take_priority_over_perceptual_hash(self):
        first = self.root / "first.png"
        second = self.root / "second.png"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        fingerprints = {
            first: engine.ImageFingerprint(first, "same-sha", "0000000000000000"),
            second: engine.ImageFingerprint(second, "same-sha", "ffffffffffffffff"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            groups = engine.find_duplicate_groups([second, first], conn=self.conn)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].kind, "exact")
        self.assertEqual(groups[0].members, (fingerprints[first], fingerprints[second]))

    def test_near_duplicates_are_grouped_within_hamming_threshold(self):
        first = self.root / "first.png"
        second = self.root / "second.png"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        fingerprints = {
            first: engine.ImageFingerprint(first, "first", "0000000000000000"),
            second: engine.ImageFingerprint(second, "second", "0000000000000003"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            groups = engine.find_duplicate_groups([second, first], hamming_threshold=2, conn=self.conn)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].kind, "near")
        self.assertEqual(groups[0].members, (fingerprints[first], fingerprints[second]))

    def test_exact_group_exposes_full_similarity_for_every_member(self):
        first = self.root / "first.png"
        second = self.root / "second.png"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        fingerprints = {
            first: engine.ImageFingerprint(first, "same-sha", "0000000000000000"),
            second: engine.ImageFingerprint(second, "same-sha", "ffffffffffffffff"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            group = engine.find_duplicate_groups([second, first], conn=self.conn)[0]

        self.assertEqual(
            group.member_similarities,
            (
                engine.MemberSimilarity(fingerprints[first], distance=0, similarity_percent=100.0),
                engine.MemberSimilarity(fingerprints[second], distance=0, similarity_percent=100.0),
            ),
        )

    def test_near_group_scores_members_against_keeper_deterministically(self):
        keeper = self.root / "keeper.png"
        other = self.root / "other.png"
        keeper.write_bytes(b"keeper-with-more-bytes")
        other.write_bytes(b"other")
        fingerprints = {
            keeper: engine.ImageFingerprint(keeper, "keeper", "0000000000000000"),
            other: engine.ImageFingerprint(other, "other", "0000000000000003"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            first = engine.find_duplicate_groups([other, keeper], hamming_threshold=2, conn=self.conn)[0]
            second = engine.find_duplicate_groups([keeper, other], hamming_threshold=2, conn=self.conn)[0]

        expected = (
            engine.MemberSimilarity(fingerprints[keeper], distance=0, similarity_percent=100.0),
            engine.MemberSimilarity(fingerprints[other], distance=2, similarity_percent=96.88),
        )
        self.assertEqual(first.keeper, fingerprints[keeper])
        self.assertEqual(first.member_similarities, expected)
        self.assertEqual(second.member_similarities, expected)

    def test_near_group_at_threshold_keeps_score_and_complete_link_boundary(self):
        first = self.root / "first.png"
        second = self.root / "second.png"
        third = self.root / "third.png"
        first.write_bytes(b"first-is-deliberately-the-largest-file")
        second.write_bytes(b"second")
        third.write_bytes(b"third")
        fingerprints = {
            first: engine.ImageFingerprint(first, "first", "0000000000000000"),
            second: engine.ImageFingerprint(second, "second", "0000000000000003"),
            third: engine.ImageFingerprint(third, "third", "0000000000000007"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            groups = engine.find_duplicate_groups([third, second, first], hamming_threshold=2, conn=self.conn)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].members, (fingerprints[first], fingerprints[second]))
        self.assertEqual(groups[0].member_similarities[1].distance, 2)
        self.assertEqual(groups[0].member_similarities[1].similarity_percent, 96.88)

    def test_near_duplicate_chain_requires_complete_link(self):
        first = self.root / "a.png"
        middle = self.root / "b.png"
        last = self.root / "c.png"
        for path in (first, middle, last):
            path.write_bytes(path.name.encode())
        fingerprints = {
            first: engine.ImageFingerprint(first, "a", "0000000000000000"),
            middle: engine.ImageFingerprint(middle, "b", "0000000000000001"),
            last: engine.ImageFingerprint(last, "c", "0000000000000003"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            groups = engine.find_duplicate_groups([last, middle, first], hamming_threshold=1, conn=self.conn)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].members, (fingerprints[first], fingerprints[middle]))

    def test_generated_images_detect_exact_and_reencoded_near_duplicates(self):
        exact_source = self.root / "exact-source.png"
        exact_copy = self.root / "exact-copy.png"
        near_source = self.root / "near-source.png"
        reencoded = self.root / "near-reencoded.jpg"
        resized = self.root / "near-resized.webp"
        unrelated = self.root / "unrelated.png"

        image = Image.new("RGB", (160, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 150, 90), fill="navy")
        draw.ellipse((35, 20, 115, 85), fill="gold")
        draw.line((0, 0, 159, 99), fill="red", width=5)
        image.save(exact_source)
        exact_copy.write_bytes(exact_source.read_bytes())
        near_image = image.copy()
        near_image.putpixel((0, 99), (1, 1, 1))
        near_image.save(near_source)
        near_image.save(reencoded, quality=82)
        near_image.resize((240, 150)).save(resized, quality=82)
        Image.new("RGB", (160, 100), "black").save(unrelated)

        groups = engine.find_duplicate_groups(
            [unrelated, resized, near_source, reencoded, exact_copy, exact_source],
            hamming_threshold=8,
            conn=self.conn,
        )

        self.assertEqual([group.kind for group in groups], ["exact", "near"])
        self.assertEqual({member.path for member in groups[0].members}, {exact_source, exact_copy})
        self.assertEqual({member.path for member in groups[1].members}, {near_source, reencoded, resized})
        self.assertTrue(all(score.similarity_percent == 100.0 for score in groups[0].member_similarities))
        self.assertNotIn(unrelated, {member.path for group in groups for member in group.members})

    def test_keeper_prefers_larger_pixel_area(self):
        small = self.root / "small.png"
        large = self.root / "large.png"
        Image.new("RGB", (20, 20), "red").save(small)
        Image.new("RGB", (30, 30), "red").save(large)
        fingerprints = {
            small: engine.ImageFingerprint(small, "same-sha", "0000000000000000"),
            large: engine.ImageFingerprint(large, "same-sha", "ffffffffffffffff"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            group = engine.find_duplicate_groups([small, large], conn=self.conn)[0]

        self.assertEqual(group.keeper, fingerprints[large])
        self.assertEqual(group.duplicate_candidates, (fingerprints[small],))

    def test_keeper_breaks_same_area_tie_by_larger_file_size(self):
        smaller = self.root / "smaller.png"
        larger = self.root / "larger.png"
        Image.new("RGB", (24, 24), "red").save(smaller, optimize=True)
        Image.new("RGB", (24, 24), "red").save(larger)
        larger.write_bytes(larger.read_bytes() + b"padding")
        fingerprints = {
            smaller: engine.ImageFingerprint(smaller, "same-sha", "0000000000000000"),
            larger: engine.ImageFingerprint(larger, "same-sha", "ffffffffffffffff"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            group = engine.find_duplicate_groups([smaller, larger], conn=self.conn)[0]

        self.assertGreater(larger.stat().st_size, smaller.stat().st_size)
        self.assertEqual(group.keeper, fingerprints[larger])

    def test_keeper_breaks_complete_tie_by_lexicographic_path(self):
        later = self.root / "z.png"
        earlier = self.root / "a.png"
        for path in (later, earlier):
            Image.new("RGB", (24, 24), "red").save(path)
        fingerprints = {
            later: engine.ImageFingerprint(later, "same-sha", "0000000000000000"),
            earlier: engine.ImageFingerprint(earlier, "same-sha", "ffffffffffffffff"),
        }

        with patch.object(engine, "image_fingerprint", side_effect=lambda path, **_: fingerprints[Path(path)]):
            group = engine.find_duplicate_groups([later, earlier], conn=self.conn)[0]

        self.assertEqual(group.keeper, fingerprints[earlier])
        self.assertEqual(group.duplicate_candidates, (fingerprints[later],))

    def test_broken_and_non_image_inputs_are_safely_excluded(self):
        valid = self.root / "valid.png"
        broken = self.root / "broken.png"
        text = self.root / "notes.txt"
        Image.new("RGB", (24, 16), "red").save(valid)
        broken.write_bytes(b"not an image")
        text.write_text("not an image")

        self.assertEqual(
            engine.find_duplicate_groups([valid, broken, text, self.root / "missing.png"], conn=self.conn),
            [],
        )


if __name__ == "__main__":
    unittest.main()
