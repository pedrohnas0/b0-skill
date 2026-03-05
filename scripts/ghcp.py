#!/usr/bin/env python3
"""Copies a directory from a GitHub repo to a local path.

Usage: ghcp <owner/repo> <path> <dest>
Example: ghcp remotion-dev/skills skills/remotion ./local-dir
"""

import json
import sys
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/b0-skill/scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import ui


def main():
    if len(sys.argv) != 4:
        ui.fail("usage: ghcp <owner/repo> <path> <dest>")
        sys.exit(1)

    repo, prefix, dest = sys.argv[1], sys.argv[2], Path(sys.argv[3])

    ui.header(f"ghcp {repo}")

    # Fetch tree
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    try:
        with urllib.request.urlopen(tree_url) as resp:
            tree = json.loads(resp.read())["tree"]
    except Exception as e:
        ui.fail("could not fetch repo", str(e))
        sys.exit(1)

    files = [
        item["path"] for item in tree
        if item["path"].startswith(prefix + "/") and item["type"] == "blob"
    ]

    if not files:
        ui.fail(f"no files found under '{prefix}'")
        sys.exit(1)

    raw_base = f"https://raw.githubusercontent.com/{repo}/main"

    # Group files by directory
    dirs = {}
    for file_path in files:
        rel = file_path[len(prefix) + 1:]
        d = str(Path(rel).parent)
        if d not in dirs:
            dirs[d] = []
        dirs[d].append(Path(rel).name)

    # Download
    dir_names = sorted(dirs.keys())
    for i, d in enumerate(dir_names):
        is_last = i == len(dir_names) - 1
        label = d if d != "." else prefix.split("/")[-1] + "/"

        if i == 0 and is_last:
            ui.group_start(label)
        elif i == 0:
            ui.group_start(label)
        elif is_last:
            ui.group_end(label)
        else:
            ui.group_mid(label)

        for fname in sorted(dirs[d]):
            rel = fname if d == "." else f"{d}/{fname}"
            file_path = f"{prefix}/{rel}"
            local = dest / rel
            local.parent.mkdir(parents=True, exist_ok=True)

            url = f"{raw_base}/{file_path}"
            try:
                urllib.request.urlretrieve(url, local)
                ui.list_item(fname)
            except Exception:
                ui.list_item(f"{fname}  {ui.red('✗')}")

    ui.result(f"{len(files)} files {ui.dim('→')} {dest}")


if __name__ == "__main__":
    main()
