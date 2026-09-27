# Lucy job inventory

UTC。30件、有効27件・停止3件。disabledは定時起動だけを止め、手動runは可能です。

| Job | Cron | Enabled | Collector | Dependencies |
|---|---|---|---|---|
| blog-triage | `20 10 * * *` | true | blog_checkpoint.py | blog-ingest |
| blog-wiki-ingest | `40 10 * * *` | true | blog_triage_checkpoint.py | blog-triage |
| blog-ingest | `0 10 * * *` | true | blog_ingest.py | — |
| check-skill-inventory | `0 16 * * 0` | true | check_new_skills.py | — |
| weekly-ai-digest | `0 0 * * 1` | true | — | — |
| dreaming-collect | `0 18 * * *` | true | dreaming_collect.py | — |
| dreaming-group | `10 18 * * *` | true | dreaming_checkpoint.py | dreaming-collect |
| dreaming-wiki-ingest | `20 18 * * *` | true | dreaming_group_checkpoint.py | dreaming-group |
| trending-topics | `0 12 * * *` | true | — | — |
| wiki-graph-analysis | `0 15 * * 5` | true | — | — |
| wiki-health | `0 17 * * *` | false | — | — |
| newsletter-ingest | `10 10 * * *` | true | process_email.py | — |
| newsletter-triage | `30 10 * * *` | true | newsletter_checkpoint.py | newsletter-ingest |
| newsletter-wiki-ingest | `50 10 * * *` | true | newsletter_triage_checkpoint.py | newsletter-triage |
| x-bookmarks-ingest | `30 11,23 * * *` | true | fetch_x_bookmarks.py | — |
| x-accounts-scan | `30 22 */2 * *` | true | fetch_x_accounts.py | — |
| skeleton-enrich-daily | `0 19 * * *` | true | — | — |
| wiki-health-plan | `10 17 * * *` | false | wiki_health.py | — |
| wiki-health-fix | `50 17 * * *` | true | wiki_health_json.py | — |
| ai-topics-slack-hot-posts | `30 0,12,18 * * *` | true | ai_topics_slack_hot_posts_context.py | — |
| active-crawl | `0 11 * * *` | true | — | — |
| sitemap-monitor | `0 6 * * *` | true | sitemap_monitor.py | — |
| tag-audit-weekly | `0 10 * * 1` | true | tag_audit.py | — |
| pipeline-watchdog | `0 0,6,12,18 * * *` | true | pipeline_watchdog.py | — |
| wiki-watchdog-fix | `35 17 * * *` | true | wiki_watchdog_fix_context.py | — |
| raw-backlog-ingest | `0 0,4,10,14,18,22 * * *` | false | raw_backlog_collect_cron.sh | — |
| jp-to-en-translation | `0 0 * * 0` | true | — | — |
| skill-drift-check | `0 10 * * 1` | true | — | — |
| llm-pricing-monitor | `0 10 * * 1` | true | — | — |
| hierarchy-candidate-detection | `0 15 * * 3` | true | — | — |
