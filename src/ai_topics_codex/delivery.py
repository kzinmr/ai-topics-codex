"""Local outbox is authoritative; delivery retries never rerun wiki work."""

import json
from pathlib import Path
from .config import json_write
from .process import execute


def enqueue(cfg, run, job, text):
    if not text.strip() or text.strip() == "NO_MESSAGE":
        return None
    path = cfg.state / "outbox" / f"{run}.json"
    json_write(
        path,
        {
            "version": 1,
            "run": run,
            "job": job["name"],
            "route": job["delivery"],
            "text": text,
            "status": "pending",
            "attempts": 0,
        },
    )
    return path


def deliver(cfg, path: Path):
    item = json.loads(path.read_text())
    if item["status"] == "delivered":
        return item
    route = cfg.local.get("delivery", {}).get(item["route"], {})
    if not route or route.get("kind", "outbox") == "outbox":
        return item
    # An explicit route enables this command. Transport credentials belong to this runner process.
    argv = route.get("command")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(x, str) for x in argv)
    ):
        raise ValueError(
            "delivery command must be an argv array; reads the JSON envelope on stdin"
        )
    item["attempts"] += 1
    try:
        execute(
            argv,
            cwd=cfg.profile,
            env=cfg.env(),
            timeout=route.get("timeout_seconds", 60),
            input=json.dumps(item, ensure_ascii=False),
        )
        item["status"] = "delivered"
        item.pop("error", None)
    except Exception as exc:
        item["status"] = "failed"
        item["error"] = str(exc)
    json_write(path, item)
    return item
