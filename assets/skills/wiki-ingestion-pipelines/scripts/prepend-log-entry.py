import os
#!/usr/bin/env python3
'\nPrepend a new log entry to wiki/log.md while keeping the header at the top.\n\nUsage:\n    python3 prepend-log-entry.py LOG_PATH < entry.txt\n\nOr import and call:\n    from prepend_log_entry import prepend_log_entry\n    prepend_log_entry("~/wiki/log.md", new_entry_text)\n\nThe log.md file has this structure:\n    # Wiki Log\n    _Log of all wiki changes. Newest entries at top._\n    ## [2026-06-30 07:40] — Newsletter wiki-ingest — 8 takes...\n    ...\n\nThe header must always remain at the top of the file.\n'

import sys


HEADER = "# Wiki Log\n\n_Log of all wiki changes. Newest entries at top._\n\n"


def prepend_log_entry(log_path: str, new_entry: str) -> None:
    """Prepend a new entry to log.md, preserving the header."""
    with open(log_path) as f:
        content = f.read()

    # Find the header in the current file
    header_idx = content.find("# Wiki Log")
    if header_idx == -1:
        # No header found — just prepend with header
        with open(log_path, "w") as f:
            f.write(HEADER + new_entry.strip() + "\n\n" + content.strip() + "\n")
        return

    # Extract everything between the header and the first log entry
    # Current structure: [header] [existing content...]
    prefix = content[:header_idx]
    rest = content[header_idx:]

    # Remove the header from rest
    if rest.startswith(HEADER):
        existing = rest[len(HEADER):]
    else:
        existing = rest

    # Build: header → new entry → existing content
    combined = HEADER + new_entry.strip() + "\n\n" + existing.strip() + "\n"

    with open(log_path, "w") as f:
        f.write(combined)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 prepend-log-entry.py LOG_PATH")
        sys.exit(1)

    log_path = sys.argv[1]
    new_entry = sys.stdin.read()
    prepend_log_entry(log_path, new_entry)
