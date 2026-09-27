import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "assets/scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CollectorTest(unittest.TestCase):
    def test_failed_scrape_is_not_acknowledged(self):
        m = load("blog_ingest")
        items = [
            {"url": "https://ok", "blog": "ok"},
            {"url": "https://failed", "blog": "bad"},
        ]

        def scrape(url):
            return (
                {"title": "saved", "url": url, "content": "body", "fetched_at": "now"}
                if url.endswith("ok")
                else None
            )

        with (
            patch.object(m, "scrape_url", side_effect=scrape),
            patch.object(m, "save_article", return_value="raw.md"),
            patch.object(m, "_mark_articles_as_read") as mark,
        ):
            saved, unsaved = m.persist_blog_articles({"blog_articles": items})
            self.assertEqual(len(saved), 1)
            self.assertEqual(len(unsaved), 1)
            self.assertEqual(mark.call_args.args[0], saved)

    def test_raw_article_is_immutable(self):
        m = load("blog_ingest")
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(m, "RAW_ARTICLES_DIR", Path(temp)),
        ):
            raw = {
                "title": "original",
                "url": "https://example.com",
                "content": "original",
                "fetched_at": "now",
            }
            path = Path(m.save_article(raw, "fixture"))
            original = path.read_bytes()
            raw["content"] = "changed"
            m.save_article(raw, "fixture")
            self.assertEqual(path.read_bytes(), original)

    def test_empty_mailbox_replaces_stale_checkpoint(self):
        class Mailbox:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def login(self, *a):
                return "OK", []

            def create(self, *a):
                return "OK", []

            def select(self, *a):
                return "OK", []

            def uid(self, *a):
                return "OK", [b""]

            def expunge(self):
                return "OK", []

        with (
            tempfile.TemporaryDirectory() as temp,
            patch.dict(
                os.environ,
                {"WIKI_PROFILE_ROOT": temp, "WIKI_AGENT_HOME": temp + "/.wiki-agent"},
            ),
        ):
            m = load("process_email")
            m.CHECKPOINT_DIR.mkdir(parents=True)
            m.LATEST_CHECKPOINT.write_text('{"processed_count":99}')
            with (
                patch.object(m, "_require_env"),
                patch.object(m.imaplib, "IMAP4_SSL", return_value=Mailbox()),
            ):
                result = m.process_all_unseen()
            self.assertEqual(result["processed_count"], 0)
            self.assertEqual(
                json.loads(m.LATEST_CHECKPOINT.read_text())["processed_count"], 0
            )
            self.assertIn("run_id", result)

    def test_sitemap_only_acknowledges_saved_articles(self):
        m = load("sitemap_monitor")
        articles = [{"url": "https://one"}, {"url": "https://two"}]
        with (
            patch.object(m, "fetch_sitemap", return_value="xml"),
            patch.object(m, "parse_sitemap", return_value=articles),
            patch.object(m, "load_state", return_value=set()),
            patch.object(
                m, "scrape_article", return_value={"url": "https://one", "title": "one"}
            ),
            patch.object(m, "save_raw_article", return_value="raw.md"),
            patch.object(m, "save_state") as save,
            patch.object(m, "MAX_ARTICLES_PER_SOURCE", 1),
        ):
            m.process_source(
                {
                    "name": "fixture",
                    "url": "https://site",
                    "sitemap_url": "https://sitemap",
                    "url_pattern": "",
                    "state_file": "state",
                    "file_prefix": "fixture",
                }
            )
            self.assertEqual(save.call_args.args[1], {"https://one"})

    def test_health_json_skips_expensive_markdown_sections(self):
        m = load("wiki_health")
        from io import StringIO

        with (
            patch.object(m, "load_l2_pages", return_value={}),
            patch.object(m, "load_raw_articles", return_value=[]),
            patch.object(
                m,
                "section_unprocessed_raw",
                side_effect=AssertionError("should not run"),
            ),
            patch.object(sys, "argv", ["wiki_health.py", "--json"]),
            patch("sys.stdout", new_callable=StringIO) as stdout,
        ):
            m.main()
            self.assertIn("overview", json.loads(stdout.getvalue()))


if __name__ == "__main__":
    unittest.main()
