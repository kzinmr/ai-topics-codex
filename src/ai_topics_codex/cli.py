from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from .config import Config
from .state import Store, profile_lock


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description="Codex-native AI wiki operations (Lucy)")
    p.add_argument("--source", type=Path)
    p.add_argument("--profile", type=Path)
    p.add_argument("--local", type=Path)
    subs = p.add_subparsers(dest="action", required=True)
    subs.add_parser("login")
    subs.add_parser("account")
    subs.add_parser("chat")
    subs.add_parser("sandbox-check")
    subs.add_parser("validate")
    subs.add_parser("jobs")
    init = subs.add_parser("init")
    g = init.add_mutually_exclusive_group()
    g.add_argument("--content-source", type=Path)
    g.add_argument("--clone", action="store_true")
    subs.add_parser("sync-assets")
    doctor = subs.add_parser("doctor")
    doctor.add_argument("--job")
    run = subs.add_parser("run")
    run.add_argument("job")
    run.add_argument("--dry-run", action="store_true")
    prompt = subs.add_parser("prompt")
    prompt.add_argument("job")
    subs.add_parser("tick")
    subs.add_parser("serve")
    subs.add_parser("status")
    replay = subs.add_parser("retry")
    replay.add_argument("run_id")
    recover = subs.add_parser("recover")
    recover.add_argument("run_id")
    subs.add_parser("reset-cursor")
    snap = subs.add_parser("snapshot")
    snap.add_argument("destination", type=Path)
    snap.add_argument("--legacy", action="store_true")
    snap.add_argument("--quiesced", action="store_true")
    snap.add_argument("--include-content", action="store_true")
    restore = subs.add_parser("restore")
    restore.add_argument("bundle", type=Path)
    restore.add_argument("--rehearsal", action="store_true")
    outbox = subs.add_parser("outbox")
    outbox.add_argument("--deliver", action="store_true")
    exe = subs.add_parser("exec")
    exe.add_argument("command", nargs=argparse.REMAINDER)
    args = p.parse_args(argv)
    try:
        cfg = Config(args.source, args.profile, args.local)
        if args.action in ("login", "account", "chat"):
            from .codex import account_status, codex_env

            if args.action == "account":
                emit(account_status(cfg))
                return 0
            if not (cfg.state / "profile.json").exists():
                raise ValueError("run init first")
            executable = cfg.local.get("codex", {}).get("executable", "codex")
            cmd = [
                executable,
                "-c",
                'forced_login_method="chatgpt"',
                "-c",
                'model_provider="openai"',
            ]
            if args.action == "login":
                return subprocess.run(
                    cmd + ["login", "--device-auth"], env=codex_env(cfg.env())
                ).returncode
            from .sandbox import arguments

            cmd += arguments(cfg)
            with profile_lock(cfg.state):
                return subprocess.run(
                    cmd + ["--cd", str(cfg.repo)], env=codex_env(cfg.env())
                ).returncode
        if args.action == "sandbox-check":
            from .sandbox import probe

            with profile_lock(cfg.state):
                result = probe(cfg)
            emit(result)
            return 0 if result["ok"] else 1
        if args.action == "retry":
            from .runner import retry

            result = retry(cfg, args.run_id)
            emit(result)
            return 0 if result["status"] in ("ok", "skipped") else 1
        if args.action == "validate":
            emit({"ok": True, "jobs": len(cfg.jobs)})
            return 0
        if args.action == "jobs":
            emit(cfg.jobs)
            return 0
        if args.action == "init":
            from .profile import initialize

            emit(initialize(cfg, args.content_source, args.clone))
            return 0
        if args.action == "sync-assets":
            from .profile import sync_assets

            with profile_lock(cfg.state):
                emit(sync_assets(cfg))
            return 0
        if args.action == "doctor":
            from .doctor import doctor

            with profile_lock(cfg.state):
                result = doctor(cfg, args.job)
            emit(result)
            return 0 if result["ok"] else 1
        if args.action in ("run", "prompt"):
            from .runner import run, prompt_for

            job = cfg.job(args.job)
            if args.action == "prompt":
                print(prompt_for(cfg, job))
                return 0
            if args.dry_run:
                emit(
                    {
                        "job": job,
                        "profile": str(cfg.profile),
                        "harness": "codex",
                        "script": str(cfg.runtime / "scripts" / job["script"])
                        if job.get("script")
                        else None,
                        "side_effects": False,
                    }
                )
                return 0
            result = run(cfg, args.job)
            emit(result)
            return 0 if result["status"] in ("ok", "skipped") else 1
        if args.action in ("tick", "serve"):
            from .runner import tick

            if args.action == "tick":
                result = tick(cfg)
                emit(result)
                return int(any(r["status"] == "error" for r in result))
            from .sandbox import probe

            with profile_lock(cfg.state):
                result = probe(cfg)
            if not result["ok"]:
                raise RuntimeError("native sandbox check failed; scheduler not started")
            while True:
                emit(tick(cfg))
                sys.stdout.flush()
                time.sleep(15)
        if args.action == "snapshot":
            from .backup import snapshot

            # A legacy source has no runner lock; --quiesced attests that all writers have been stopped.
            if (cfg.state / "profile.json").exists():
                with profile_lock(cfg.state):
                    emit(
                        snapshot(
                            cfg.profile,
                            args.destination,
                            quiesced=args.quiesced,
                            include_content=args.include_content,
                            legacy=args.legacy,
                        )
                    )
            else:
                emit(
                    snapshot(
                        cfg.profile,
                        args.destination,
                        quiesced=args.quiesced,
                        include_content=args.include_content,
                        legacy=args.legacy,
                    )
                )
            return 0
        if args.action == "restore":
            from .backup import restore

            emit(restore(cfg, args.bundle, rehearsal=args.rehearsal))
            return 0
        if args.action == "exec":
            if not args.command:
                raise ValueError("exec requires a command")
            return subprocess.run(
                args.command, cwd=cfg.profile, env=cfg.env()
            ).returncode
        if args.action == "outbox":
            from .delivery import deliver

            with profile_lock(cfg.state):
                results = []
                for path in sorted((cfg.state / "outbox").glob("*.json")):
                    if args.deliver:
                        item = deliver(cfg, path)
                    else:
                        item = json.loads(path.read_text())
                    results.append(
                        {
                            k: item.get(k)
                            for k in ("run", "job", "route", "status", "attempts")
                        }
                    )
                emit(results)
                return int(any(i["status"] == "failed" for i in results))
        if args.action == "status":
            if not (cfg.state / "runs.db").exists():
                emit({"runs": []})
                return 0
            store = Store(cfg.state)
            try:
                emit({j["name"]: store.latest(j["name"]) for j in cfg.jobs})
            finally:
                store.close()
            return 0
        if args.action in ("recover", "reset-cursor"):
            with profile_lock(cfg.state):
                store = Store(cfg.state)
                try:
                    at = datetime.now(timezone.utc).isoformat()
                    if args.action == "recover":
                        row = store.db.execute(
                            "SELECT status FROM runs WHERE id=?", (args.run_id,)
                        ).fetchone()
                        if not row or row[0] != "running":
                            raise ValueError("run is not interrupted/running")
                        store.finish(
                            args.run_id,
                            at,
                            "error",
                            {
                                "error": "operator marked interrupted run failed; inspect side effects before manual retry"
                            },
                        )
                        store.view(cfg)
                    else:
                        store.set_meta(
                            "cursor",
                            datetime.now(timezone.utc)
                            .replace(second=0, microsecond=0)
                            .isoformat(),
                        )
                finally:
                    store.close()
            emit({"ok": True})
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
