"""Reproduce local Codex config/skill checks without printing configuration secrets.

Optional --smoke runs a small read-only model turn and therefore consumes Codex
usage. It disables external MCP servers for that turn and never generates audio.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
ROLES = ["cat_audio_" + role for role in ("director", "bgm", "sfx", "edit", "unreal", "qa")]


def executable() -> str:
    direct = shutil.which("codex.exe")
    if direct:
        return direct
    npm = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@openai/codex/node_modules/@openai"
    candidates = sorted(npm.glob("codex-win32-*/vendor/*/bin/codex.exe"))
    if candidates:
        return str(candidates[0])
    found = shutil.which("codex")
    if found and Path(found).suffix.lower() not in (".cmd", ".bat", ".ps1"):
        return found
    raise RuntimeError("Native Codex executable was not found")


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream:
            stream.close()


def config_check(exe: str) -> dict:
    process = subprocess.Popen(
        [exe, "--strict-config", "-C", str(ROOT), "app-server", "--stdio"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", cwd=ROOT,
    )
    replies: queue.Queue = queue.Queue()
    deadline = time.monotonic() + 120

    def reader() -> None:
        try:
            for line in process.stdout:
                try:
                    replies.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except (ValueError, OSError):
            pass

    threading.Thread(target=reader, daemon=True).start()

    def send(request: dict) -> None:
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()

    def call(number: int, method: str, params: dict) -> dict:
        send({"id": number, "method": method, "params": params})
        while time.monotonic() < deadline:
            try:
                message = replies.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("Codex app-server exited before replying")
                continue
            if message.get("id") == number:
                if "error" in message:
                    raise RuntimeError(f"{method} RPC error code {message['error'].get('code')}")
                return message.get("result", {})
        raise TimeoutError("Codex app-server verification exceeded 120 seconds")

    try:
        init = call(1, "initialize", {"clientInfo": {"name": "cat-audio-config-check", "version": "1.0"}, "capabilities": {"experimentalApi": True}})
        send({"method": "initialized"})
        result = call(2, "config/read", {"includeLayers": True, "cwd": str(ROOT)})
        config = result.get("config", {})
        skills = call(3, "skills/list", {"cwds": [str(ROOT)], "forceReload": True})
        found = [s for item in skills.get("data", []) for s in item.get("skills", []) if s.get("name") == "cat-audio-director"]
        agents = config.get("agents", {})
        servers = config.get("mcp_servers", {})
        expected_urls = {"suno": "https://api.suno.com/mcp", "unreal-mcp": "http://127.0.0.1:8000/mcp"}
        endpoints = {name: {"matches_expected_url": servers.get(name, {}).get("url") == url, "enabled": servers.get(name, {}).get("enabled", False)} for name, url in expected_urls.items()}
        # Suno may be deliberately disabled until OAuth is completed. URL setup
        # and authenticated access are separate claims.
        passed = bool(found and found[0].get("enabled") and agents.get("enabled") and all(x["matches_expected_url"] for x in endpoints.values()) and endpoints["unreal-mcp"]["enabled"])
        return {
            "passed": passed,
            "client": init.get("userAgent"),
            "strict_config": True,
            "project_layer_loaded": any(layer.get("name", {}).get("type") == "project" for layer in result.get("layers", [])),
            "agents": {key: agents.get(key) for key in ("enabled", "max_concurrent_threads_per_session")},
            "servers": endpoints,
            "skill": [{key: s.get(key) for key in ("name", "path", "scope", "enabled")} for s in found],
            "skill_errors": sum(len(item.get("errors", [])) for item in skills.get("data", [])),
        }
    finally:
        stop(process)


def roles_check() -> list[dict]:
    results = []
    for name in ROLES:
        path = ROOT / ".codex/agents" / f"{name}.toml"
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        results.append({"name": name, "path": str(path), "passed": config.get("name") == name and all(isinstance(config.get(key), str) and config[key] for key in ("description", "developer_instructions")), "model_inherited": "model" not in config})
    return results


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if re.search(r"token|secret|password|authorization|credential|api.?key", k, re.I) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"https?://[^\s\"<>]+", "[URL OMITTED]", value)
        value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+\S+)", "[REDACTED]", value, flags=re.I)
    return value


def spawn_evidence(events: list[dict]) -> list[dict]:
    """CLI JSON omits spawn details in 0.163.0; extract only safe metadata.

    Local history is supplementary evidence, not a stable public API. If its
    storage format changes, retain false/unverified instead of guessing.
    Never copy message bodies, secrets, or complete history into the report.
    """
    ids = [e.get("thread_id") for e in events if e.get("type") == "thread.started"]
    if not ids or not re.fullmatch(r"[0-9a-f-]{36}", ids[0] or ""):
        return []
    history = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    records = {}
    for path in history.glob(f"*/*/*/*{ids[0]}.jsonl"):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                    payload = item.get("payload", {})
                    call_id = payload.get("call_id")
                    if item.get("type") != "response_item":
                        continue
                    if payload.get("type") == "function_call" and payload.get("name") == "spawn_agent":
                        args = json.loads(payload.get("arguments", "{}"))
                        if args.get("agent_type") in ("cat_audio_bgm", "cat_audio_sfx"):
                            records[call_id] = {"timestamp": item.get("timestamp"), "agent_type": args["agent_type"], "task_name": args.get("task_name"), "spawn_succeeded": False}
                    if payload.get("type") == "function_call_output" and call_id in records:
                        outcome = json.loads(payload.get("output", "{}"))
                        records[call_id]["spawn_succeeded"] = bool(outcome.get("task_name")) and not outcome.get("error")
                except (ValueError, TypeError):
                    continue
    return list(records.values())


def smoke(exe: str) -> dict:
    # The project and user configuration provide names only. Secret-bearing
    # values and remote URLs are neither copied into this command nor logged.
    names = set()
    for path in (Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml", ROOT / ".codex/config.toml"):
        if path.is_file():
            names.update(tomllib.loads(path.read_text(encoding="utf-8")).get("mcp_servers", {}))
    # --ephemeral in CLI 0.163.0 caused native child spawn to fail with
    # "no rollout found for the thread ID". Keep normal local session storage.
    argv = [exe, "exec", "--strict-config", "--json", "-C", str(ROOT), "-s", "read-only"]
    for name in sorted(names):
        if re.fullmatch(r"[A-Za-z0-9_-]+", name):
            argv += ["-c", f"mcp_servers.{name}.enabled=false"]
    for feature in ("shell_tool", "apps", "plugins", "memories"):
        argv += ["-c", f"features.{feature}=false"]
    prompt = (
        "This is ONLY a Cat Audio Director delegation smoke test. Do not run the normal production pipeline. "
        "Do not use shell, network, providers, Unreal, or file writes. No audio generation, no credits. "
        "Use native custom agent roles cat_audio_bgm and cat_audio_sfx if available: spawn both in parallel, "
        "then wait for both and collect their JSON proposals. Do not substitute another role silently. "
        "BGM worker returns exactly one proposal {id:'smoke_bgm',kind:'bgm',prompt:'quiet playful castle test',duration_seconds:2,loop:true}. "
        "SFX worker returns exactly one proposal {id:'smoke_sfx',kind:'sfx',prompt:'single soft cat bell test',duration_seconds:1,loop:false}. "
        "All project context necessary for this restricted smoke test is in this message; do not inspect files. "
        "Return strict JSON {native_roles_used:boolean,assets:[both proposals],limitation:string_or_null}. "
        "If custom roles are unavailable, state that fact and stop; do not pretend to have spawned them."
    )
    argv.append(prompt)
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", cwd=ROOT)
    timed_out = False
    try:
        try:
            output, _ = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                output, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate(timeout=5)
        events = []
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(redact(event))
        proposals = None
        for event in events:
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                try:
                    candidate = json.loads(item.get("text", ""))
                    if isinstance(candidate, dict) and "native_roles_used" in candidate:
                        proposals = candidate
                except json.JSONDecodeError:
                    pass
        evidence = spawn_evidence(events)
        roles_spawned = {e["agent_type"] for e in evidence if e["spawn_succeeded"]}
        verified = (not timed_out and process.returncode == 0 and
                    roles_spawned == {"cat_audio_bgm", "cat_audio_sfx"} and
                    isinstance(proposals, dict) and proposals.get("native_roles_used") is True and
                    {asset.get("id") for asset in proposals.get("assets", [])} == {"smoke_bgm", "smoke_sfx"})
        return {"executed": True, "model_inherited": True, "external_mcp_disabled": True, "timed_out": timed_out, "exit_code": process.returncode, "events": events, "spawn_evidence": evidence, "proposals": proposals, "native_role_execution_verified": verified, "note": "Native role evidence combines successful spawn records with collected proposals. This does not test production generation or Unreal writes."}
    finally:
        stop(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Also run a 120-second read-only Codex delegation test (consumes Codex usage)")
    args = parser.parse_args()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "project": str(ROOT)}
    try:
        exe = executable()
        report["roles"] = roles_check()
        report["config"] = config_check(exe)
        report["passed"] = report["config"]["passed"] and all(item["passed"] for item in report["roles"])
        if args.smoke:
            report["smoke"] = smoke(exe)
            report["passed"] = report["passed"] and report["smoke"]["native_role_execution_verified"]
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__)
    target = ROOT / "Saved/CatAudioDirector/verification/codex_config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(target), "smoke_requested": args.smoke}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
