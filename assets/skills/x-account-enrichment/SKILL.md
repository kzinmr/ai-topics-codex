---
name: x-account-enrichment
description: "Enrich tracked X author entities using verified posts and linked primary material."
---

# x-account-enrichment

Tracked accounts live in ~/ai-topics/config/feeds/x-accounts.yaml. Use supplied post IDs and
resolve linked evidence. Verify person/organization identity and current affiliations rather
than inferring from a handle. Distinguish a quoted claim from the author's own statement.
Use build_x_wiki.py only to create absent skeletons, never overwrite existing rich pages.
