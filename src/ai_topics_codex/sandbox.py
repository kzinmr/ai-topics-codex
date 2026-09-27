"""Codex native permission profiles, shared by jobs, chat and non-model probes.

Do not send legacy sandboxPolicy overrides: they replace the finer filesystem
policy on Codex 0.157.1. The App Server inherits this named profile instead.
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import shutil
import sys
import tempfile

PROFILE = "wiki-native"
RESEARCH_JOBS = frozenset(
    {
        "active-crawl",
        "trending-topics",
        "x-bookmarks-ingest",
        "x-accounts-scan",
        "skeleton-enrich-daily",
        "llm-pricing-monitor",
        "dreaming-collect",
    }
)


def settings(cfg, job=None):
    options = cfg.local.get("codex", {})
    name = job["name"] if job else None
    network_jobs = options.get("network_jobs", sorted(RESEARCH_JOBS))
    network = name in network_jobs
    scratch = cfg.state / "work"
    scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
    # No root/home/tmp read grant. Existing source trees are read-only; only
    # content and scratch are writable, including when cwd is the repository.
    fs = {
        ":minimal": "read",
        str(cfg.repo): "read",
        str(cfg.repo / "wiki"): "write",
        str(scratch): "write",
        str(cfg.skills): "read",
        str(cfg.runtime / "scripts"): "read",
        str(cfg.runtime / "checkpoints"): "read",
        str(cfg.runtime / "outputs"): "read",
        str(cfg.state / "assets.json"): "read",
        str(cfg.state / "jobs-view.json"): "read",
    }
    # Python may be installed by uv/mise outside the system platform roots.
    for path in (
        Path(sys.executable).parent.parent,
        Path(sys.executable).resolve().parent.parent,
    ):
        fs[str(path)] = "read"
    executable = shutil.which(
        options.get("executable", "codex"), path=cfg.env()["PATH"]
    )
    if executable:
        entry = Path(executable).resolve()
        # npm's launcher invokes its packaged native helper from node_modules.
        package = entry.parent.parent
        fs[str(package if (package / "package.json").is_file() else entry)] = "read"
    # Source code, secrets, auth, Git metadata, state and other profiles are not
    # made writable. Explicit denies also cover accidental nested auth paths.
    for path in (
        cfg.profile / ".codex",
        Path(cfg.env()["CODEX_HOME"]),
        cfg.state / "secrets.json",
        cfg.state / "local.json",
        cfg.repo / "config/hermes",
        cfg.repo / ".codex",
        cfg.repo / ".agents",
    ):
        fs[str(path)] = "deny"
    for root in (cfg.repo, cfg.skills, cfg.runtime / "scripts"):
        fs[str(root / "**/.env*")] = "deny"
    # Research jobs add new evidence. Editing/triage jobs cannot change raw.
    # Existing-evidence preservation for research is checked by the runner.
    if name not in RESEARCH_JOBS:
        fs[str(cfg.repo / "wiki/raw")] = "read"
    fs[str(cfg.repo / "wiki/transcripts")] = "read"
    if name in {"blog-triage", "newsletter-triage", "dreaming-group"}:
        fs[str(cfg.repo / "wiki")] = "read"
    return {
        "default_permissions": PROFILE,
        "permissions": {PROFILE: {"filesystem": fs, "network": {"enabled": network}}},
        "approval_policy": "never",
        "allow_login_shell": False,
        "features.shell_snapshot": False,
        "features.apps": False,
        "features.browser_use": False,
        "features.plugins": False,
    }


def toml(value):
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(json.dumps(k) + "=" + toml(v) for k, v in value.items())
            + "}"
        )
    return json.dumps(value, ensure_ascii=False)


def arguments(cfg, job=None):
    args = []
    for key, value in settings(cfg, job).items():
        args += ["-c", key + "=" + toml(value)]
    return args


def probe(cfg):
    """Exercise the actual App Server sandbox without tokens or live secrets."""
    from .codex import command, connect, _codex_request

    env = cfg.env()
    options = cfg.local.get("codex", {})
    # Canary files contain no credentials and are cleaned even on failure.
    with tempfile.TemporaryDirectory(
        prefix="sandbox-probe-", dir=cfg.state
    ) as directory:
        control = Path(directory) / "control"
        control.write_text("synthetic private control")
        script = cfg.runtime / "scripts" / (".probe-" + Path(directory).name)
        script.write_text("synthetic operational code")
        auth = cfg.profile / ".codex" / (".probe-" + Path(directory).name)
        auth.parent.mkdir(exist_ok=True, mode=0o700)
        auth.write_text("synthetic authentication")
        link = cfg.repo / "wiki" / (".probe-link-" + Path(directory).name)
        link.symlink_to(control)
        raw_dir = cfg.repo / "wiki/raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".sandbox-probe-", dir=raw_dir
        ) as raw_temp:
            raw = Path(raw_temp) / "evidence"
            raw.write_text("synthetic evidence")
            # A host-local listener makes the denial check independent of DNS or internet outages.
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen()
                port = listener.getsockname()[1]
                code = """import json, pathlib, socket
control, raw, wiki, scratch, port, script, auth, link = INPUT
results = {}
for key, path, action in [
 ("control_read_denied", control, "read"),
 ("control_write_denied", control, "write"),
 ("raw_write_denied", raw, "write"),
 ("script_write_denied", script, "write"),
 ("auth_read_denied", auth, "read"),
 ("symlink_escape_denied", link, "read"),
]:
 try:
  p=pathlib.Path(path)
  p.read_text() if action == "read" else p.write_text("blocked mutation")
  results[key]=False
 except OSError: results[key]=True
for key, path in [("wiki_write_allowed", wiki), ("scratch_write_allowed", scratch)]:
 try:
  p=pathlib.Path(path); p.write_text("probe"); results[key]=p.read_text()=="probe"; p.unlink()
 except OSError: results[key]=False
try:
 s=socket.create_connection(("127.0.0.1", port), timeout=2); s.close(); results["network_denied"]=False
except OSError: results["network_denied"]=True
print(json.dumps(results))
"""
                wiki = cfg.repo / "wiki" / (".probe-" + Path(directory).name)
                scratch = cfg.state / "work" / (".probe-" + Path(directory).name)
                code = code.replace(
                    "INPUT",
                    repr(
                        [
                            str(control),
                            str(raw),
                            str(wiki),
                            str(scratch),
                            port,
                            str(script),
                            str(auth),
                            str(link),
                        ]
                    ),
                )
                stream = None
                try:
                    stream = connect(command(options, cfg), cfg.repo, env, 30)
                    result, _ = _codex_request(
                        stream,
                        40,
                        "command/exec",
                        {
                            "command": [sys.executable, "-c", code],
                            "cwd": str(cfg.repo),
                            "timeoutMs": 10000,
                        },
                    )
                    if result.get("exitCode") != 0:
                        raise RuntimeError(
                            "Native sandbox probe failed: "
                            + result.get("stderr", "")[-2000:]
                        )
                    checks = json.loads(result["stdout"])
                    checks["raw_preserved"] = raw.read_text() == "synthetic evidence"
                    checks["control_preserved"] = (
                        control.read_text() == "synthetic private control"
                    )
                    return {"ok": all(checks.values()), "checks": checks}
                finally:
                    if stream is not None:
                        stream.close()
                    wiki.unlink(missing_ok=True)
                    scratch.unlink(missing_ok=True)
                    script.unlink(missing_ok=True)
                    auth.unlink(missing_ok=True)
                    link.unlink(missing_ok=True)
