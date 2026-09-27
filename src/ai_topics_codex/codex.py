"""Harness transports. The scheduler, scripts, persistence and delivery live elsewhere.

Protocol references and tested versions: docs/architecture.md.
"""

from __future__ import annotations
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from .process import stop


class JsonLines:
    def __init__(self, argv, cwd, env, timeout, event_sink=None):
        self.event_sink = event_sink
        self.deadline = time.monotonic() + timeout
        self.proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self.messages = queue.Queue()
        self.stderr = []

        def read():
            try:
                for line in self.proc.stdout:
                    try:
                        self.messages.put(json.loads(line))
                    except ValueError:
                        self.messages.put(RuntimeError("non-JSON harness output"))
            finally:
                self.messages.put(EOFError("harness closed before completion"))

        def errors():
            for line in self.proc.stderr:
                self.stderr.append(line)
                if len(self.stderr) > 100:
                    self.stderr.pop(0)

        self.read_thread = threading.Thread(target=read, daemon=True)
        self.err_thread = threading.Thread(target=errors, daemon=True)
        self.read_thread.start()
        self.err_thread.start()

    def send(self, message):
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def recv(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("harness deadline exceeded")
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("harness deadline exceeded") from None
        if isinstance(message, Exception):
            raise message
        if self.event_sink and message.get("method", "").startswith(
            ("item/", "turn/", "thread/tokenUsage/")
        ):
            self.event_sink(message)
        return message

    def close(self):
        stop(self.proc)
        self.read_thread.join(timeout=2)
        self.err_thread.join(timeout=2)
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                pipe.close()
            except OSError:
                pass


def _codex_request(stream, id, method, params):
    stream.send({"id": id, "method": method, "params": params})
    pending = []
    while True:
        event = stream.recv()
        if event.get("id") == id and "method" not in event:
            if "error" in event:
                raise RuntimeError(f"Codex {method}: {event['error']}")
            return event.get("result", {}), pending
        reject_server_request(stream, event)
        pending.append(event)


def reject_server_request(stream, event):
    if "id" in event and "method" in event:
        method = event["method"]
        if method in (
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        ):
            stream.send({"id": event["id"], "result": {"decision": "decline"}})
        else:
            stream.send(
                {
                    "id": event["id"],
                    "error": {
                        "code": -32601,
                        "message": "Unattended runner does not support interactive requests",
                    },
                }
            )
        raise RuntimeError(f"harness requires operator interaction: {method}")


def codex_env(env):
    """Subscription-only: do not inherit API billing/provider overrides."""
    env = dict(env)
    for key in list(env):
        if key.startswith(
            (
                "OPENAI_",
                "AZURE_OPENAI_",
                "CODEX_API_",
                "CODEX_WIF_",
                "DISCORD_",
                "TELEGRAM_",
                "CF_EMAIL_",
            )
        ) or key in (
            "CODEX_ACCESS_TOKEN",
            "CODEX_MANAGED_AUTH",
            "CODEX_PROVIDER",
            "EMAIL_PASSWORD",
            "SLACK_BOT_TOKEN",
            "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
            "CODEX_THREAD_ID",
            "CODEX_SESSION_ID",
        ):
            env.pop(key, None)
    return env


def command(options):
    return [
        options.get("executable", "codex"),
        "-c",
        'forced_login_method="chatgpt"',
        "-c",
        'model_provider="openai"',
        "-c",
        "web_search=" + json.dumps(options.get("web_search", "live")),
        "app-server",
    ]


def connect(argv, cwd, env, timeout, event_sink=None):
    stream = JsonLines(argv, cwd, codex_env(env), timeout, event_sink)
    try:
        _codex_request(
            stream,
            1,
            "initialize",
            {"clientInfo": {"name": "ai_topics_codex", "version": "1.0.0"}},
        )
        stream.send({"method": "initialized", "params": {}})
        return stream
    except BaseException:
        stream.close()
        raise


def require_subscription(stream):
    result, _ = _codex_request(stream, 2, "account/read", {"refreshToken": False})
    account = result.get("account") or {}
    if account.get("type") != "chatgpt":
        raise RuntimeError(
            "ChatGPT subscription login required; run ai-topics-codex login. API-key fallback is disabled."
        )
    return {"type": account["type"], "plan": account.get("planType")}


def usage_limits(stream, request_id=20):
    data, _ = _codex_request(stream, request_id, "account/rateLimits/read", {})
    return {
        key: data.get(key)
        for key in ("ordinaryUsageAllowed", "rateLimits", "rateLimitsByLimitId")
        if key in data
    }


def require_capacity(limits):
    if limits.get("ordinaryUsageAllowed") is False:
        raise RuntimeError(
            "ChatGPT usage unavailable; wait for reset or inspect account. No API fallback or credit reset is performed."
        )
    current = limits.get("rateLimits") or {}
    if current.get("spendControlReached") or any(
        (current.get(window) or {}).get("usedPercent", 0) >= 100
        for window in ("primary", "secondary")
    ):
        raise RuntimeError(
            "ChatGPT usage limit reached; inspect account and retry after reset. No API fallback."
        )


def account_status(cfg):
    options = cfg.local.get("codex", {})
    stream = connect(command(options), cfg.profile, cfg.env(), 30)
    try:
        account = require_subscription(stream)
        limits = usage_limits(stream)
        return {"account": account, "rate_limits": limits}
    finally:
        stream.close()


def codex(argv, prompt, cwd, env, timeout, options):
    stream = connect(argv, cwd, env, timeout, options.get("event_sink"))
    thread = None
    turn_id = None
    finished = False
    try:
        account = require_subscription(stream)
        limits = usage_limits(stream)
        require_capacity(limits)
        external = (
            options.get("sandbox", env.get("WIKI_CODEX_SANDBOX", "workspace-write"))
            == "external"
        )
        if external and not (
            env.get("WIKI_CONTAINER_ISOLATED") == "1"
            and (Path("/.dockerenv").exists() or Path("/run/.containerenv").exists())
        ):
            raise RuntimeError(
                "external sandbox requires the isolated container deployment"
            )
        params = {
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "sandbox": "read-only" if external else "workspace-write",
            "modelProvider": "openai",
        }
        if options.get("model"):
            params["model"] = options["model"]
        result, _ = _codex_request(stream, 3, "thread/start", params)
        thread = result["thread"]["id"]
        policy = {
            "type": "workspaceWrite",
            "writableRoots": [env["WIKI_PROFILE_ROOT"]],
            "networkAccess": options.get("network_access", True),
        }
        if external:
            policy = {
                "type": "externalSandbox",
                "networkAccess": "enabled"
                if options.get("network_access", True)
                else "restricted",
            }
        params = {
            "threadId": thread,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "sandboxPolicy": policy,
        }
        if options.get("output_schema"):
            params["outputSchema"] = options["output_schema"]
        if options.get("effort"):
            params["effort"] = options["effort"]
        turn, early = _codex_request(stream, 4, "turn/start", params)
        turn_id = turn["turn"]["id"]
        messages = {}
        usage = None
        while True:
            event = early.pop(0) if early else stream.recv()
            reject_server_request(stream, event)
            p = event.get("params", {})
            method = event.get("method")
            if method == "account/rateLimits/updated":
                limits = {
                    key: p.get(key)
                    for key in ("rateLimits", "rateLimitsByLimitId")
                    if key in p
                }
            if (
                p.get("threadId", thread) != thread
                or p.get("turnId", turn_id) != turn_id
            ):
                continue
            if (
                method == "item/completed"
                and p.get("item", {}).get("type") == "agentMessage"
            ):
                item = p["item"]
                if item.get("phase") != "commentary":
                    messages[item["id"]] = item.get("text", "")
            if method == "thread/tokenUsage/updated":
                usage = p.get("tokenUsage")
            if method == "turn/completed" and p.get("turn", {}).get("id") == turn_id:
                finished = True
                if p["turn"].get("status") != "completed":
                    raise RuntimeError(
                        f"Codex turn {p['turn'].get('status')}: {p['turn'].get('error')}"
                    )
                if not messages:
                    raise RuntimeError("Codex completed without a final answer")
                return {
                    "text": list(messages.values())[-1],
                    "thread_id": thread,
                    "turn_id": turn_id,
                    "usage": usage,
                    "account": account,
                    "rate_limits": limits,
                }
    finally:
        if thread and turn_id and not finished:
            try:
                stream.send(
                    {
                        "id": 99,
                        "method": "turn/interrupt",
                        "params": {"threadId": thread, "turnId": turn_id},
                    }
                )
            except (OSError, ValueError):
                pass
        stream.close()


def run_agent(cfg, prompt, timeout, *, output_schema=None, event_sink=None):
    options = {
        **cfg.local.get("codex", {}),
        "output_schema": output_schema,
        "event_sink": event_sink,
    }
    return codex(command(options), prompt, cfg.repo, cfg.env(), timeout, options)
