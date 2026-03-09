"""Tests for agent-daemon.py tool executors and auto-detect."""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# Import from agent-daemon.py (dashes not valid in Python module names)
_spec = importlib.util.spec_from_file_location(
    "agent_daemon", Path(__file__).parent / "agent-daemon.py"
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_mod)  # type: ignore

get_daemon_name = _mod.get_daemon_name
tool_bash = _mod.tool_bash
tool_read = _mod.tool_read
tool_edit = _mod.tool_edit
tool_write = _mod.tool_write
tool_glob = _mod.tool_glob
tool_grep = _mod.tool_grep


# ── get_daemon_name ───────────────────────────────────────────

def test_daemon_name_from_DAEMON_NAME(monkeypatch):
    monkeypatch.setenv("DAEMON_NAME", "meu-vps")
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    assert get_daemon_name() == "meu-vps"


def test_daemon_name_from_WSL_DISTRO_NAME(monkeypatch):
    monkeypatch.delenv("DAEMON_NAME", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "debian10")
    assert get_daemon_name() == "debian10"


def test_daemon_name_fallback_to_hostname(monkeypatch):
    monkeypatch.delenv("DAEMON_NAME", raising=False)
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    import socket
    assert get_daemon_name() == socket.gethostname()


def test_daemon_name_DAEMON_NAME_takes_precedence(monkeypatch):
    monkeypatch.setenv("DAEMON_NAME", "override")
    monkeypatch.setenv("WSL_DISTRO_NAME", "debian10")
    assert get_daemon_name() == "override"


# ── tool_bash ─────────────────────────────────────────────────

def test_tool_bash_basic():
    result = asyncio.run(tool_bash("echo hello"))
    assert result["output"].strip() == "hello"
    assert result["exit"] == 0


def test_tool_bash_exit_code():
    result = asyncio.run(tool_bash("exit 42"))
    assert result["exit"] == 42


def test_tool_bash_timeout_kills():
    result = asyncio.run(tool_bash("sleep 10", timeout=1))
    assert result["exit"] == -1
    assert "Timed out" in result["output"]


def test_tool_bash_stderr_captured():
    result = asyncio.run(tool_bash("echo err >&2"))
    assert "err" in result["output"]


# ── tool_read ─────────────────────────────────────────────────

def test_tool_read_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3\n")
    result = asyncio.run(tool_read(str(f)))
    assert "line1" in result["output"]
    assert result["type"] == "file"
    assert result["lines"] == 3


def test_tool_read_offset_limit(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("\n".join(f"line{i}" for i in range(10)) + "\n")
    result = asyncio.run(tool_read(str(f), offset=3, limit=2))
    assert "3: line2" in result["output"]
    assert result["lines"] == 2


def test_tool_read_directory(tmp_path):
    (tmp_path / "file.ts").write_text("x")
    (tmp_path / "subdir").mkdir()
    result = asyncio.run(tool_read(str(tmp_path)))
    assert result["type"] == "directory"
    assert "file.ts" in result["output"]
    assert "subdir/" in result["output"]


def test_tool_read_not_found():
    result = asyncio.run(tool_read("/nonexistent/file.txt"))
    assert "error" in result


def test_tool_read_binary(tmp_path):
    f = tmp_path / "bin.dat"
    f.write_bytes(b"\x00\x01\x02binary")
    result = asyncio.run(tool_read(str(f)))
    assert "error" in result
    assert "binary" in result["error"].lower()


# ── tool_edit ─────────────────────────────────────────────────

def test_tool_edit_basic(tmp_path):
    f = tmp_path / "test.ts"
    f.write_text("const x = 1\nconst y = 2\n")
    result = asyncio.run(tool_edit(str(f), "const x = 1", "const x = 99"))
    assert result["output"] == "Edit applied."
    assert f.read_text() == "const x = 99\nconst y = 2\n"


def test_tool_edit_not_found_string(tmp_path):
    f = tmp_path / "test.ts"
    f.write_text("hello world")
    result = asyncio.run(tool_edit(str(f), "not there", "x"))
    assert "error" in result


def test_tool_edit_multiple_matches_without_replace_all(tmp_path):
    f = tmp_path / "test.ts"
    f.write_text("x\nx\nx\n")
    result = asyncio.run(tool_edit(str(f), "x", "y"))
    assert "error" in result
    assert "3" in result["error"]


def test_tool_edit_replace_all(tmp_path):
    f = tmp_path / "test.ts"
    f.write_text("x\nx\nx\n")
    result = asyncio.run(tool_edit(str(f), "x", "y", replace_all=True))
    assert result["replacements"] == 3
    assert f.read_text() == "y\ny\ny\n"


def test_tool_edit_file_not_found():
    result = asyncio.run(tool_edit("/nonexistent.ts", "x", "y"))
    assert "error" in result


# ── tool_write ────────────────────────────────────────────────

def test_tool_write_creates_file(tmp_path):
    target = tmp_path / "new.ts"
    result = asyncio.run(tool_write(str(target), "export const x = 1\n"))
    assert "Wrote" in result["output"]
    assert target.read_text() == "export const x = 1\n"


def test_tool_write_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c.ts"
    asyncio.run(tool_write(str(target), "hi"))
    assert target.exists()


def test_tool_write_overwrites(tmp_path):
    target = tmp_path / "f.ts"
    target.write_text("old")
    asyncio.run(tool_write(str(target), "new"))
    assert target.read_text() == "new"


# ── tool_glob ─────────────────────────────────────────────────

def test_tool_glob_finds_files(tmp_path, monkeypatch):
    (tmp_path / "a.ts").write_text("x")
    (tmp_path / "b.ts").write_text("x")
    (tmp_path / "c.py").write_text("x")
    result = asyncio.run(tool_glob("*.ts", path=str(tmp_path)))
    assert result["count"] == 2
    assert "a.ts" in result["output"]


def test_tool_glob_no_matches(tmp_path):
    result = asyncio.run(tool_glob("*.nonexistent", path=str(tmp_path)))
    assert result["count"] == 0


# ── tool_grep ─────────────────────────────────────────────────

def test_tool_grep_finds_pattern(tmp_path):
    (tmp_path / "a.ts").write_text("const x = 1\nexport default x\n")
    result = asyncio.run(tool_grep("const", path=str(tmp_path)))
    assert result["matches"] >= 1
    assert "const" in result["output"]


def test_tool_grep_include_filter(tmp_path):
    (tmp_path / "a.ts").write_text("hello")
    (tmp_path / "b.py").write_text("hello")
    result = asyncio.run(tool_grep("hello", path=str(tmp_path), include="*.ts"))
    assert "a.ts" in result["output"]
    assert "b.py" not in result["output"]


def test_tool_grep_no_matches(tmp_path):
    (tmp_path / "a.ts").write_text("world")
    result = asyncio.run(tool_grep("xyznotfound", path=str(tmp_path)))
    assert result["matches"] == 0
    assert "No matches" in result["output"]
