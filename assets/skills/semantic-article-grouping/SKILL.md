---
name: semantic-article-grouping
description: "Triage collected RSS/newsletter articles and group related evidence for wiki ingestion."
---

# semantic-article-grouping

Use the supplied checkpoint and preserve its run_id as checkpoint_run_id. Read article bodies
before choosing take. Search existing Wiki coverage and today's log, including other pipeline
outputs, to avoid repeated work. take requires novel evidence; reference is useful context;
skip covers duplicates, irrelevant sources or unreadable material. State body access failures
in body_excerpt and reason_ja, never promote unreadable snippets to take. Preserve source IDs,
URLs and raw paths. Use the runner's strict JSON schema; one decision per item, no batch entries
that lose IDs. Return decisions even when every item is skip. The runner stores triage output;
a downstream ingest archives skip/reference with archive_triage.py. Do not repeat collection.
