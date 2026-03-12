#!/usr/bin/env python3
"""Query Neon databases directly.

Usage:
  db <service> <query>          - Run SQL query
  db <service>                  - Show connection info
  db ai "SELECT COUNT(*) FROM sessions"
  db auth "SELECT * FROM users LIMIT 5"

Services: ai, auth
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/b0-skill/scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import ui

SERVICES = {
    "ai":   Path(os.path.expanduser("~/dev/buildzero/services/ai")),
    "auth": Path(os.path.expanduser("~/dev/buildzero/services/auth")),
}


def get_db_url(service: str) -> str:
    """Get DATABASE_URL for a service. Auto-pulls from Vercel if missing."""
    svc_dir = SERVICES.get(service)
    if not svc_dir:
        ui.fail(f"unknown service: {service}")
        print(f"  available: {', '.join(SERVICES)}")
        sys.exit(1)

    env_file = svc_dir / ".env.local"

    if not env_file.exists():
        ui.warn(f"pulling env vars for {service}...")
        subprocess.run(["vercel", "env", "pull"], cwd=svc_dir, capture_output=True)

    if not env_file.exists():
        ui.fail(f"no .env.local in {svc_dir}")
        print("  run: vercel env pull")
        sys.exit(1)

    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"')
            return url

    ui.fail(f"DATABASE_URL not found in {env_file}")
    sys.exit(1)


def parse_conn(url: str) -> dict:
    """Parse postgresql://user:pass@host/db into components."""
    parsed = urllib.parse.urlparse(url)
    return {
        "host": parsed.hostname,
        "database": parsed.path.lstrip("/"),
    }


def query(db_url: str, sql: str) -> dict:
    """Execute SQL via Neon HTTP API."""
    host = parse_conn(db_url)["host"]

    body = json.dumps({
        "query": sql,
        "params": [],
    }).encode()

    req = urllib.request.Request(f"https://{host}/sql", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Neon-Connection-String", db_url)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            err = json.loads(error_body)
            ui.fail(f"SQL error: {err.get('message', error_body)}")
        except json.JSONDecodeError:
            ui.fail(f"HTTP {e.code}: {error_body[:200]}")
        sys.exit(1)


def format_table(result: dict) -> None:
    """Print query results as aligned table."""
    fields = result.get("fields", [])
    rows = result.get("rows", [])

    if not fields:
        ui.ok("query executed (no results)")
        return

    headers = [f["name"] for f in fields]

    # Rows are dicts keyed by field name
    widths = [len(h) for h in headers]
    for row in rows:
        for i, h in enumerate(headers):
            val = row.get(h)
            widths[i] = max(widths[i], len(str(val) if val is not None else "NULL"))
    widths = [min(w, 50) for w in widths]

    # Header
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(f"  {ui.dim(header_line)}")
    print(f"  {ui.dim('─' * len(header_line))}")

    # Rows
    for row in rows:
        cells = []
        for i, h in enumerate(headers):
            val = row.get(h)
            text = str(val) if val is not None else ui.dim("NULL")
            if len(str(val or "")) > 50:
                text = str(val)[:47] + "..."
            cells.append(text.ljust(widths[i]))
        print(f"  {'  '.join(cells)}")

    print(f"\n  {ui.dim(f'{len(rows)} rows')}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    service = sys.argv[1]
    db_url = get_db_url(service)

    if len(sys.argv) < 3:
        conn = parse_conn(db_url)
        ui.ok(f"{service}", f"{conn['host']} / {conn['database']}")
        sys.exit(0)

    sql = " ".join(sys.argv[2:])
    print(f"  {ui.dim(f'{service} →')} {sql[:80]}{'...' if len(sql) > 80 else ''}")

    result = query(db_url, sql)
    format_table(result)


if __name__ == "__main__":
    main()
