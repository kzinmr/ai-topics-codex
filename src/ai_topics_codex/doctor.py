import hashlib
import importlib.util
import json
import os
import shutil
from .config import inside


def doctor(cfg, job=None):
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("initialized", (cfg.state / "profile.json").is_file())
    check(
        "canonical-wiki",
        cfg.wiki.is_dir() and cfg.wiki.resolve() == (cfg.repo / "wiki").resolve(),
    )
    for name in ("SCHEMA.md", "index.md", "log.md"):
        check("wiki/" + name, (cfg.wiki / name).is_file())
    check("native-profile", not (cfg.profile / ".hermes").exists())
    if (cfg.repo / ".git").exists():
        import subprocess

        hook = cfg.repo / ".githooks/pre-commit"
        check("content-hook", hook.is_file() and os.access(hook, os.X_OK))
        hooks = subprocess.run(
            ["git", "-C", str(cfg.repo), "config", "core.hooksPath"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        check(
            "content-hook-config",
            hooks == ".githooks",
            "must use content repository validation hooks",
        )
    selected = [cfg.job(job)] if job else [j for j in cfg.jobs if j["enabled"]]
    env = cfg.env()
    for mod in ("bs4", "httpx", "readability", "yaml", "requests"):
        check(
            "python:" + mod,
            importlib.util.find_spec(mod) is not None,
            "Install .[collectors] in the runner Python environment",
        )
    names = {j["name"] for j in selected}
    for binary, needed in [
        ("git", True),
        ("bash", True),
        ("blogwatcher-cli", "blog-ingest" in names),
        (
            "xurl",
            bool(names & {"x-bookmarks-ingest", "x-accounts-scan", "trending-topics"}),
        ),
    ]:
        if needed:
            check(
                "binary:" + binary, shutil.which(binary, path=env["PATH"]) is not None
            )
    if "newsletter-ingest" in names:
        for name in ("EMAIL_IMAP_HOST", "EMAIL_ADDRESS", "EMAIL_PASSWORD"):
            check("secret:" + name, bool(env.get(name)))
    if "ai-topics-slack-hot-posts" in names:
        for name in ("SLACK_BOT_TOKEN", "AI_TOPICS_SLACK_CHANNEL_ID"):
            check("secret:" + name, bool(env.get(name)))
    executable = cfg.local.get("codex", {}).get("executable", "codex")
    if any(not j["no_agent"] for j in selected):
        found = shutil.which(executable, path=env["PATH"]) is not None
        check("codex-binary", found)
        if found:
            from .codex import account_status
            from .sandbox import probe

            try:
                result = probe(cfg)
                check("native-sandbox", result["ok"], result)
            except Exception as exc:
                check("native-sandbox", False, str(exc))

            try:
                check("chatgpt-subscription", True, account_status(cfg))
            except Exception as exc:
                check("chatgpt-subscription", False, str(exc))
    manifest = cfg.state / "assets.json"
    if manifest.exists():
        changed = []
        for relative, digest in json.loads(manifest.read_text()).items():
            path = inside(cfg.profile, relative)
            if (
                not path.exists()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                changed.append(relative)
        check("managed-assets", not changed, ",".join(changed[:20]))
    else:
        check("managed-assets", False, "run init")
    secrets = cfg.state / "secrets.json"
    if secrets.exists():
        check(
            "secret-file-permissions",
            secrets.stat().st_mode & 0o077 == 0,
            "chmod 600 secrets.json",
        )
    return {
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "notes": [
            "Credentials are checked for presence, not network authentication. Delivery defaults to a local outbox."
        ],
    }
