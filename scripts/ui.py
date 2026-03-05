"""b0-skill UI system.

Shared visual language for all b0 scripts.

Characters:
  ✓  success     ✗  failure     ⚠  warning
  →  points to   ·  separator   ⠋  loading
  ┌  group top   ├  group mid   └  group end   │  group line   ─  dash
"""

import os
import sys

# Colors — respect NO_COLOR standard (https://no-color.org)
_NO_COLOR = os.environ.get("NO_COLOR") is not None


def _c(code, text):
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t):  return _c("32", t)
def red(t):    return _c("31", t)
def yellow(t): return _c("33", t)
def dim(t):    return _c("2", t)
def bold(t):   return _c("1", t)


# ── Inline messages ──────────────────────────────────────────

def ok(msg, detail=None):
    d = f"  {dim(detail)}" if detail else ""
    print(f"  {green('✓')} {msg}{d}")


def fail(msg, detail=None):
    d = f"  {dim(detail)}" if detail else ""
    print(f"  {red('✗')} {msg}{d}")


def warn(msg, detail=None):
    d = f"  {dim(detail)}" if detail else ""
    print(f"  {yellow('⚠')} {msg}{d}")


# ── Header ───────────────────────────────────────────────────

def header(title):
    print(f"\n  {bold(title)}\n")


# ── Tree groups ──────────────────────────────────────────────

def group_start(name):
    print(f"  {dim('┌')} {bold(name)}")


def group_mid(name):
    print(f"  {dim('│')}")
    print(f"  {dim('├')} {bold(name)}")


def group_end(name):
    print(f"  {dim('│')}")
    print(f"  {dim('└')} {bold(name)}")


def group_line():
    print(f"  {dim('│')}")


# ── Tree items (inside groups) ───────────────────────────────

def item_ok(label, value="", detail=""):
    _item(green("✓"), label, value, detail)


def item_fail(label, value="", detail=""):
    _item(red("✗"), label, value, detail)


def item_warn(label, value="", detail=""):
    _item(yellow("⚠"), label, value, detail)


def item_none(label, value="", detail=""):
    _item(" ", label, value, detail)


def _item(icon, label, value, detail):
    l = f"{label:<14}"
    v = f"{value:<20}" if value else ""
    d = f"{dim('→')} {dim(detail)}" if detail else ""
    print(f"  {dim('│')}  {icon} {l}{v}{d}")


# ── Progress steps ───────────────────────────────────────────

def step_done(label, detail=""):
    d = f"  {dim(detail)}" if detail else ""
    print(f"  {dim('├─')} {label:<28}{green('✓')}{d}")


def step_last(label, detail=""):
    d = f"  {dim(detail)}" if detail else ""
    print(f"  {dim('└─')} {label:<28}{green('✓')}{d}")


def step_fail(label, reason=""):
    r = f"  {reason}" if reason else ""
    print(f"  {dim('├─')} {label:<28}{red('✗')}{r}")


def step_active(label, msg=""):
    m = f" {msg}" if msg else ""
    print(f"  {dim('├─')} {label:<28}{dim('⠋')}{dim(m)}")


# ── List items (inside groups, no status icon) ───────────────

def list_item(left, right="", tag=""):
    l = f"{left:<30}"
    r = f"{dim('→')} {right:<24} " if right else ""
    t = f"{dim(tag)}" if tag else ""
    print(f"  {dim('│')}  {l}{r}{t}")


# ── Footer ───────────────────────────────────────────────────

def footer(msg):
    print(f"\n  {dim(msg)}\n")


def result(msg):
    print(f"\n  {msg}\n")
