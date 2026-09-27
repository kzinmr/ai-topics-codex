"""Validate the strict JSON subset used by Codex outputSchema and handoff files."""

import json
from pathlib import Path


def validate(value, schema, path="$"):
    types = schema["type"]
    types = types if isinstance(types, list) else [types]
    actual = (
        "null"
        if value is None
        else "boolean"
        if isinstance(value, bool)
        else "object"
        if isinstance(value, dict)
        else "array"
        if isinstance(value, list)
        else "string"
        if isinstance(value, str)
        else "number"
    )
    if actual not in types:
        raise ValueError(f"{path}: expected {types}, got {actual}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: invalid enum value")
    if actual == "object":
        missing = set(schema["required"]) - value.keys()
        if missing:
            raise ValueError(f"{path}: missing {sorted(missing)}")
        extra = value.keys() - schema["properties"].keys()
        if extra:
            raise ValueError(f"{path}: unexpected {sorted(extra)}")
        for key, item in value.items():
            validate(item, schema["properties"][key], path + "." + key)
    elif actual == "array":
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")


def response_schema(cfg, job):
    return json.loads(
        (
            cfg.source
            / "config/schemas"
            / ("groups.json" if job["name"] == "dreaming-group" else "triage.json")
        ).read_text()
    )


def validate_handoff(cfg, job, value):
    validate(value, response_schema(cfg, job))
    ids = set()
    for decision in value["decisions"]:
        key = decision["item_id"]
        if not key or key in ids:
            raise ValueError("decision IDs must be nonempty and unique")
        ids.add(key)
        if decision["recommended_action"] == "take":
            raw = decision["raw_path"]
            if not raw:
                raise ValueError("take requires a saved source body")
            if raw.startswith("~/"):
                raw = str(cfg.profile / raw[2:])
            file = Path(raw).resolve()
            roots = [
                (cfg.wiki / "raw").resolve(),
                cfg.repo / "inbox",
                cfg.repo / "transcripts",
            ]
            if not file.is_file() or not any(
                file.is_relative_to(root) for root in roots
            ):
                raise ValueError(
                    "take raw_path must be an existing source inside this profile"
                )
    for group in value.get("groups", []):
        if not set(group["item_ids"]) <= ids:
            raise ValueError("group references unknown decision IDs")
