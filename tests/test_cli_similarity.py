"""``shotsort similarity``의 비파괴 검사와 명시 선택 삭제 테스트."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cli
import engine


def fingerprint(path: Path, sha: str) -> engine.ImageFingerprint:
    return engine.ImageFingerprint(path, sha, "0000000000000000")


class SimilarityCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.keeper_path = self.root / "keeper.png"
        self.other_path = self.root / "other.png"
        self.keeper_path.write_bytes(b"keeper bytes")
        self.other_path.write_bytes(b"other")
        self.keeper = fingerprint(self.keeper_path, "keeper")
        self.other = fingerprint(self.other_path, "other")
        self.group = engine.DuplicateGroup(
            "near",
            (self.keeper, self.other),
            self.keeper,
            (
                engine.MemberSimilarity(self.keeper, 0, 100.0),
                engine.MemberSimilarity(self.other, 2, 96.88),
            ),
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def args(self, *extra: str):
        return cli.build_parser().parse_args(["similarity", str(self.root), *extra])

    def test_parser_defaults_and_passes_threshold_to_engine(self):
        args = self.args("--threshold", "3")
        with patch.object(engine, "find_images", return_value=[]), patch.object(
            engine, "find_duplicate_groups", return_value=engine.DuplicateDetectionResult()
        ) as find_groups:
            cli.cmd_similarity(args)

        self.assertEqual(args.threshold, 3)
        find_groups.assert_called_once_with([], hamming_threshold=3)
        self.assertEqual(self.args().threshold, 8)

    def test_renders_group_member_numbers_scores_sizes_and_errors(self):
        result = engine.DuplicateDetectionResult(
            [self.group], [engine.SimilarityError(self.root / "broken.png", "읽기 실패")]
        )
        with patch.object(engine, "find_images", return_value=[self.keeper_path, self.other_path]), patch.object(
            engine, "find_duplicate_groups", return_value=result
        ), patch("builtins.print") as output:
            cli.cmd_similarity(self.args())

        rendered = "\n".join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn("[1] 유사", rendered)
        self.assertIn("보존 후보", rendered)
        self.assertIn("1.", rendered)
        self.assertIn("100.00%", rendered)
        self.assertIn("96.88%", rendered)
        self.assertIn(engine.human_mb(self.keeper_path.stat().st_size), rendered)
        self.assertIn("검사 실패", rendered)
        self.assertIn("읽기 실패", rendered)

    def test_renders_exact_group_distinctly(self):
        group = engine.DuplicateGroup(
            "exact",
            (self.keeper, self.other),
            self.keeper,
            (
                engine.MemberSimilarity(self.keeper, 0, 100.0),
                engine.MemberSimilarity(self.other, 0, 100.0),
            ),
        )
        with patch("builtins.print") as output:
            cli._render_similarity_groups([group])

        self.assertIn("[1] exact", str(output.call_args_list[0].args[0]))

    def test_only_explicit_non_keeper_selection_is_trashed_once(self):
        args = self.args("--delete", "1:2", "-y")
        with patch.object(engine, "find_images", return_value=[self.keeper_path, self.other_path]), patch.object(
            engine, "find_duplicate_groups", return_value=engine.DuplicateDetectionResult([self.group])
        ), patch.object(engine, "trash", return_value=1) as trash:
            cli.cmd_similarity(args)

        trash.assert_called_once_with([str(self.other_path)])

    def test_no_selection_or_invalid_or_declined_selection_never_trashes(self):
        result = engine.DuplicateDetectionResult([self.group])
        for extra, response in (((), "y"), (("--delete", "1:1"), "y"), (("--delete", "9:2"), "y"), (("--delete", "1:2"), "n")):
            with self.subTest(extra=extra), patch.object(engine, "find_images", return_value=[]), patch.object(
                engine, "find_duplicate_groups", return_value=result
            ), patch.object(engine, "trash") as trash, patch("builtins.input", return_value=response):
                cli.cmd_similarity(self.args(*extra))
            trash.assert_not_called()

    def test_invalid_delete_syntax_is_rejected_without_trashing(self):
        with patch.object(engine, "find_images", return_value=[]), patch.object(
            engine, "find_duplicate_groups", return_value=engine.DuplicateDetectionResult([self.group])
        ), patch.object(engine, "trash") as trash, patch("builtins.print") as output:
            cli.cmd_similarity(self.args("--delete", "1"))

        self.assertTrue(any("GROUP:NUMBER" in str(call.args[0]) for call in output.call_args_list))
        trash.assert_not_called()

    def test_duplicate_delete_selection_is_rejected_without_trashing(self):
        with patch.object(engine, "find_images", return_value=[]), patch.object(
            engine, "find_duplicate_groups", return_value=engine.DuplicateDetectionResult([self.group])
        ), patch.object(engine, "trash") as trash, patch("sys.stderr") as stderr:
            cli.cmd_similarity(self.args("--delete", "1:2", "--delete", "1:2", "-y"))

        self.assertIn("중복된 삭제 선택", stderr.write.call_args_list[0].args[0])
        trash.assert_not_called()

    def test_trash_runtime_error_is_printed_to_stderr(self):
        with patch.object(engine, "find_images", return_value=[]), patch.object(
            engine, "find_duplicate_groups", return_value=engine.DuplicateDetectionResult([self.group])
        ), patch.object(engine, "trash", side_effect=RuntimeError("권한 없음")), patch("sys.stderr") as stderr:
            cli.cmd_similarity(self.args("--delete", "1:2", "-y"))

        self.assertEqual(stderr.write.call_args_list[0].args, ("권한 없음",))


if __name__ == "__main__":
    unittest.main()
