#!/usr/bin/env python3
"""Read the runner's validated JSON handoff, not rendered model prose."""
import json, os
from pathlib import Path
from ai_topics_codex.config import json_write

def main():
    state=Path(os.environ.get('WIKI_AGENT_HOME',Path.home()/'.wiki-agent'))
    source=state/'outputs/blog-triage/latest.json'
    if not source.exists():
        print(json.dumps({'ok':False,'error':'blog-triage structured output missing'}));return 1
    data=json.loads(source.read_text())
    json_write(state/'checkpoints/blog_ingest/triage_latest.json',data)

    print(json.dumps(data,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
