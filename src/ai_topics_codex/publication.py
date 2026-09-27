"""Trusted publication and evidence checks, outside the model's write boundary."""

import hashlib
import os
from .process import execute


def evidence(cfg):
    result = {}
    for root in (
        cfg.repo / "wiki/raw",
        cfg.repo / "wiki/transcripts",
        cfg.repo / "transcripts",
    ):
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file():
                    result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_evidence(before):
    from pathlib import Path

    changed = []
    for name, digest in before.items():
        path = Path(name)
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            changed.append(name)
    if changed:
        raise RuntimeError(
            "Existing raw evidence changed; publication blocked: "
            + ", ".join(changed[:5])
        )


def git(cfg, *args):
    return execute(
        ["git", "-C", str(cfg.repo), *args], cwd=cfg.repo, env=cfg.env(), timeout=120
    )


def validate_wiki(cfg):
    for path in (cfg.repo / "wiki").rglob("*"):
        if path.is_symlink():
            raise RuntimeError(
                "Wiki symlink rejected before trusted post-processing: " + str(path)
            )


def preflight(cfg):
    validate_wiki(cfg)
    if cfg.local.get("publication", "local") != "local":
        if git(cfg, "status", "--porcelain"):
            raise RuntimeError(
                "Publication requires a clean content worktree; reconcile existing changes first"
            )


def publish(cfg, job, run):
    policy = cfg.local.get("publication", "local")
    if policy == "local":
        return {"policy": "local", "published": False}
    hook = cfg.repo / ".githooks/pre-commit"
    if (
        not hook.is_file()
        or not os.access(hook, os.X_OK)
        or git(cfg, "config", "core.hooksPath").strip() != ".githooks"
    ):
        raise RuntimeError(
            "Publication requires the executable content pre-commit hook"
        )
    # Preflight required a clean tree, so every change belongs to this locked run.
    changed = git(cfg, "diff", "--name-only", "-z").split("\0")
    changed += git(cfg, "diff", "--cached", "--name-only", "-z").split("\0")
    changed += git(cfg, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    changed = sorted(set(p for p in changed if p))
    if any(not p.startswith("wiki/") for p in changed):
        raise RuntimeError("Publication refuses changes outside wiki/")
    if not changed:
        return {"policy": policy, "published": False, "reason": "no changes"}
    git(cfg, "add", "--", *changed)
    # git commit executes the content repository hook; no bypass is supported.
    git(cfg, "commit", "-m", f"wiki: {job['name']} ({run})")
    commit = git(cfg, "rev-parse", "HEAD").strip()
    if policy == "push":
        git(cfg, "push", "origin", "HEAD")
    return {"policy": policy, "published": True, "commit": commit}
