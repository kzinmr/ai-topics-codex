import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from ai_topics_codex.config import Config, json_write
from ai_topics_codex.profile import initialize, sync_assets
from ai_topics_codex.runner import run, tick
from ai_topics_codex.state import Store, profile_lock
from ai_topics_codex.schedule import cron_matches
from ai_topics_codex.backup import snapshot, restore
from ai_topics_codex.codex import codex

SOURCE = Path(__file__).resolve().parents[1]


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wiki test spaces ")
        self.root = Path(self.temp.name)
        self.cfg = Config(SOURCE, self.root / "profile one")
        initialize(self.cfg)
        for name in ("SCHEMA.md", "index.md", "log.md"):
            (self.cfg.wiki / name).write_text("# fixture\n")

    def tearDown(self):
        self.temp.cleanup()

    def job(self, name="blog-ingest"):
        job = self.cfg.job(name)
        job.update(
            script=None,
            no_agent=False,
            depends_on=[],
            skills=[],
            response_format="text",
        )
        return job

    def fake(self, cfg, prompt, timeout):
        return {"text": "finished", "usage": {"output": 2}}

    def test_delivery_failure_does_not_repeat_wiki_job(self):
        j = self.job()
        self.cfg.local = {
            "delivery": {"operations": {"kind": "command", "command": []}}
        }
        result = run(self.cfg, j["name"], self.fake)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["delivery_status"], "failed")

    def test_parent_harness_config_is_not_inherited(self):
        with patch.dict(
            os.environ,
            {"CODEX_HOME": "/operator/private", "PI_CODING_AGENT_DIR": "/operator/pi"},
        ):
            env = self.cfg.env()
            self.assertEqual(env["CODEX_HOME"], str(self.cfg.profile / ".codex"))
            self.assertNotIn("PI_CODING_AGENT_DIR", env)

    def test_manifest_complete(self):
        self.assertEqual(len(self.cfg.jobs), 30)

    def test_init_refuses_existing(self):
        with self.assertRaises(ValueError):
            initialize(self.cfg)

    def test_env_ignores_host_home(self):
        with patch.dict(os.environ, {"HOME": "/unexpected"}):
            env = self.cfg.env()
            self.assertEqual(env["HOME"], str(self.cfg.profile))
            self.assertEqual(env["WIKI_ROOT"], str(self.cfg.wiki))

    def test_dry_run_has_no_side_effects(self):
        fresh = self.root / "never created"
        result = subprocess.run(
            [
                str(SOURCE / "bin/ai-topics-codex"),
                "--profile",
                str(fresh),
                "run",
                "newsletter-ingest",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(fresh.exists())

    def test_no_agent_does_not_call_harness(self):
        j = self.job()
        j.update(script="fixture.py", no_agent=True)
        (self.cfg.runtime / "scripts/fixture.py").write_text('print("hello")')

        def fail(*args):
            raise AssertionError("unexpected model call")

        result = run(self.cfg, j["name"], fail)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["delivery_status"], "pending")

    def test_wake_gate_and_empty_no_agent(self):
        for content in ("print('{\"wakeAgent\": false}')", "pass"):
            j = self.job()
            j.update(script="fixture.py", no_agent=True)
            (self.cfg.runtime / "scripts/fixture.py").write_text(content)
            result = run(self.cfg, j["name"], self.fake)
            self.assertIn(result["status"], ("ok", "skipped"))
        self.assertEqual(list((self.cfg.state / "outbox").glob("*")), [])

    def test_script_failure_and_json_failure(self):
        for content in (
            "raise SystemExit(3)",
            'print(\'{"ok": false, "error": "missing"}\')',
        ):
            j = self.job()
            j["script"] = "fixture.py"
            (self.cfg.runtime / "scripts/fixture.py").write_text(content)
            result = run(self.cfg, j["name"], self.fake)
            self.assertEqual(result["status"], "error")
        self.assertFalse((self.cfg.runtime / "outputs" / j["id"]).exists())

    def test_json_contract(self):
        j = self.job()
        j["response_format"] = "json"
        result = run(
            self.cfg,
            j["name"],
            lambda *a: {
                "text": '{"decisions":[], "checkpoint_run_id":"fixture", "summary_ja":"test"}\nCOST_REPORT: invented'
            },
        )
        self.assertEqual(result["status"], "error")
        result = run(
            self.cfg,
            j["name"],
            lambda *a: {
                "text": '```json\n{"decisions":[], "checkpoint_run_id":"fixture", "summary_ja":"test"}\n```'
            },
        )
        self.assertEqual(result["status"], "ok")

    def test_legacy_checkpoint_handoff(self):
        j = self.job("blog-triage")
        j["response_format"] = "json"
        self.assertEqual(
            run(
                self.cfg,
                j["name"],
                lambda *a: {
                    "text": '{"decisions": [], "checkpoint_run_id":"fixture", "summary_ja":"test"}'
                },
            )["status"],
            "ok",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(self.cfg.runtime / "scripts/blog_triage_checkpoint.py"),
            ],
            env=self.cfg.env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["checkpoint_run_id"], "fixture")

    def test_stale_dependency_prevents_model(self):
        store = Store(self.cfg.state)
        at = datetime.now(timezone.utc) - timedelta(days=3)
        store.start("old", "blog-ingest", at.isoformat())
        store.finish("old", at.isoformat(), "ok", {})
        store.close()
        result = run(self.cfg, "blog-triage", self.fake)
        self.assertEqual(result["status"], "error")
        self.assertIn("stale", result["error"])

    def test_tick_is_deduplicated(self):
        for j in self.cfg.jobs:
            j["enabled"] = False
        j = self.job()
        j.update(enabled=True, schedule="* * * * *")
        at = datetime.now(timezone.utc)
        counter = []

        def model(*args):
            counter.append(1)
            return {"text": "ok"}

        self.assertEqual(len(tick(self.cfg, at, model)), 1)
        self.assertEqual(tick(self.cfg, at, model), [])
        self.assertEqual(counter, [1])

    def test_profile_lock(self):
        with profile_lock(self.cfg.state):
            with self.assertRaises(RuntimeError):
                run(self.cfg, "blog-ingest", self.fake)

    def test_live_scheduler_rejected(self):
        (self.cfg.profile / ".hermes").mkdir()
        with self.assertRaises(RuntimeError):
            run(self.cfg, "blog-ingest", self.fake)

    def test_asset_drift_is_not_overwritten(self):
        p = self.cfg.runtime / "scripts/blog_ingest.py"
        p.write_text("local change")
        with self.assertRaises(ValueError):
            sync_assets(self.cfg)
        self.assertEqual(p.read_text(), "local change")

    def test_secrets_redacted(self):
        j = self.job()
        json_write(
            self.cfg.state / "secrets.json", {"TEST_API_KEY": "private-value-test"}
        )
        result = run(self.cfg, j["name"], lambda *a: {"text": "private-value-test"})
        self.assertEqual(result["status"], "ok")
        self.assertNotIn(
            "private-value-test",
            (self.cfg.state / "runs" / result["run"] / "response.md").read_text(),
        )

    def test_snapshot_relocation_sqlite_and_no_secrets(self):
        json_write(self.cfg.runtime / "processed_x_accounts.json", {"item": "seen"})
        json_write(
            self.cfg.runtime / "checkpoints/latest.json",
            {
                "raw_path": str(self.cfg.profile) + "/wiki/raw/a.md",
                "legacy": "/opt/data/wiki/raw/b.md",
            },
        )
        json_write(self.cfg.state / "secrets.json", {"secret": "never-export"})
        (self.cfg.profile / ".blogwatcher").mkdir()
        db = sqlite3.connect(self.cfg.profile / ".blogwatcher/blogwatcher.db")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE seen(value)")
        db.execute("INSERT INTO seen VALUES(42)")
        db.commit()
        bundle = self.root / "state.tar.gz"
        snapshot(self.cfg.profile, bundle, quiesced=True)
        db.close()
        with tarfile.open(bundle) as tar:
            self.assertNotIn(".wiki-agent/secrets.json", tar.getnames())
        target = Config(SOURCE, self.root / "moved with spaces")
        initialize(target)
        restore(target, bundle)
        data = json.loads((target.runtime / "checkpoints/latest.json").read_text())
        self.assertTrue(data["raw_path"].startswith(str(target.profile)))
        self.assertTrue(data["legacy"].startswith(str(target.profile)))
        db = sqlite3.connect(target.profile / ".blogwatcher/blogwatcher.db")
        self.assertEqual(db.execute("SELECT value FROM seen").fetchone()[0], 42)
        db.close()
        with self.assertRaises(ValueError):
            restore(target, bundle)

    def test_rehearsal_snapshot_requires_explicit_restore(self):
        bundle = self.root / "state.tar.gz"
        snapshot(self.cfg.profile, bundle)
        target = Config(SOURCE, self.root / "moved")
        initialize(target)
        with self.assertRaises(ValueError):
            restore(target, bundle)

    def test_archive_traversal_is_rejected(self):
        import io, hashlib

        body = b"bad"
        manifest = {
            "version": 2,
            "layout": "codex-v1",
            "consistency": "quiesced",
            "files": {
                "../escape": {"sha256": hashlib.sha256(body).hexdigest(), "size": 3}
            },
        }
        bundle = self.root / "bad.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            for name, data in [
                ("manifest.json", json.dumps(manifest).encode()),
                ("../escape", body),
            ]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        with self.assertRaises(ValueError):
            restore(self.cfg, bundle)
        self.assertFalse((self.root / "escape").exists())


class ProtocolTest(unittest.TestCase):
    def test_protocols(self):
        for name, fn in [("codex", codex)]:
            for scenario in ("ok", "reject", "failure", "eof", "approval", "timeout"):
                with (
                    self.subTest(name=name, scenario=scenario),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    argv = [
                        sys.executable,
                        str(SOURCE / "tests/fixtures/harness.py"),
                        name,
                        scenario,
                    ]
                    env = {**os.environ, "WIKI_PROFILE_ROOT": temp}
                    if scenario == "ok":
                        self.assertEqual(
                            json.loads(fn(argv, "task", temp, env, 2, {})["text"])[
                                "decisions"
                            ],
                            [],
                        )
                    else:
                        with self.assertRaises((RuntimeError, EOFError, TimeoutError)):
                            fn(
                                argv,
                                "task",
                                temp,
                                env,
                                0.3 if scenario == "timeout" else 2,
                                {},
                            )


class CronTest(unittest.TestCase):
    def test_sunday_and_dom_or(self):
        sun = datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc)
        self.assertTrue(cron_matches("0 10 1 * 7", sun))
        self.assertTrue(cron_matches("0 10 */2 * *", sun))
        self.assertFalse(cron_matches("0 10 */2 * *", sun + timedelta(days=1)))

    def test_invalid(self):
        for expr in ("* * * *", "60 * * * *", "*/0 * * * *", "* * * * 8"):
            with self.assertRaises(ValueError):
                cron_matches(expr, datetime.now())


class ContentBackupTest(unittest.TestCase):
    def test_deleted_tracked_content_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = Config(SOURCE, root / "source")
            initialize(source)
            subprocess.run(
                ["git", "init", str(source.repo)], check=True, capture_output=True
            )
            page = source.repo / "wiki/deleted.md"
            page.write_text("original")
            subprocess.run(
                ["git", "-C", str(source.repo), "add", "wiki/deleted.md"], check=True
            )
            page.unlink()
            bundle = root / "snapshot.tar.gz"
            snapshot(source.profile, bundle, quiesced=True, include_content=True)
            target = Config(SOURCE, root / "target")
            initialize(target)
            (target.repo / "wiki/deleted.md").write_text("original")
            restore(target, bundle)
            self.assertFalse((target.repo / "wiki/deleted.md").exists())


if __name__ == "__main__":
    unittest.main()
