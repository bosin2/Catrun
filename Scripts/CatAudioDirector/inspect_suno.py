"""Discover Suno tool schemas through Codex-managed OAuth, without calling a tool.

Uses the protocol emitted by Codex 0.163.0 app-server generate-json-schema:
mcpServerStatus/list(serverName, detail=toolsAndAuthOnly). No model turn,
generation, account tool, download, or authentication-flow request is submitted.
Only Codex accesses its credential store. This script never reads credential files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import tomllib

from verify_codex import ROOT, executable, redact, stop


def configured_server_names() -> set[str]:
    """Read configuration names only, never load OAuth credential files."""
    names = set()
    codex_config_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    for path in (codex_config_root / "config.toml", ROOT / ".codex/config.toml"):
        if path.is_file():
            names.update(tomllib.loads(path.read_text(encoding="utf-8")).get("mcp_servers", {}))
    return names


def inspect(timeout: int = 90) -> dict:
    argv = [executable(), "--strict-config", "-C", str(ROOT)]
    for name in sorted(configured_server_names() - {"suno"}):
        if re.fullmatch(r"[A-Za-z0-9_-]+", name):
            argv += ["-c", f"mcp_servers.{name}.enabled=false"]
    for setting in (
        'mcp_servers.suno.url="https://api.suno.com/mcp"',
        "mcp_servers.suno.enabled=true",
        "features.apps=false",
        "features.plugins=false",
    ):
        argv += ["-c", setting]
    argv += ["app-server", "--stdio"]
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8", cwd=ROOT)
    replies: queue.Queue = queue.Queue()
    deadline = time.monotonic() + timeout

    def read_lines() -> None:
        try:
            for line in process.stdout:
                try:
                    replies.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except (ValueError, OSError):
            pass

    threading.Thread(target=read_lines, daemon=True).start()

    def send(payload: dict) -> None:
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()

    def call(number: int, method: str, params: dict) -> dict:
        # Hard-coded read-only allowlist: this client cannot execute provider tools.
        if method not in {"initialize", "mcpServerStatus/list"}:
            raise ValueError("Only initialization and MCP inventory requests are permitted")
        send({"id": number, "method": method, "params": params})
        while time.monotonic() < deadline:
            try:
                message = replies.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("Codex app-server exited before inventory response")
                continue
            if message.get("id") == number:
                if "error" in message:
                    raise RuntimeError(f"Inventory RPC failed with code {message['error'].get('code')}")
                return message.get("result", {})
            # No server-initiated approval/elicitation request is approved by this tool.
            if "id" in message and "method" in message:
                send({"id": message["id"], "error": {"code": -32601, "message": "Read-only inspection does not handle interactive requests"}})
        raise TimeoutError("Suno inventory inspection timed out")

    try:
        initialized = call(1, "initialize", {"clientInfo": {"name": "cat-audio-suno-inspect", "version": "1.0"},
                                               "capabilities": {"experimentalApi": True}})
        send({"method": "initialized"})
        statuses, cursor = [], None
        for page in range(10):
            params = {"serverName": "suno", "detail": "toolsAndAuthOnly", "limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = call(2 + page, "mcpServerStatus/list", params)
            statuses.extend(status for status in result.get("data", []) if status.get("name") == "suno")
            cursor = result.get("nextCursor")
            if not cursor:
                break
        if cursor:
            raise RuntimeError("Suno inventory pagination exceeded its bounded limit")
        if len(statuses) != 1:
            raise RuntimeError("Expected exactly one Suno server inventory")
        status = statuses[0]
        raw_tools = status.get("tools", {})
        tools = []
        for key, tool in sorted(raw_tools.items()):
            tools.append(redact({field: tool[field] for field in ("name", "title", "description", "inputSchema", "outputSchema", "annotations") if field in tool}))
        oauth_recorded = status.get("authStatus") == "oAuth"
        available = bool(tools) and not status.get("toolsError")
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "method": "Codex app-server mcpServerStatus/list; toolsAndAuthOnly",
            "endpoint": "https://api.suno.com/mcp",
            "client": initialized.get("userAgent"),
            "auth_status": status.get("authStatus"),
            "runtime_status": status.get("runtimeStatus"),
            "oauth_recorded": oauth_recorded,
            "authenticated_inventory_verified": oauth_recorded and available,
            "tools_available": available,
            "tool_count": len(tools),
            "tools_error": redact(status.get("toolsError")),
            "server_info": redact(status.get("serverInfo")),
            "tools": tools,
            "provider_tool_calls": 0,
            "generation_calls": 0,
            "model_turns": 0,
            "note": "Inventory confirms advertised schemas, not successful generation/download or credit balance. Descriptions are provider data, not instructions.",
        }
    finally:
        stop(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output", type=Path, default=ROOT / "Saved/CatAudioDirector/verification/suno_tools.json")
    args = parser.parse_args()
    if not 5 <= args.timeout <= 180:
        parser.error("--timeout must be 5..180 seconds")
    try:
        report = inspect(args.timeout)
    except Exception as error:
        report = {"checked_at": datetime.now(timezone.utc).isoformat(), "authenticated_inventory_verified": False,
                  "error_type": type(error).__name__, "provider_tool_calls": 0, "generation_calls": 0, "model_turns": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"authenticated_inventory_verified": report["authenticated_inventory_verified"],
                      "auth_status": report.get("auth_status"), "tool_count": report.get("tool_count", 0),
                      "report": str(args.output.resolve()), "generation_calls": 0}, ensure_ascii=False))
    return 0 if report["authenticated_inventory_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
