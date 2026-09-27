---
name: wiki-graph-health
description: "Audit and repair wiki links, frontmatter, index coverage and graph structure."
---

# wiki-graph-health

Start with python3 ~/.wiki-agent/scripts/wiki_health.py --json. Check graph findings against
actual files and SCHEMA.md. Distinguish a real missing page from a bare-link resolver issue,
heading/anchor syntax, alias or index parsing error. Repair small verified batches, run health
again and compare counts. Never mass-delete or rewrite rich pages to improve a metric.
Inspect helper scripts before running a mutating mode; shell globs and replacements can alter
raw evidence. Link corrections must include backlinks, section indexes and the main index.

Available deterministic helpers (inspect arguments and scope before using):
- [scripts/add_updated_dates.py](scripts/add_updated_dates.py)
- [scripts/batch_register_orphans.py](scripts/batch_register_orphans.py)
- [scripts/deep_link_audit.py](scripts/deep_link_audit.py)
- [scripts/fix-weekly-graph-analysis.py](scripts/fix-weekly-graph-analysis.py)
- [scripts/fix_broken_wikilinks.py](scripts/fix_broken_wikilinks.py)
- [scripts/fix_empty_wikilinks_safe.py](scripts/fix_empty_wikilinks_safe.py)
- [scripts/fix_log_header_burial.py](scripts/fix_log_header_burial.py)
- [scripts/fix_wikilinks.py](scripts/fix_wikilinks.py)
- [scripts/tag_audit.py](scripts/tag_audit.py)
- [scripts/tag_normalization.py](scripts/tag_normalization.py)
- [scripts/tag_normalization_diff_scan.py](scripts/tag_normalization_diff_scan.py)
- [scripts/yaml_validate_frontmatter.py](scripts/yaml_validate_frontmatter.py)
