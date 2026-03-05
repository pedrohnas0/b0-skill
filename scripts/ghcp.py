#!/usr/bin/env python3
"""Copies a directory from a GitHub repo to a local path.

Usage: ghcp <owner/repo> <path> <dest>
Example: ghcp remotion-dev/skills skills/remotion ./local-dir
"""

import json
import sys
import urllib.request
from pathlib import Path

def main():
    if len(sys.argv) != 4:
        sys.exit("Usage: ghcp <owner/repo> <path> <dest>")

    repo, prefix, dest = sys.argv[1], sys.argv[2], Path(sys.argv[3])

    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    with urllib.request.urlopen(tree_url) as resp:
        tree = json.loads(resp.read())["tree"]

    files = [
        item["path"] for item in tree
        if item["path"].startswith(prefix + "/") and item["type"] == "blob"
    ]

    if not files:
        sys.exit(f"No files found under '{prefix}' in {repo}")

    raw_base = f"https://raw.githubusercontent.com/{repo}/main"

    for file_path in files:
        rel = file_path[len(prefix) + 1:]
        local = dest / rel
        local.parent.mkdir(parents=True, exist_ok=True)

        url = f"{raw_base}/{file_path}"
        urllib.request.urlretrieve(url, local)
        print(f"  {rel}")

    print(f"Done -> {dest}")

if __name__ == "__main__":
    main()
