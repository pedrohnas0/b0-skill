#!/usr/bin/env python3
"""Cloudflare API helper.

Usage:
  cf zones                                  - List zones
  cf dns list                               - List DNS records
  cf dns create <type> <name> <content>     - Create DNS record
  cf dns delete <record_id>                 - Delete DNS record
  cf pagerule list                          - List page rules
  cf pagerule create <match> <url>          - Create redirect (302)
  cf pagerule delete <rule_id>              - Delete page rule
"""

import json
import sys
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/meta/scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import ui

ENV_FILE = Path("/home/pedro/dev/.claude/skills/meta/.env")


def load_env():
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()
    return env


def api(method, path, data=None):
    env = load_env()
    url = f"https://api.cloudflare.com/client/v4/{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("X-Auth-Email", env["CF_EMAIL"])
    req.add_header("X-Auth-Key", env["CF_API_KEY"])
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zone_id():
    return load_env()["CF_ZONE_ID"]


def cmd_zones():
    ui.header("cf zones")
    result = api("GET", "zones")
    ui.group_start("zones")
    for z in result["result"]:
        ui.list_item(z["name"], z["id"], z["plan"]["name"])
    ui.result(f"{len(result['result'])} zones")


def cmd_dns_list():
    ui.header("cf dns list")
    result = api("GET", f"zones/{zone_id()}/dns_records")
    records = result["result"]

    # Group by type
    by_type = {}
    for r in records:
        t = r["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    types = sorted(by_type.keys())
    for i, t in enumerate(types):
        if i == 0:
            ui.group_start(t)
        elif i == len(types) - 1:
            ui.group_end(t)
        else:
            ui.group_mid(t)

        for r in by_type[t]:
            tag = "proxied" if r.get("proxied") else "direct"
            ui.list_item(r["name"], r["content"], tag)

    ui.result(f"{len(records)} records")


def cmd_dns_create(rtype, name, content):
    result = api("POST", f"zones/{zone_id()}/dns_records", {
        "type": rtype, "name": name, "content": content, "proxied": True
    })
    if result["success"]:
        ui.ok("dns record created")
        ui.list_item(f"{rtype} {name}", content)
    else:
        ui.fail("dns record failed", str(result["errors"]))


def cmd_dns_delete(record_id):
    result = api("DELETE", f"zones/{zone_id()}/dns_records/{record_id}")
    if result["success"]:
        ui.ok("dns record deleted", record_id)
    else:
        ui.fail("delete failed", str(result["errors"]))


def cmd_pagerule_list():
    ui.header("cf pagerule list")
    result = api("GET", f"zones/{zone_id()}/pagerules")
    rules = result["result"]
    ui.group_start("page rules")
    for r in rules:
        target = r["targets"][0]["constraint"]["value"]
        url = r["actions"][0].get("value", {}).get("url", "?")
        ui.list_item(target, url, r["id"][:12])
    ui.result(f"{len(rules)} rules")


def cmd_pagerule_create(match, url):
    result = api("POST", f"zones/{zone_id()}/pagerules", {
        "targets": [{"target": "url", "constraint": {"operator": "matches", "value": match}}],
        "actions": [{"id": "forwarding_url", "value": {"url": url, "status_code": 302}}],
        "status": "active"
    })
    if result["success"]:
        ui.ok("page rule created")
        ui.list_item(match, url)
    else:
        ui.fail("page rule failed", str(result["errors"]))


def cmd_pagerule_delete(rule_id):
    result = api("DELETE", f"zones/{zone_id()}/pagerules/{rule_id}")
    if result["success"]:
        ui.ok("page rule deleted", rule_id)
    else:
        ui.fail("delete failed", str(result["errors"]))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]

    if cmd == "zones":
        cmd_zones()
    elif cmd == "dns":
        if len(args) < 2:
            ui.fail("usage: cf dns <list|create|delete>")
            sys.exit(1)
        sub = args[1]
        if sub == "list":
            cmd_dns_list()
        elif sub == "create" and len(args) == 5:
            cmd_dns_create(args[2], args[3], args[4])
        elif sub == "delete" and len(args) == 3:
            cmd_dns_delete(args[2])
        else:
            ui.fail("usage: cf dns <list|create <type> <name> <content>|delete <id>>")
    elif cmd == "pagerule":
        if len(args) < 2:
            ui.fail("usage: cf pagerule <list|create|delete>")
            sys.exit(1)
        sub = args[1]
        if sub == "list":
            cmd_pagerule_list()
        elif sub == "create" and len(args) == 4:
            cmd_pagerule_create(args[2], args[3])
        elif sub == "delete" and len(args) == 3:
            cmd_pagerule_delete(args[2])
        else:
            ui.fail("usage: cf pagerule <list|create <match> <url>|delete <id>>")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
