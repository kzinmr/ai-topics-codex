---
name: blogwatcher
description: "Maintain RSS source definitions and collection with the profile blogwatcher database."
---

# blogwatcher

Feed selection lives in ~/ai-topics/config/feeds/blogs.opml. The runner provides blogwatcher-cli
and its HOME points at the profile. Use import_opml.py for initial import; inspect --help first.
Use the existing collector for scans. Mark an article read only after the body was saved.
Keep failed fetches unread. Do not run a second scan during a scheduled pre-collected job.
