#!/usr/bin/env python3
"""Run the structured health collector; propagate failures to the runner."""
import subprocess
import sys
from pathlib import Path
result = subprocess.run([sys.executable, str(Path(__file__).parent / "wiki_health.py"), "--json"],
                        capture_output=True, text=True, timeout=120)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
raise SystemExit(result.returncode)
