#!/usr/bin/env python3
# HN keyword supplement; usage: script.py [days] [min_points]
import urllib.request, urllib.parse, json, sys, datetime
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())
days = int(sys.argv[1]) if len(sys.argv) > 1 else 4
minpts = int(sys.argv[2]) if len(sys.argv) > 2 else 80
cutoff = int(datetime.datetime.now(datetime.UTC).timestamp()) - days*86400
seen = set()
# Extend this list per-run with today's hot topic keywords (see tip above).
queries = ["AI agent", "Claude", "OpenAI", "LLM", "open weights", "model release",
           "prompt injection", "AI safety", "coding agent", "MCP", "Anthropic"]
for q in queries:
    try:
        d = get(f"https://hn.algolia.com/api/v1/search?query={urllib.request.quote(q)}"
                f"&tags=story&numericFilters=created_at_i%3E{cutoff},points%3E{minpts}")
    except Exception as e:
        print(q, "ERR", e); continue
    for h in d.get('hits', [])[:5]:
        oid = h.get('objectID')
        if oid in seen: continue
        seen.add(oid)
        print(f"[{h.get('created_at','')[:10]} {h.get('points')}pts/{h.get('num_comments')}c] {h.get('title')}")
        print(f"    ext: {h.get('url')}")
        print(f"    hn : https://news.ycombinator.com/item?id={oid}")
