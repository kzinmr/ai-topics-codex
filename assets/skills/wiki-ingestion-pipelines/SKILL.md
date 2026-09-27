---
name: wiki-ingestion-pipelines
description: "Operate the collected-source to triage to wiki pipelines using durable checkpoints."
---

# wiki-ingestion-pipelines

Blog and newsletter pipelines each have collection, JSON triage and synthesis stages.
Dreaming has collection, theme grouping and synthesis. Read injected data, never rerun the
collector. The runner validates dependency success/freshness and checkpoint IDs. Do not use
older output to work around a failed upstream stage. Persistent checkpoints are under
~/.wiki-agent/checkpoints, outputs under ~/.wiki-agent/outputs/<job-name>.
After reading take sources, enrich existing pages and archive skip/reference decisions with
python3 ~/.wiki-agent/scripts/archive_triage.py <blog|newsletter|dreaming>. Check its output
and stage only new archive evidence and this job's Wiki edits. Preserve archive dedup state.

Available deterministic helpers (inspect arguments and scope before using):
- [scripts/prepend-log-entry.py](scripts/prepend-log-entry.py)
