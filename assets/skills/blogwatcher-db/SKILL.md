---
name: blogwatcher-db
description: "Inspect RSS collection and dedup state using SQLite without changing ingestion flags."
---

# blogwatcher-db

Read ~/.blogwatcher/blogwatcher.db using a read-only SQLite connection. Inspect table schemas
before querying because CLI releases can differ. Compare source ID, URL and saved raw path
when diagnosing duplicates. Never reset read flags globally or copy a live DB without SQLite
online backup. Use the runner snapshot command for consistent transport of committed WAL data.
