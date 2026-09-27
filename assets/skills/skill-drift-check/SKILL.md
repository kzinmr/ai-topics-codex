---
name: skill-drift-check
description: "Audit installed Codex wiki skill assets against their deployment hashes."
---

# skill-drift-check

Run python3 ~/.wiki-agent/scripts/check_skill_drift.py. Report modified/missing managed assets.
Edit authoritative assets in ai-topics-codex, review drift explicitly, then use sync-assets.
Do not overwrite local changes automatically or import unrelated operator skills. Inventory
looks at ~/.agents/skills and the managed source tree, not another agent's plugin registry.
