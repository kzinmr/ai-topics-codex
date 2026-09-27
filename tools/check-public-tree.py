#!/usr/bin/env python3
"""Check source artifacts for embedded credentials and forbidden canonical paths.

Optionally compare exact credential values from a legacy .env without displaying
those values. Never export source secrets or state to a public repository.
"""

import argparse
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--legacy-profile", type=Path)
args = p.parse_args()
values = []
if args.legacy_profile:
    for file in (args.legacy_profile / ".hermes/.env", args.legacy_profile / ".env"):
        if file.exists():
            for line in file.read_text().splitlines():
                key, sep, value = line.partition("=")
                if sep and re.search(r"TOKEN|SECRET|PASSWORD|API_KEY", key, re.I):
                    value = value.strip().strip("\"'")
                    if len(value) > 8:
                        values.append(value)
files = (
    subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    )
    .decode()
    .split("\0")
)
issues = []
for name in files:
    file = root / name
    if not file.is_file():
        continue
    try:
        text = file.read_text()
    except UnicodeDecodeError:
        continue
    for value in values:
        if value in text:
            issues.append((name, "matches a source credential"))
    if re.search(
        r"(?<![a-zA-Z0-9_-])(?:sk-[a-zA-Z0-9_-]{24,}|gh[pousr]_[a-zA-Z0-9]{25,}|xox[baprs]-[a-zA-Z0-9-]{20,}|AKIA[0-9A-Z]{16})",
        text,
    ):
        issues.append((name, "credential-like literal"))
    if name.startswith("assets/") and re.search(
        r"/opt/(?:data|hermes)|/srv/hermes|/home/exedev|~/home/wiki|~/.wiki-agent/home/wiki",
        text,
    ):
        issues.append((name, "runtime-specific path in operational assets"))
    if (
        name.startswith(("profiles/", ".local/", "backups/"))
        or file.name.startswith(".env")
        and file.name != ".env.example"
    ):
        issues.append((name, "private file in public tree"))
for name, reason in sorted(set(issues)):
    print(f"{name}: {reason}")
print(
    f"Checked {len(files) - 1} source files; {len(set(issues))} findings (no credential values printed)."
)
raise SystemExit(bool(issues))
