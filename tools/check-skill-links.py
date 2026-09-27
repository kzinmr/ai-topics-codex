#!/usr/bin/env python3
"""Report inherited local reference gaps; does not execute skill instructions."""

from pathlib import Path
import re
import yaml

root = Path(__file__).resolve().parents[1] / "assets/skills"
missing = set()
for file in root.glob("*/SKILL.md"):
    text = file.read_text()
    try:
        header = yaml.safe_load(text.split("---", 2)[1])
        if (
            header.get("name") != file.parent.name
            or not isinstance(header.get("description"), str)
            or not header["description"].strip()
        ):
            raise ValueError("name/description invalid")
    except (IndexError, ValueError, AttributeError, yaml.YAMLError):
        missing.add((file.parent.name, "invalid Codex skill frontmatter"))
    for rel in re.findall(
        r"(?<![/\w])(?:references|scripts)/[A-Za-z0-9_.-]+\.(?:md|py|sh)",
        file.read_text(),
    ):
        if not (file.parent / rel).exists():
            missing.add((file.parent.name, rel))
for skill, rel in sorted(missing):
    print(skill, rel)
print("Missing local reference targets:", len(missing))

raise SystemExit(bool(missing))
