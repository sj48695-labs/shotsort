"""휴지통 이동 — Finder -10010 은 파일별 재시도, 없는 파일은 이동 실패가 아님."""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine


POSIX_FILE = re.compile(r'POSIX file "([^"]+)"')
FINDER_10010 = (
    "29:246: execution error: Finder에 오류 발생: "
    "처리 구조가 이 클래스의 대상체를 처리할 수 없습니다. (-10010).\n"
)


def add_image(conn, path, *, grp="act", size=100):
    conn.execute(
        """INSERT INTO images(path, ocr_text, project, kind, summary, grp, size)
           VALUES(?,?,?,?,?,?,?)""",
        (str(path), "", grp, "ui", "", grp, size),
    )
    conn.commit()


def db_paths(conn):
    return [row["path"] for row in conn.execute("SELECT path FROM images ORDER BY path")]


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.db_path = self.state / "cache.db"
        self.patches = [
            patch.object(engine, "STATE_DIR", self.state),
            patch.object(engine, "DB_PATH", self.db_path),
        ]
        for item in self.patches:
            item.start()
        self.conn = engine.db()

    def tearDown(self):
        self.conn.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def _png(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(b"png")
        add_image(self.conn, path)
        return path

    def _run_trash(self, paths, fake_run):
        with patch("engine.subprocess.run", side_effect=fake_run):
            return engine.trash([str(p) for p in paths])

    def test_batch_success_forgets_all_and_returns_trashed(self):
        a, b = self._png("a.png"), self._png("b.png")
        calls = []

        def fake_run(cmd, **kwargs):
            files = POSIX_FILE.findall(cmd[cmd.index("-e") + 1])
            calls.append(files)
            for file in files:
                Path(file).unlink()
            return subprocess.CompletedProcess(cmd, 0, "", "")

        result = self._run_trash([a, b], fake_run)
        self.assertEqual(list(result.trashed), [str(a), str(b)])
        self.assertEqual(result.missing, ())
        self.assertEqual(result.failed, ())
        self.assertEqual(len(calls), 1)
        self.assertEqual(db_paths(self.conn), [])
        self.assertFalse(a.exists())
        self.assertFalse(b.exists())

    def test_finder_10010_retries_each_file_instead_of_failing_the_job(self):
        a, b, c = self._png("a.png"), self._png("b.png"), self._png("c.png")
        calls = []

        def fake_run(cmd, **kwargs):
            files = POSIX_FILE.findall(cmd[cmd.index("-e") + 1])
            calls.append(tuple(files))
            if len(files) > 1:
                raise subprocess.CalledProcessError(1, cmd, stderr=FINDER_10010)
            Path(files[0]).unlink()
            return subprocess.CompletedProcess(cmd, 0, "", "")

        result = self._run_trash([a, b, c], fake_run)
        self.assertEqual(list(result.trashed), [str(a), str(b), str(c)])
        self.assertEqual(result.failed, ())
        self.assertEqual(len(calls[0]), 3)
        self.assertEqual(calls[1:], [(str(a),), (str(b),), (str(c),)])
        self.assertEqual(db_paths(self.conn), [])

    def test_one_per_file_failure_does_not_block_the_rest(self):
        a, b, c = self._png("a.png"), self._png("b.png"), self._png("c.png")

        def fake_run(cmd, **kwargs):
            files = POSIX_FILE.findall(cmd[cmd.index("-e") + 1])
            if len(files) > 1:
                raise subprocess.CalledProcessError(1, cmd, stderr=FINDER_10010)
            if files[0] == str(b):
                raise subprocess.CalledProcessError(1, cmd, stderr="permission denied\n")
            Path(files[0]).unlink()
            return subprocess.CompletedProcess(cmd, 0, "", "")

        result = self._run_trash([a, b, c], fake_run)
        self.assertEqual(list(result.trashed), [str(a), str(c)])
        self.assertEqual(list(result.failed), [str(b)])
        self.assertEqual(db_paths(self.conn), [str(b)])
        self.assertTrue(b.exists())

    def test_missing_files_are_forgotten_not_reported_as_trash_failure(self):
        a = self._png("a.png")
        missing = self.root / "gone.png"
        add_image(self.conn, missing)
        calls = []

        def fake_run(cmd, **kwargs):
            files = POSIX_FILE.findall(cmd[cmd.index("-e") + 1])
            calls.append(tuple(files))
            for file in files:
                Path(file).unlink()
            return subprocess.CompletedProcess(cmd, 0, "", "")

        result = self._run_trash([a, missing], fake_run)
        self.assertEqual(list(result.trashed), [str(a)])
        self.assertEqual(list(result.missing), [str(missing)])
        self.assertEqual(result.failed, ())
        self.assertEqual(calls, [(str(a),)])
        self.assertEqual(db_paths(self.conn), [])

    def test_trash_summary_does_not_repeat_failure_prefix(self):
        result = engine.TrashResult(
            trashed=("/tmp/ok.png",),
            missing=("/tmp/gone.png",),
            failed=("/tmp/bad.png",),
        )
        text = engine.trash_summary(result)
        self.assertEqual(text.count("휴지통 이동 실패"), 0)
        self.assertIn("1개를 휴지통으로 보냈습니다", text)
        self.assertIn("원본 파일이 없습니다", text)
        self.assertIn("gone.png", text)
        self.assertIn("보내지 못했습니다", text)
        self.assertIn("bad.png", text)


class TrashGuiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()
        cls.cli = Path(__file__).resolve().parents[1].joinpath("cli.py").read_text()

    def test_gui_and_cli_use_shared_summary_not_duplicated_prefix(self):
        self.assertIn("engine.trash_summary", self.app)
        self.assertIn("engine.trash_summary", self.cli)
        self.assertNotIn('휴지통 이동 실패: {e}', self.app)
        self.assertNotIn('휴지통 이동 실패: {e}', self.cli)


if __name__ == "__main__":
    unittest.main()
