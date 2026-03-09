#!/usr/bin/env python3
"""b0 agent daemon — executes tools on local machine via WebSocket."""

import asyncio, json, os, socket, subprocess, sys
from pathlib import Path


def get_daemon_name() -> str:
    # 1. override manual no .env (maior precedência)
    if name := os.environ.get("DAEMON_NAME"):
        return name
    # 2. WSL: env var setada automaticamente pelo subsistema
    if wsl := os.environ.get("WSL_DISTRO_NAME"):
        return wsl
    # 3. hostname como fallback universal
    return socket.gethostname()


async def tool_bash(command, timeout=120, workdir=None, **_):
    cwd = workdir or os.environ.get("DAEMON_WORKDIR", str(Path.home()))
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {"output": (stdout + stderr).decode(errors="replace"), "exit": proc.returncode}
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return {"output": f"Timed out after {timeout}s", "exit": -1}


async def tool_read(file_path, offset=None, limit=2000, **_):
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    if path.is_dir():
        return {
            "output": "\n".join(
                f.name + ("/" if f.is_dir() else "") for f in sorted(path.iterdir())
            ),
            "type": "directory",
        }
    with open(path, "rb") as f:
        if b"\x00" in f.read(4096):
            return {"error": f"Cannot read binary file: {file_path}"}
    lines, start = [], (offset or 1) - 1
    with open(path, "r", errors="replace") as f:
        for i, line in enumerate(f):
            if i < start:
                continue
            if len(lines) >= limit:
                break
            lines.append(f"{i + 1}: {line[:2000].rstrip()}")
    return {"output": "\n".join(lines), "type": "file", "lines": len(lines)}


async def tool_edit(file_path, old_string, new_string, replace_all=False, **_):
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    content = path.read_text()
    if old_string not in content:
        return {"error": "oldString not found in file"}
    count = content.count(old_string)
    if count > 1 and not replace_all:
        return {"error": f"Found {count} matches. Use replace_all=true or add more context."}
    new_content = (
        content.replace(old_string, new_string)
        if replace_all
        else content.replace(old_string, new_string, 1)
    )
    path.write_text(new_content)
    return {"output": "Edit applied.", "replacements": count if replace_all else 1}


async def tool_write(file_path, content, **_):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"output": f"Wrote {len(content)} bytes to {file_path}"}


async def tool_glob(pattern, path=None, **_):
    import glob as g

    d = path or os.environ.get("DAEMON_WORKDIR", str(Path.home()))
    matches = sorted(g.glob(pattern, root_dir=d, recursive=True))[:100]
    return {
        "output": "\n".join(str(Path(d) / m) for m in matches) or "No files found",
        "count": len(matches),
    }


async def tool_grep(pattern, path=None, include=None, **_):
    d = path or os.environ.get("DAEMON_WORKDIR", str(Path.home()))
    args = ["rg", "-nH", "--no-messages", pattern]
    if include:
        args += ["--glob", include]
    proc = await asyncio.create_subprocess_exec(
        *args + [d],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    lines = [l for l in stdout.decode(errors="replace").strip().split("\n") if l][:100]
    return {
        "output": "\n".join(lines) if lines else "No matches found",
        "matches": len(lines),
    }


TOOLS = {
    "bash": tool_bash,
    "read": tool_read,
    "edit": tool_edit,
    "write": tool_write,
    "glob": tool_glob,
    "grep": tool_grep,
}


async def main():
    try:
        import websockets
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets

    api_key = os.environ["B0_API_KEY"]
    name = get_daemon_name()
    url = os.environ.get(
        "WORKER_WS_URL", "wss://lab-ai-worker.pedrohnas0.workers.dev/ws"
    )
    backoff = 1

    while True:
        try:
            async with websockets.connect(
                url,
                additional_headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Daemon-Name": name,
                },
            ) as ws:
                print(f"[daemon] connected as '{name}'", flush=True)
                backoff = 1

                async def heartbeat():
                    while True:
                        await asyncio.sleep(30)
                        await ws.send(json.dumps({"type": "heartbeat"}))

                hb = asyncio.create_task(heartbeat())
                try:
                    async for msg in ws:
                        call = json.loads(msg)
                        if call.get("type") == "heartbeat_ack":
                            continue
                        try:
                            result = await TOOLS[call["tool"]](**call["parameters"])
                        except Exception as e:
                            result = {"error": str(e)}
                        await ws.send(
                            json.dumps({"callId": call["callId"], "result": result})
                        )
                finally:
                    hb.cancel()
        except Exception as e:
            print(f"[daemon] disconnected: {e}. retry in {backoff}s...", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    asyncio.run(main())
