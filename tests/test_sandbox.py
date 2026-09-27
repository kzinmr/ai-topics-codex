"""Boundary regression tests; the real kernel probe also runs in CI."""

import tempfile
import unittest
from pathlib import Path
from ai_topics_codex.config import Config, json_write
from ai_topics_codex.profile import initialize
from ai_topics_codex.sandbox import settings, PROFILE
from ai_topics_codex.codex import codex_env, command
from ai_topics_codex.publication import evidence, verify_evidence, preflight, publish
import subprocess

SOURCE = Path(__file__).resolve().parents[1]


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cfg = Config(SOURCE, Path(self.temp.name) / "profile")
        initialize(self.cfg)

    def tearDown(self):
        self.temp.cleanup()

    def test_no_container_or_unbounded_network_fallback(self):
        for codex in (
            {"sandbox": "external"},
            {"sandbox": "danger-full-access"},
            {"network_access": True},
        ):
            json_write(self.cfg.local_path, {"codex": codex})
            with self.assertRaises(ValueError):
                Config(SOURCE, self.cfg.profile)

    def test_sensitive_paths_are_not_writable_or_readable(self):
        policy = settings(self.cfg)["permissions"][PROFILE]
        fs = policy["filesystem"]
        self.assertNotIn(str(self.cfg.profile), fs)
        self.assertNotIn(str(self.cfg.state), fs)
        self.assertNotIn("/", fs)
        self.assertNotIn("/tmp", fs)
        self.assertEqual(fs[str(self.cfg.state / "secrets.json")], "deny")
        self.assertEqual(fs[str(self.cfg.profile / ".codex")], "deny")
        self.assertEqual(fs[str(self.cfg.runtime / "scripts")], "read")
        self.assertFalse(policy["network"]["enabled"])

    def test_triage_cannot_edit_content_and_research_is_explicit(self):
        def policy(name):
            return settings(self.cfg, self.cfg.job(name))["permissions"][PROFILE]

        self.assertEqual(
            policy("blog-triage")["filesystem"][str(self.cfg.repo / "wiki")], "read"
        )
        self.assertEqual(
            policy("blog-wiki-ingest")["filesystem"][str(self.cfg.repo / "wiki/raw")],
            "read",
        )
        self.assertTrue(policy("active-crawl")["network"]["enabled"])
        self.cfg.local = {"codex": {"network_jobs": []}}
        self.assertFalse(policy("active-crawl")["network"]["enabled"])

    def test_arbitrary_source_credentials_are_not_inherited(self):
        self.assertEqual(
            codex_env(
                {
                    "HOME": "/profile",
                    "SOME_NEW_SECRET": "secret",
                    "GITHUB_TOKEN": "secret",
                    "AWS_SESSION_TOKEN": "secret",
                    "SSH_AUTH_SOCK": "/sock",
                }
            ),
            {"HOME": "/profile"},
        )

    def test_auth_outside_profile_is_explicitly_denied(self):
        self.cfg.local = {"codex": {"auth_home": str(Path(self.temp.name) / "auth")}}
        fs = settings(self.cfg)["permissions"][PROFILE]["filesystem"]
        self.assertEqual(fs[str(Path(self.temp.name) / "auth")], "deny")
        self.assertIn('default_permissions="wiki-native"', command({}, self.cfg))

    def test_evidence_changes_block_publication(self):
        raw = self.cfg.wiki / "raw/source.md"
        raw.parent.mkdir()
        raw.write_text("original")
        original = evidence(self.cfg)
        (raw.parent / "new.md").write_text("new evidence")
        verify_evidence(original)
        raw.write_text("altered")
        with self.assertRaisesRegex(RuntimeError, "publication blocked"):
            verify_evidence(original)

    def test_publication_preserves_unrelated_work(self):
        subprocess.run(["git", "init", "-q", str(self.cfg.repo)], check=True)
        self.cfg.local = {"publication": "commit"}
        with self.assertRaisesRegex(RuntimeError, "clean content worktree"):
            preflight(self.cfg)
        self.cfg.local = {"publication": "local"}
        self.assertFalse(
            publish(self.cfg, self.cfg.job("blog-ingest"), "fixture")["published"]
        )

    def test_runner_commits_with_hook_and_rejects_unrelated_changes(self):
        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(self.cfg.repo), *args], text=True
            )

        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        hook = self.cfg.repo / ".githooks/pre-commit"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\nprintf checked > .git/hook-checked\n")
        hook.chmod(0o755)
        git("config", "core.hooksPath", ".githooks")
        git("add", ".")
        git("commit", "-qm", "fixture")
        self.cfg.local = {"publication": "commit"}
        preflight(self.cfg)
        (self.cfg.wiki / "page.md").write_text("new page")
        result = publish(self.cfg, self.cfg.job("blog-ingest"), "fixture-run")
        self.assertTrue(result["published"])
        self.assertEqual(git("status", "--porcelain"), "")
        self.assertTrue((self.cfg.repo / ".git/hook-checked").exists())
        (self.cfg.repo / "unrelated").write_text("preserve")
        with self.assertRaisesRegex(RuntimeError, "outside wiki"):
            publish(self.cfg, self.cfg.job("blog-ingest"), "fixture-other")

    def test_wiki_symlink_never_reaches_trusted_processing(self):
        from ai_topics_codex.publication import validate_wiki

        (self.cfg.wiki / "unsafe").symlink_to(self.cfg.state / "secrets.json")
        with self.assertRaisesRegex(RuntimeError, "symlink rejected"):
            validate_wiki(self.cfg)
