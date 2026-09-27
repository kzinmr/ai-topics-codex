#!/usr/bin/env python3
"""Report measured Codex tokens from the ledger; subscription cost is not inferred."""
import json,os,sqlite3
from pathlib import Path

def main():
    state=Path(os.environ.get('WIKI_AGENT_HOME',Path.home()/'.wiki-agent'))
    rows=[]
    if (state/'runs.db').exists():
        db=sqlite3.connect((state/'runs.db').as_uri()+'?mode=ro',uri=True)
        try:
            for run,job,status,detail in db.execute('SELECT id,job,status,detail FROM runs ORDER BY started'):
                rows.append({'run':run,'job':job,'status':status,'usage':json.loads(detail).get('usage')})
        finally:db.close()
    print(json.dumps({'runs':rows,'billing':'ChatGPT subscription; no inferred API cost'},indent=2))

if __name__=='__main__':main()
