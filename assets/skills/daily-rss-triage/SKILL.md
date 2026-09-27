---
name: daily-rss-triage
description: "Judge AI relevance and novelty in RSS, Hacker News and Reddit collection batches."
---

# daily-rss-triage

Prioritize original technical results, product releases, implementation lessons and substantive
analysis. Popularity is a discovery signal, not evidence. Exclude generic business news without
an AI connection. Compare against same-day blog/newsletter/dreaming output. A podcast title or
feed summary alone does not establish technical claims: fetch readable body/transcript or
mark the limitation. Keep the input item IDs and the strict triage schema.

Available deterministic helpers (inspect arguments and scope before using):
- [scripts/hn_algolia_supplement.py](scripts/hn_algolia_supplement.py)
- [scripts/hn_keyword_supplement.py](scripts/hn_keyword_supplement.py)
