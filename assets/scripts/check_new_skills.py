#!/usr/bin/env python3
"""Report native skill inventory relative to the installed asset manifest."""
import json,os
from pathlib import Path
from portable_paths import profile_root

def main():
    root=profile_root();state=root/'.wiki-agent'
    installed={p.parent.name for p in (root/'.agents/skills').glob('*/SKILL.md')}
    manifest=json.loads((state/'assets.json').read_text())
    managed={Path(p).parent.name for p in manifest if p.startswith('.agents/skills/') and p.endswith('/SKILL.md')}
    print(json.dumps({'managed':len(managed),'installed':len(installed),
                      'unmanaged':sorted(installed-managed),'missing':sorted(managed-installed)},indent=2))

if __name__=='__main__':main()
