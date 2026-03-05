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
    result = api("GET", "zones")
    for z in result["result"]:
        print(f"  {z['name']}  {z['id']}  ({z['plan']['name']})")


def cmd_dns_list():
    result = api("GET", f"zones/{zone_id()}/dns_records")
    for r in result["result"]:
        proxied = "proxied" if r.get("proxied") else "direct"
        print(f"  {r['type']:6} {r['name']:40} {r['content']:30} {proxied}  id={r['id']}")


def cmd_dns_create(rtype, name, content):
    result = api("POST", f"zones/{zone_id()}/dns_records", {
        "type": rtype, "name": name, "content": content, "proxied": True
    })
    if result["success"]:
        print(f"  Created: {rtype} {name} -> {content}")
    else:
        print(f"  Error: {result['errors']}")


def cmd_dns_delete(record_id):
    result = api("DELETE", f"zones/{zone_id()}/dns_records/{record_id}")
    print(f"  {'Deleted' if result['success'] else result['errors']}")


def cmd_pagerule_list():
    result = api("GET", f"zones/{zone_id()}/pagerules")
    for r in result["result"]:
        target = r["targets"][0]["constraint"]["value"]
        action = r["actions"][0]
        url = action.get("value", {}).get("url", "?")
        print(f"  {target} -> {url}  ({action['id']})  id={r['id']}")


def cmd_pagerule_create(match, url):
    result = api("POST", f"zones/{zone_id()}/pagerules", {
        "targets": [{"target": "url", "constraint": {"operator": "matches", "value": match}}],
        "actions": [{"id": "forwarding_url", "value": {"url": url, "status_code": 302}}],
        "status": "active"
    })
    if result["success"]:
        print(f"  Created: {match} -> {url}")
    else:
        print(f"  Error: {result['errors']}")


def cmd_pagerule_delete(rule_id):
    result = api("DELETE", f"zones/{zone_id()}/pagerules/{rule_id}")
    print(f"  {'Deleted' if result['success'] else result['errors']}")


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
            sys.exit("Usage: cf dns <list|create|delete>")
        sub = args[1]
        if sub == "list":
            cmd_dns_list()
        elif sub == "create" and len(args) == 5:
            cmd_dns_create(args[2], args[3], args[4])
        elif sub == "delete" and len(args) == 3:
            cmd_dns_delete(args[2])
        else:
            sys.exit("Usage: cf dns <list|create <type> <name> <content>|delete <id>>")
    elif cmd == "pagerule":
        if len(args) < 2:
            sys.exit("Usage: cf pagerule <list|create|delete>")
        sub = args[1]
        if sub == "list":
            cmd_pagerule_list()
        elif sub == "create" and len(args) == 4:
            cmd_pagerule_create(args[2], args[3])
        elif sub == "delete" and len(args) == 3:
            cmd_pagerule_delete(args[2])
        else:
            sys.exit("Usage: cf pagerule <list|create <match> <url>|delete <id>>")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
