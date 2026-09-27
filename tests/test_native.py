"""Native subscription, state conversion and structured-handoff acceptance tests."""

import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_topics_codex.config import Config, json_write
from ai_topics_codex.profile import initialize, sync_assets
from ai_topics_codex.codex import codex, codex_env, require_capacity
from ai_topics_codex.backup import snapshot, restore
from ai_topics_codex.runner import run, prompt_for
from ai_topics_codex.state import Store
from ai_topics_codex.structured import validate_handoff

SOURCE = Path(__file__).resolve().parents[1]


class NativeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex native ")
        self.root = Path(self.temp.name)
        self.cfg = Config(SOURCE, self.root / "profile")
        initialize(self.cfg)

    def tearDown(self):
        self.temp.cleanup()

    def test_no_legacy_directory_and_native_discovery(self):
        self.assertFalse((self.cfg.profile / ".hermes").exists())
        self.assertEqual(len(list(self.cfg.skills.glob("*/SKILL.md"))), 23)
        self.assertTrue((self.cfg.repo / "AGENTS.override.md").is_file())
        self.assertNotIn("HERMES_HOME", self.cfg.env())

    def test_profile_is_not_inherited_from_old_environment(self):
        with patch.dict(
            os.environ,
            {"HERMES_PROFILE_ROOT": "/old/live", "HERMES_SUBPROCESS_HOME": "/old/live"},
        ):
            cfg = Config(SOURCE, self.root / "new")
            self.assertEqual(cfg.profile, self.root / "new")

    def test_api_keys_and_provider_overrides_removed(self):
        env = codex_env(
            {
                "HOME": "/profile",
                "OPENAI_API_KEY": "fixture",
                "CODEX_API_KEY": "fixture",
                "OPENAI_BASE_URL": "https://example.invalid",
                "CODEX_WIF_ID_TOKEN_FILE": "/operator/token",
                "CODEX_ACCESS_TOKEN": "fixture",
                "EMAIL_PASSWORD": "source-secret",
            }
        )
        self.assertEqual(env, {"HOME": "/profile"})

    def test_legacy_adapter_config_rejected(self):
        json_write(self.cfg.local_path, {"harness": "pi"})
        with self.assertRaisesRegex(ValueError, "legacy"):
            Config(SOURCE, self.cfg.profile)

    def test_quota_exhaustion_never_falls_back(self):
        for state in (
            {"ordinaryUsageAllowed": False},
            {"rateLimits": {"primary": {"usedPercent": 100}}},
            {"rateLimits": {"spendControlReached": True}},
        ):
            with self.assertRaises(RuntimeError):
                require_capacity(state)
        require_capacity(
            {
                "ordinaryUsageAllowed": True,
                "rateLimits": {"primary": {"usedPercent": 8}},
            }
        )

    def test_publication_defaults_to_local(self):
        self.assertIn(
            "do not commit or push", prompt_for(self.cfg, self.cfg.job("active-crawl"))
        )
        self.cfg.local["publication"] = "push"
        self.assertIn(
            "configured content origin",
            prompt_for(self.cfg, self.cfg.job("active-crawl")),
        )

    def test_drifted_skill_preserved(self):
        file = self.cfg.skills / "llm-wiki/SKILL.md"
        file.write_text("operator edit")
        with self.assertRaisesRegex(ValueError, "local asset changed"):
            sync_assets(self.cfg)
        self.assertEqual(file.read_text(), "operator edit")

    def test_asset_symlink_escape_rejected_before_write(self):
        file = self.cfg.skills / "llm-wiki/SKILL.md"
        file.unlink()
        outside = self.root / "outside"
        outside.write_text("do not change")
        file.symlink_to(outside)
        with self.assertRaises(ValueError):
            sync_assets(self.cfg)
        self.assertEqual(outside.read_text(), "do not change")

    def decision(self):
        raw = self.cfg.wiki / "raw/articles/example.md"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text("Verified article body")
        return {
            "item_id": "item-1",
            "source": "blog",
            "source_name": "Example",
            "title": "An article",
            "url": "https://example.test/a",
            "raw_path": str(raw),
            "recommended_action": "take",
            "reason_ja": "新情報",
            "candidate_wiki_path": None,
            "body_excerpt": "Verified article body",
        }

    def payload(self):
        return {
            "checkpoint_run_id": "current",
            "summary_ja": "検証",
            "decisions": [self.decision()],
        }

    def test_structured_source_evidence_and_duplicate_ids(self):
        payload = self.payload()
        job = self.cfg.job("blog-triage")
        validate_handoff(self.cfg, job, payload)
        payload["decisions"].append(dict(payload["decisions"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_handoff(self.cfg, job, payload)

    def test_take_cannot_reference_outside_profile(self):
        payload = self.payload()
        outside = self.root / "outside.md"
        outside.write_text("unrelated")
        payload["decisions"][0]["raw_path"] = str(outside)
        with self.assertRaisesRegex(ValueError, "inside this profile"):
            validate_handoff(self.cfg, self.cfg.job("blog-triage"), payload)

    def test_groups_cannot_invent_ids(self):
        payload = self.payload()
        payload["groups"] = [
            {"theme": "test", "summary_ja": "試験", "item_ids": ["unknown"]}
        ]
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_handoff(self.cfg, self.cfg.job("dreaming-group"), payload)

    def test_stale_checkpoint_is_not_published(self):
        job = self.cfg.job("blog-triage")
        job.update(depends_on=[], script="fixture.py")
        (self.cfg.runtime / "scripts/fixture.py").write_text(
            'print(\'{"run_id":"new-checkpoint"}\')'
        )
        payload = self.payload()
        result = run(self.cfg, job["name"], lambda *args: {"text": json.dumps(payload)})
        self.assertEqual(result["status"], "error")
        self.assertFalse(
            (self.cfg.runtime / "outputs/blog-triage/latest.json").exists()
        )

    def test_malformed_structured_output_is_not_published(self):
        job = self.cfg.job("blog-triage")
        job.update(depends_on=[], script=None)
        payload = self.payload()
        del payload["decisions"][0]["body_excerpt"]
        result = run(self.cfg, job["name"], lambda *args: {"text": json.dumps(payload)})
        self.assertEqual(result["status"], "error")
        self.assertFalse(
            (self.cfg.runtime / "outputs/blog-triage/latest.json").exists()
        )

    def test_legacy_import_converts_paths_ids_and_preserves_secrets_boundary(self):
        old = self.root / "legacy"
        (old / ".hermes/cron/data/blog_ingest").mkdir(parents=True)
        json_write(
            old / ".hermes/cron/data/blog_ingest/latest.json",
            {
                "raw_path": str(old / "wiki/raw/a.md"),
                "state_path": "/opt/data/.hermes/cron/data/blog_ingest/latest.json",
            },
        )
        json_write(old / ".hermes/processed_emails.json", {"message-1": True})
        json_write(
            old / ".hermes/cron/jobs.json",
            {
                "jobs": [
                    {
                        "id": "58c2f4a7e1bd",
                        "name": "blog-triage",
                        "last_status": "ok",
                        "last_run_at": "2026-09-27T00:00:00+00:00",
                    }
                ]
            },
        )
        output = old / ".hermes/cron/output/58c2f4a7e1bd/20260927.md"
        output.parent.mkdir(parents=True)
        output.write_text(
            "## Response\n" + json.dumps({"checkpoint_run_id": "old", "decisions": []})
        )
        (old / ".hermes/.env").write_text("EMAIL_PASSWORD=do-not-export")
        json_write(old / ".codex/auth.json", {"secret": "never-export"})
        bundle = self.root / "legacy.tar.gz"
        snapshot(old, bundle, legacy=True, quiesced=True)
        with tarfile.open(bundle) as tar:
            names = tar.getnames()
            self.assertFalse(
                any(
                    ".hermes" in name or "auth.json" in name or ".env" in name
                    for name in names
                )
            )
        restore(self.cfg, bundle)
        self.assertTrue((self.cfg.runtime / "outputs/blog-triage/latest.json").exists())
        payload = json.loads(
            (self.cfg.runtime / "checkpoints/blog_ingest/latest.json").read_text()
        )
        self.assertEqual(
            payload["state_path"],
            str(self.cfg.runtime / "checkpoints/blog_ingest/latest.json"),
        )
        self.assertEqual(payload["raw_path"], str(self.cfg.wiki / "raw/a.md"))
        self.assertTrue(
            json.loads((self.cfg.runtime / "processed_emails.json").read_text())[
                "message-1"
            ]
        )

    def test_executable_content_hooks_survive_restore(self):
        hook = self.cfg.repo / ".githooks/pre-commit"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)
        bundle = self.root / "hooks.tar.gz"
        snapshot(self.cfg.profile, bundle, include_content=True, quiesced=True)
        target = Config(SOURCE, self.root / "target")
        initialize(target)
        restore(target, bundle)
        self.assertTrue(os.access(target.repo / ".githooks/pre-commit", os.X_OK))
        self.assertTrue((target.repo / "AGENTS.override.md").is_file())

    def test_snapshot_does_not_copy_old_agent_configs_or_credentials(self):
        json_write(self.cfg.repo / "config/hermes/config.json", {"secret": "no"})
        json_write(self.cfg.repo / "config/feeds/feeds.json", {"feeds": []})
        (self.cfg.repo / "wiki/.env").write_text("secret=no")
        bundle = self.root / "content.tar.gz"
        snapshot(self.cfg.profile, bundle, include_content=True, quiesced=True)
        with tarfile.open(bundle) as tar:
            names = tar.getnames()
            self.assertIn("ai-topics/config/feeds/feeds.json", names)
            self.assertNotIn("ai-topics/config/hermes/config.json", names)
            self.assertNotIn("ai-topics/wiki/.env", names)

    def test_codex_rejects_api_account_before_turn(self):
        argv = [
            sys.executable,
            str(SOURCE / "tests/fixtures/harness.py"),
            "codex",
            "apikey",
        ]
        with self.assertRaisesRegex(RuntimeError, "subscription login"):
            codex(argv, "test", self.cfg.repo, self.cfg.env(), 5, {})


class SkippedDependencyTest(unittest.TestCase):
    def test_skipped_upstream_does_not_consume_previous_json(self):
        from datetime import datetime, timezone

        with tempfile.TemporaryDirectory() as temp:
            cfg = Config(SOURCE, Path(temp))
            initialize(cfg)
            store = Store(cfg.state)
            at = datetime.now(timezone.utc).isoformat()
            store.start("empty", "blog-ingest", at)
            store.finish("empty", at, "skipped", {})
            store.close()
            stale = cfg.runtime / "outputs/blog-triage/latest.json"
            json_write(stale, {"old": True})

            def no_model(*args):
                raise AssertionError("must not consume stale output")

            result = run(cfg, "blog-triage", no_model)
            self.assertEqual(result["status"], "skipped")
            self.assertFalse(stale.exists())
            self.assertEqual(
                run(cfg, "blog-wiki-ingest", no_model)["status"], "skipped"
            )


class ReplayInputTest(unittest.TestCase):
    def test_retry_uses_original_collector_output_once(self):
        from ai_topics_codex.runner import retry

        with tempfile.TemporaryDirectory() as temp:
            cfg = Config(SOURCE, Path(temp))
            initialize(cfg)
            job = cfg.job("x-bookmarks-ingest")
            job["script"] = "fixture.py"
            counter = cfg.profile / "counter"
            script = cfg.runtime / "scripts/fixture.py"
            script.write_text(
                "from pathlib import Path\np=Path("
                + repr(str(counter))
                + ')\np.write_text(str(int(p.read_text())+1) if p.exists() else "1")\nprint("original bookmarks")\n'
            )

            def fail(*args):
                raise RuntimeError("quota exhausted after collection")

            failed = run(cfg, job["name"], fail)
            self.assertEqual(failed["status"], "error")

            def success(cfg, prompt, timeout):
                self.assertIn("original bookmarks", prompt)
                return {"text": "processed original bookmarks"}

            done = retry(cfg, failed["run"], success)
            self.assertEqual(done["status"], "ok")
            self.assertEqual(counter.read_text(), "1")
            with self.assertRaisesRegex(ValueError, "newer run"):
                retry(cfg, failed["run"], success)

    def test_dreaming_rejects_stale_nested_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = Config(SOURCE, Path(temp))
            initialize(cfg)
            job = cfg.job("dreaming-group")
            job.update(depends_on=[], script="fixture.py")
            (cfg.runtime / "scripts/fixture.py").write_text(
                'print(\'{"_checkpoint":{"run_id":"new"}}\')'
            )
            value = {
                "checkpoint_run_id": "old",
                "summary_ja": "x",
                "decisions": [],
                "groups": [],
            }
            result = run(cfg, job["name"], lambda *args: {"text": json.dumps(value)})
            self.assertEqual(result["status"], "error")
            self.assertIn("checkpoint_run_id", result["error"])

    def test_missing_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = Config(SOURCE, Path(temp))
            initialize(cfg)
            job = cfg.job("blog-triage")
            job.update(depends_on=[], script="fixture.py")
            (cfg.runtime / "scripts/fixture.py").write_text(
                'print(\'{"run_id":"current","candidates":[{"item_id":"required"}]}\')'
            )
            value = {"checkpoint_run_id": "current", "summary_ja": "x", "decisions": []}
            result = run(cfg, job["name"], lambda *args: {"text": json.dumps(value)})
            self.assertEqual(result["status"], "error")
            self.assertIn("omitted", result["error"])


if __name__ == "__main__":
    unittest.main()
