"""Optional explicit delivery command. Reads an outbox envelope from stdin.

Run IDs are appended for receiver-side deduplication. A crash after provider
acceptance can still duplicate a message: transport delivery is at-least-once.
"""

import json
import os
import sys
import urllib.error
import urllib.request


def post(url, payload, headers):
    request = urllib.request.Request(
        url,
        json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
            if isinstance(result, dict) and result.get("ok") is False:
                raise RuntimeError("provider rejected delivery")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"delivery HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("delivery connection failed") from None


def main():
    item = json.load(sys.stdin)
    route = item["route"]
    text = item["text"] + "\n[run:" + item["run"] + "]"
    if route == "digest":
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        chat = os.environ["TELEGRAM_DIGEST_CHAT"]
        for start in range(0, len(text), 4000):
            post(
                "https://api.telegram.org/bot" + token + "/sendMessage",
                {"chat_id": chat, "text": text[start : start + 4000]},
                {},
            )
    else:
        channel = os.environ[
            "DISCORD_HOT_POSTS_CHANNEL"
            if route == "hot-posts"
            else "DISCORD_OPERATIONS_CHANNEL"
        ]
        token = os.environ["DISCORD_BOT_TOKEN"]
        for start in range(0, len(text), 1900):
            post(
                "https://discord.com/api/v10/channels/" + channel + "/messages",
                {
                    "content": text[start : start + 1900],
                    "allowed_mentions": {"parse": []},
                },
                {"Authorization": "Bot " + token},
            )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
