#!/usr/bin/env python3
"""Opt-in real-model acceptance against an isolated synthetic wiki, never production."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ai_topics_codex.config import Config, json_write
from ai_topics_codex.profile import initialize
from ai_topics_codex.runner import run
from ai_topics_codex.state import Store
from ai_topics_codex.sandbox import probe

p = argparse.ArgumentParser(description=__doc__)
p.add_argument(
    "--live",
    action="store_true",
    required=True,
    help="Explicitly spend subscription usage on synthetic acceptance",
)
p.add_argument(
    "--auth-home",
    type=Path,
    required=True,
    help="Existing ChatGPT login directory; credentials are not copied",
)
a = p.parse_args()
# OS temp directories can carry implicit sandbox access (observed on macOS).
# Keep the profile under ignored development state and verify the real boundary
# before spending model usage or opening the existing authentication directory.
scratch = Path(__file__).resolve().parents[1] / ".local" / "smoke-profiles"
scratch.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="wiki-codex-acceptance-", dir=scratch) as temp:
    cfg = Config(profile=Path(temp))
    initialize(cfg)
    cfg.local = {
        "codex": {"auth_home": str(a.auth_home.resolve()), "web_search": "disabled"},
        "publication": "local",
    }
    boundary = probe(cfg)
    if not boundary["ok"]:
        raise RuntimeError({"sandbox_probe": boundary})
    subprocess.run(["git", "init", "-q", str(cfg.repo)], check=True)
    (cfg.wiki / "SCHEMA.md").write_text("""# Schema
Curated pages are English. Use title, created, updated, type, tags and sources
frontmatter. Allowed tags: ai, inference. Concepts live in concepts/. Every new
page needs source evidence and index/log updates. Raw files are immutable.
""")
    (cfg.wiki / "index.md").write_text("# Wiki index\n\n## Concepts\n")
    (cfg.wiki / "log.md").write_text("# Wiki log\n")
    raw = cfg.wiki / "raw/articles/2026-09-27_fixture_cache.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("""---
title: Fixture Cache experiment
source: https://example.invalid/fixture-cache
created: 2026-09-27
---
This synthetic acceptance source describes Fixture Cache, an LLM inference cache.
In the stated local experiment it reduced repeated prompt processing from 40 ms
to 25 ms for identical prompts. This is a synthetic observation, not a real-world
benchmark or a general performance guarantee. It caches only exact prompt matches
and invalidates entries when the model version changes.
""")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    json_write(
        cfg.runtime / "checkpoints/blog_ingest/latest.json",
        {
            "run_id": "acceptance-fixture",
            "date": "2026-09-27",
            "saved_articles": [
                {
                    "blog": "Fixture",
                    "title": "Fixture Cache experiment",
                    "source": "blog",
                    "source_name": "Fixture",
                    "url": "https://example.invalid/fixture-cache",
                    "raw_path": str(raw),
                }
            ],
        },
    )
    # A source script already completed; seed its successful dependency record.
    store = Store(cfg.state)
    now = datetime.now(timezone.utc).isoformat()
    store.start("fixture-source", "blog-ingest", now)
    store.finish("fixture-source", now, "ok", {})
    store.close()
    instructions = cfg.profile / "acceptance-triage.md"
    instructions.write_text("""This is a synthetic acceptance test, not public factual research.
Read the injected checkpoint and its local raw article. Choose take for blog-1
because its content is new to this empty test Wiki. Return the required triage JSON
with checkpoint_run_id acceptance-fixture, raw_path matching the actual saved file,
and candidate_wiki_path concepts/fixture-cache.md. Do not browse, message or publish.
""")
    cfg.job("blog-triage")["prompt"] = str(instructions)
    triage = run(cfg, "blog-triage")
    if triage["status"] != "ok":
        raise RuntimeError(triage)
    output = json.loads((cfg.runtime / "outputs/blog-triage/latest.json").read_text())
    assert output["decisions"][0]["recommended_action"] == "take", output
    instructions = cfg.profile / "acceptance-ingest.md"
    instructions.write_text("""This is a synthetic acceptance test. Use the supplied validated triage
JSON and read the local source body. Create concepts/fixture-cache.md with required
frontmatter, exact source URL, the 40 ms to 25 ms observation and its synthetic,
non-generalizable limitation. Add it to index.md and append a log entry. Do not
edit raw evidence. Do not browse, commit, push or send messages. Report what changed.
""")
    cfg.job("blog-wiki-ingest")["prompt"] = str(instructions)
    ingest = run(cfg, "blog-wiki-ingest")
    if ingest["status"] != "ok":
        raise RuntimeError(ingest)
    page = cfg.wiki / "concepts/fixture-cache.md"
    text = page.read_text()
    assert "40" in text and "25" in text and "synthetic" in text.lower(), text
    assert "https://example.invalid/fixture-cache" in text, text
    assert "fixture-cache" in (cfg.wiki / "index.md").read_text()
    assert len((cfg.wiki / "log.md").read_text()) > len("# Wiki log\n")
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == digest
    assert not (cfg.profile / ".hermes").exists()
    print(
        json.dumps(
            {
                "ok": True,
                "triage": triage["status"],
                "ingest": ingest["status"],
                "raw_preserved": True,
                "index_and_log_updated": True,
                "usage": [triage.get("usage"), ingest.get("usage")],
            },
            indent=2,
        )
    )
