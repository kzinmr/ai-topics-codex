"""Path and configuration contract. No harness import is allowed here."""

from __future__ import annotations
import json
import os
import re
import sys
import tempfile
from pathlib import Path


class ConfigError(ValueError):
    pass


def atomic_write(path: Path, text: str, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ConfigError(f"path escapes root: {relative}")
    return path


class Config:
    def __init__(self, source=None, profile=None, local=None):
        self.source = Path(
            source
            or os.environ.get("AI_TOPICS_CODEX_SOURCE")
            or Path(__file__).resolve().parents[2]
        ).resolve()
        self.profile = (
            Path(
                profile
                or os.environ.get("WIKI_PROFILE_ROOT")
                or os.environ.get("WIKI_SUBPROCESS_HOME")
                or self.source / "profiles/lucy"
            )
            .expanduser()
            .resolve()
        )
        self.repo = self.profile / "ai-topics"
        self.wiki = self.profile / "wiki"
        self.state = self.profile / ".wiki-agent"
        self.runtime = self.state
        self.skills = self.profile / ".agents/skills"
        self.local_path = Path(local).resolve() if local else self.state / "local.json"
        self.local = (
            json.loads(self.local_path.read_text()) if self.local_path.exists() else {}
        )
        self.manifest = json.loads((self.source / "config/jobs.json").read_text())
        self.jobs = self.manifest["jobs"]
        self.by_name = {j["name"]: j for j in self.jobs}
        self.validate()

    def validate(self):
        from .schedule import cron_matches
        from datetime import datetime, timezone

        if self.manifest.get("version") != 1 or self.manifest.get("timezone") != "UTC":
            raise ConfigError("jobs version=1 and timezone=UTC required")
        if len(self.by_name) != len(self.jobs):
            raise ConfigError("duplicate job names")
        ids = set()
        for j in self.jobs:
            if not re.fullmatch("[a-z0-9]+(?:-[a-z0-9]+)*", j["name"]):
                raise ConfigError("invalid job name")
            if not re.fullmatch("[a-zA-Z0-9_-]+", j["id"]) or j["id"] in ids:
                raise ConfigError("invalid or duplicate job id")
            ids.add(j["id"])
            cron_matches(j["schedule"], datetime.now(timezone.utc))
            if not isinstance(j["enabled"], bool) or not isinstance(
                j["no_agent"], bool
            ):
                raise ConfigError("enabled/no_agent must be boolean")
            if j["no_agent"] and not j.get("script"):
                raise ConfigError("no_agent requires script")
            if (
                j.get("script")
                and not inside(self.source / "assets/scripts", j["script"]).is_file()
            ):
                raise ConfigError(f"missing script: {j['script']}")
            if not inside(self.source, j["prompt"]).is_file():
                raise ConfigError(f"missing prompt: {j['name']}")
            for skill in j["skills"]:
                if not inside(
                    self.source / "assets/skills", skill + "/SKILL.md"
                ).is_file():
                    raise ConfigError(f"missing skill: {skill}")
            for dep in j["depends_on"]:
                if dep not in self.by_name:
                    raise ConfigError(f"unknown dependency: {dep}")
            for key in (
                "timeout_seconds",
                "script_timeout_seconds",
                "max_dependency_age_hours",
            ):
                if not isinstance(j[key], (int, float)) or j[key] <= 0:
                    raise ConfigError(f"invalid {key}")

        def visit(name, stack):
            if name in stack:
                raise ConfigError("dependency cycle")
            for dep in self.by_name[name]["depends_on"]:
                visit(dep, stack + [name])

        for name in self.by_name:
            visit(name, [])
        if "harness" in self.local or "adapters" in self.local:
            raise ConfigError(
                "Use codex configuration; legacy harness/adapters settings are not supported"
            )
        if self.local.get("publication", "local") not in ("local", "commit", "push"):
            raise ConfigError("publication must be local, commit or push")
        options = self.local.get("codex", {})
        if not isinstance(options, dict):
            raise ConfigError("codex must be an object")
        if options.get("sandbox", "native") != "native":
            raise ConfigError(
                "codex.sandbox must be native; run sync-assets and remove old sandbox settings"
            )
        if options.get("network_access", False):
            raise ConfigError(
                "Use codex.network_jobs for explicit per-job network permission"
            )
        if options.get("web_search", "live") not in ("live", "cached", "disabled"):
            raise ConfigError("invalid codex.web_search")
        if "network_jobs" in options and (
            not isinstance(options["network_jobs"], list)
            or any(name not in self.by_name for name in options["network_jobs"])
        ):
            raise ConfigError("codex.network_jobs must list known job names")

    def env(self):
        env = os.environ.copy()
        # Harness configuration must belong to the destination profile. Explicit
        # entries in local.environment below can opt into a dedicated external store.
        for key in list(env):
            if key.startswith("HERMES_"):
                env.pop(key, None)
        for key in (
            "CODEX_HOME",
            "PI_CODING_AGENT_DIR",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
        ):
            env.pop(key, None)
        # Plain JSON is parsed, never sourced as shell. It is local and ignored by git.
        secrets = self.state / "secrets.json"
        if secrets.exists():
            values = json.loads(secrets.read_text())
            if not all(
                isinstance(k, str) and isinstance(v, str) for k, v in values.items()
            ):
                raise ConfigError("secrets.json must map names to strings")
            env.update(values)
        env.update({k: str(v) for k, v in self.local.get("environment", {}).items()})
        env.update(
            HOME=str(self.profile),
            WIKI_PROFILE_ROOT=str(self.profile),
            WIKI_SUBPROCESS_HOME=str(self.profile),
            WIKI_AGENT_HOME=str(self.runtime),
            WIKI_WORK_DIR=str(self.state / "work"),
            AI_TOPICS_REPO=str(self.repo),
            AI_TOPICS_HOME=str(self.repo),
            WIKI_ROOT=str(self.wiki),
            WIKI_PATH=str(self.wiki),
            AI_TOPICS_CODEX_SOURCE=str(self.source),
            AI_TOPICS_CODEX_STATE=str(self.state),
            AI_TOPICS_JOBS_FILE=str(self.state / "jobs-view.json"),
            AI_TOPICS_SKILLS=str(self.skills),
            PYTHONPATH=str(self.source / "src")
            + os.pathsep
            + env.get("PYTHONPATH", ""),
            TZ="UTC",
            PYTHONDONTWRITEBYTECODE="1",
            TMPDIR=str(self.state / "work"),
        )
        env["PATH"] = os.pathsep.join(
            [
                str(self.source / "bin"),
                str(Path(sys.executable).parent),
                str(self.runtime / "venv/bin"),
                str(self.runtime / "bin"),
                str(self.profile / "bin"),
                env.get("PATH", ""),
            ]
        )
        env["CODEX_HOME"] = str(
            Path(self.local.get("codex", {}).get("auth_home", self.profile / ".codex"))
            .expanduser()
            .resolve()
        )
        return env

    def job(self, name):
        try:
            return self.by_name[name]
        except KeyError:
            raise ConfigError(f"unknown job: {name}") from None
