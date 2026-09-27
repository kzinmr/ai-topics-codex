"""Minimal protocol peer, deliberately independent of adapter implementation."""

import json
import sys
import time


def send(value):
    print(json.dumps(value), flush=True)


mode = sys.argv[1]
scenario = sys.argv[2] if len(sys.argv) > 2 else "ok"
if scenario == "timeout":
    time.sleep(20)
    raise SystemExit()
for line in sys.stdin:
    data = json.loads(line)
    if mode == "codex":
        method = data.get("method")
        if method == "initialize":
            send({"id": data["id"], "result": {"userAgent": "fixture"}})
        elif method == "account/read":
            send(
                {
                    "id": data["id"],
                    "result": {
                        "account": {
                            "type": "apiKey" if scenario == "apikey" else "chatgpt",
                            "planType": "pro",
                        }
                    },
                }
            )
        elif method == "account/rateLimits/read":
            send({"id": data["id"], "result": {"rateLimits": {}}})
        elif method == "thread/start":
            send({"id": data["id"], "result": {"thread": {"id": "thread-fixture"}}})
        elif method == "turn/start":
            assert "sandboxPolicy" not in data["params"]
            assert data["params"]["approvalPolicy"] == "never"
            if scenario == "reject":
                send(
                    {
                        "id": data["id"],
                        "error": {"code": -1, "message": "invalid model"},
                    }
                )
                continue
            send({"id": data["id"], "result": {"turn": {"id": "turn-fixture"}}})
            if scenario == "approval":
                send(
                    {
                        "id": 99,
                        "method": "item/commandExecution/requestApproval",
                        "params": {},
                    }
                )
                continue
            if scenario == "eof":
                raise SystemExit()
            send(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thread-fixture",
                        "item": {
                            "id": "commentary",
                            "type": "agentMessage",
                            "text": "working",
                            "phase": "commentary",
                        },
                    },
                }
            )
            send(
                {
                    "method": "item/agentMessage/delta",
                    "params": {"delta": "not authoritative"},
                }
            )
            send(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thread-fixture",
                        "item": {
                            "id": "answer",
                            "type": "agentMessage",
                            "text": '{"decisions": [], "ok": true}',
                            "phase": "final_answer",
                        },
                    },
                }
            )
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread-fixture",
                        "turn": {
                            "id": "turn-fixture",
                            "status": "failed"
                            if scenario == "failure"
                            else "completed",
                            "error": None,
                        },
                    },
                }
            )
