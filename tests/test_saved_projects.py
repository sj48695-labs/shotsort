import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import engine


def add_image(conn, path, *, text="", project="unknown", kind="ui", grp=None,
              manual=0, deletable=0):
    conn.execute(
        """INSERT INTO images(path, ocr_text, project, kind, summary, grp,
                              manual_group, deletable)
           VALUES(?,?,?,?,?,?,?,?)""",
        (str(path), text, project, kind, text, grp, manual, deletable),
    )
    conn.commit()


class SavedProjectsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.db_path = self.state / "cache.db"
        self.patches = [patch.object(engine, "STATE_DIR", self.state),
                        patch.object(engine, "DB_PATH", self.db_path)]
        for item in self.patches:
            item.start()
        self.conn = engine.db()

    def tearDown(self):
        self.conn.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_project_crud_persists(self):
        engine.save_project("act-server", ["act server", "gitlab.com/acme/act"])
        engine.save_project("hitc", "hitc.io", enabled=False)
        self.assertEqual(engine.list_projects(), [
            {"name": "act-server", "aliases": ["act server", "gitlab.com/acme/act"],
             "characteristics": "", "enabled": True},
            {"name": "hitc", "aliases": ["hitc.io"], "characteristics": "",
             "enabled": False},
        ])
        self.assertEqual(engine.set_project_enabled("hitc", True), 1)
        self.assertEqual(engine.delete_project("act-server"), 1)
        self.assertEqual(engine.list_projects(), [
            {"name": "hitc", "aliases": ["hitc.io"], "characteristics": "",
             "enabled": True}])

    def test_characteristics_persist_and_active_rules_resolve(self):
        saved = engine.save_project(
            "act", ["act chat"], characteristics="주황색 대화방 형태"
        )
        engine.save_project("disabled", [], enabled=False, characteristics="파란 화면")
        self.assertEqual(saved["characteristics"], "주황색 대화방 형태")
        self.assertEqual(engine.resolve_project_rules(self.conn), [{
            "name": "act", "aliases": ["act chat"],
            "characteristics": "주황색 대화방 형태", "enabled": True,
        }])
        self.assertEqual(len(engine.resolve_project_rules(self.conn, enabled_only=False)), 2)

    def test_existing_saved_projects_table_is_migrated(self):
        self.conn.close()
        self.db_path.unlink()
        old = sqlite3.connect(self.db_path)
        old.execute(
            "CREATE TABLE saved_projects(name TEXT PRIMARY KEY, aliases TEXT, enabled INTEGER)"
        )
        old.execute("INSERT INTO saved_projects VALUES('act', '[]', 1)")
        old.commit()
        old.close()
        self.conn = engine.db()
        row = self.conn.execute(
            "SELECT characteristics FROM saved_projects WHERE name='act'"
        ).fetchone()
        self.assertEqual(row[0], "")

    def test_visual_characteristics_only_enter_prompt_with_image(self):
        calls = []

        class Messages:
            def create(self, **kwargs):
                calls.append(kwargs)
                payload = {"project": "act", "kind": "chat", "summary": "대화",
                           "deletable": False, "confidence": 0.9}
                return SimpleNamespace(content=[SimpleNamespace(
                    type="text", text=__import__("json").dumps(payload))])

        client = SimpleNamespace(messages=Messages())
        rules = [{"name": "act", "aliases": [],
                  "characteristics": "주황색 대화방 형태", "enabled": True}]
        image = self.root / "screen.png"
        engine.classify_image(client, "model", "hello", image, False, rules)
        text_prompt = calls[-1]["messages"][0]["content"][-1]["text"]
        self.assertIn("act", text_prompt)
        self.assertNotIn("주황색 대화방 형태", text_prompt)

        with patch.object(engine, "_downscaled_b64", return_value=(None, None)):
            engine.classify_image(client, "model", "hello", image, True, rules)
        failed_image_prompt = calls[-1]["messages"][0]["content"][-1]["text"]
        self.assertNotIn("주황색 대화방 형태", failed_image_prompt)

        with patch.object(engine, "_downscaled_b64", return_value=("abc", "image/jpeg")):
            engine.classify_image(client, "model", "hello", image, True, rules)
        image_prompt = calls[-1]["messages"][0]["content"][-1]["text"]
        self.assertIn("주황색 대화방 형태", image_prompt)

    def test_existing_images_table_is_migrated(self):
        self.conn.close()
        self.db_path.unlink()
        old = sqlite3.connect(self.db_path)
        old.execute("CREATE TABLE images(path TEXT PRIMARY KEY, project TEXT, grp TEXT)")
        old.commit()
        old.close()
        self.conn = engine.db()
        columns = {r[1] for r in self.conn.execute("PRAGMA table_info(images)")}
        self.assertIn("manual_group", columns)

    def test_saved_matching_is_scoped_and_prefers_longer_rule(self):
        inside = self.root / "scan" / "one.png"
        outside = self.root / "other" / "two.png"
        add_image(self.conn, inside, text="deploy act server now")
        add_image(self.conn, outside, text="deploy act server now", grp="keep-me")
        engine.save_project("act", [])
        engine.save_project("act-server", ["act server"])
        self.assertEqual(engine.apply_saved_projects(conn=self.conn, root=self.root / "scan"), 1)
        self.assertEqual(self.conn.execute("SELECT grp FROM images WHERE path=?", (str(inside),)).fetchone()[0], "act-server")
        self.assertEqual(self.conn.execute("SELECT grp FROM images WHERE path=?", (str(outside),)).fetchone()[0], "keep-me")

    def test_filename_matching_and_token_boundaries(self):
        good = self.root / "scan" / "hitc-dashboard.png"
        false_positive = self.root / "scan" / "transaction.png"
        add_image(self.conn, good)
        add_image(self.conn, false_positive, text="transaction complete")
        engine.save_project("hitc", [])
        engine.save_project("act", [])
        engine.apply_saved_projects(conn=self.conn, paths=[good, false_positive])
        rows = dict(self.conn.execute("SELECT path, grp FROM images"))
        self.assertEqual(rows[str(good)], "hitc")
        self.assertIsNone(rows[str(false_positive)])

    def test_manual_groups_survive_consolidation_and_saved_rules(self):
        manual = self.root / "manual.png"
        automatic = self.root / "automatic.png"
        add_image(self.conn, manual, text="act-server", grp="old")
        add_image(self.conn, automatic, text="act-server", grp="old")
        with patch.object(engine, "db", return_value=self.conn):
            self.assertEqual(engine.move_images_to_group([str(manual)], "chosen"), 1)
        engine.save_project("act-server", [])
        engine.consolidate_all(conn=self.conn, use_llm=False, paths=[manual, automatic])
        rows = {r[0]: (r[1], r[2]) for r in self.conn.execute(
            "SELECT path, grp, manual_group FROM images")}
        self.assertEqual(rows[str(manual)], ("chosen", 1))
        self.assertEqual(rows[str(automatic)][0], "act-server")

    def test_rename_marks_rows_manual(self):
        add_image(self.conn, self.root / "a.png", grp="old")
        add_image(self.conn, self.root / "b.png", grp="old")
        with patch.object(engine, "db", return_value=self.conn):
            self.assertEqual(engine.rename_group("old", "new"), 2)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM images WHERE grp='new' AND manual_group=1").fetchone()[0]
        self.assertEqual(count, 2)

    def test_saved_project_keeps_singleton_group(self):
        only = self.root / "only.png"
        add_image(self.conn, only, text="work in gitlab.com/acme/act")
        engine.save_project("act-server", ["gitlab.com/acme/act"])
        engine.consolidate_all(conn=self.conn, use_llm=False, paths=[only])
        self.assertEqual(self.conn.execute("SELECT grp FROM images").fetchone()[0], "act-server")


if __name__ == "__main__":
    unittest.main()
