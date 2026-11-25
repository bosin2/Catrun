"""Add-only SoundWave import through Epic UE 5.8 MCP + Python remote execution.

MCP is used for discovery/state and to temporarily enable Epic's loopback Python
bridge. The stock ProgrammaticToolset is NOT a general Python execution API.
No map, Blueprint, gameplay binding, SoundCue or MetaSound graph is edited.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE = Path("C:/Program Files/Epic Games/UE_5.8/Engine")
ROOT = "/Game/Audio/CatAudioDirector"
SCENE = "editor_toolset.toolsets.scene.SceneTools"
APP = "EditorToolset.EditorAppToolset"
OBJECT = "editor_toolset.toolsets.object.ObjectTools"
SETTINGS = {"refPath": "/Script/PythonScriptPlugin.Default__PythonScriptPluginSettings"}
MARKER = "CAT_AUDIO_REPORT:"


class BridgeError(RuntimeError):
    pass


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unwrap(result):
    """Decode Epic's MCP text envelope, leaving actual JSON-valued strings intact."""
    if result.get("isError"):
        raise BridgeError(str(result.get("content", result)))
    if "structuredContent" in result:
        value = result["structuredContent"]
    else:
        texts = [c["text"] for c in result.get("content", []) if c.get("type") == "text"]
        text = "\n".join(texts)
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return text
    if isinstance(value, dict) and set(value) == {"returnValue"}:
        return value["returnValue"]
    return value


class UnrealMCP:
    """Serial, loopback-only JSON-RPC client; never retries mutating calls."""
    def __init__(self, endpoint="http://127.0.0.1:8000/mcp", timeout=30):
        url = urllib.parse.urlparse(endpoint)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise BridgeError("Unreal MCP must use local loopback HTTP")
        if url.username or url.password or url.fragment:
            raise BridgeError("Invalid Unreal MCP URL")
        self.endpoint, self.timeout = endpoint, timeout
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self.counter = 0
        self.schemas = {}

    def rpc(self, method, params=None, *, notification=False, read_only=False):
        self.counter += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            payload["id"] = self.counter
        attempts = 3 if read_only else 1
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(self.endpoint, json.dumps(payload).encode(), self.headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    session = response.headers.get("Mcp-Session-Id")
                    if session:
                        self.headers["Mcp-Session-Id"] = session
                    if notification:
                        return {}
                    if "text/event-stream" in response.headers.get("Content-Type", ""):
                        value = None
                        for line in response:
                            if line.startswith(b"data:"):
                                candidate = json.loads(line[5:].strip())
                                if candidate.get("id") == self.counter:
                                    value = candidate
                                    break
                        if value is None:
                            raise BridgeError("MCP stream ended without the matching response")
                    else:
                        value = json.loads(response.read())
                if "error" in value:
                    raise BridgeError(str(value["error"]))
                return value["result"]
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt + 1 == attempts:
                    raise
                time.sleep(0.25 * (2 ** attempt))

    def connect(self):
        info = self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                      "clientInfo": {"name": "cat-audio-director", "version": "1.0"}}, read_only=True)
        self.rpc("notifications/initialized", notification=True)
        names = {x["name"] for x in self.rpc("tools/list", read_only=True)["tools"]}
        if not {"list_toolsets", "describe_toolset", "call_tool"} <= names:
            raise BridgeError("Expected Epic UE 5.8 tool-search API; refusing to guess tool names")
        return info

    def meta(self, name, arguments, *, read_only=True):
        return unwrap(self.rpc("tools/call", {"name": name, "arguments": arguments}, read_only=read_only))

    def describe(self, toolset):
        value = self.meta("describe_toolset", {"toolset_name": toolset})
        if not isinstance(value, dict) or not isinstance(value.get("tools"), list):
            raise BridgeError("Unexpected describe_toolset response")
        self.schemas[toolset] = {t["name"].rsplit(".", 1)[-1]: t for t in value["tools"]}
        return value

    def tool(self, toolset, name, arguments=None, *, read_only=True):
        if toolset not in self.schemas:
            self.describe(toolset)
        schema = self.schemas[toolset].get(name)
        if schema is None:
            raise BridgeError(f"Tool unavailable: {toolset}.{name}")
        args = arguments or {}
        declared = schema.get("inputSchema", {})
        if not set(declared.get("required", [])) <= set(args):
            raise BridgeError(f"Missing arguments for {name}")
        if set(args) - set(declared.get("properties", {})):
            raise BridgeError(f"Undeclared arguments for {name}")
        return self.meta("call_tool", {"toolset_name": toolset, "tool_name": name, "arguments": args}, read_only=read_only)


def inspect_editor(client):
    info = client.connect()
    available = client.meta("list_toolsets", {})
    level = client.tool(SCENE, "get_current_level")
    pie = client.tool(APP, "IsPIERunning")
    settings = client.tool(OBJECT, "get_properties", {"instance": SETTINGS,
                         "properties": ["bRemoteExecution", "RemoteExecutionMulticastBindAddress"]})
    if isinstance(settings, str):
        settings = json.loads(settings)
    return {"status": "connected", "endpoint": client.endpoint, "initialize": info,
            "current_level": level, "pie_running": pie, "toolsets": available,
            "python_remote_settings": settings,
            "integration": "Epic MCP discovery plus temporary loopback Epic Python remote execution",
            "scope": "New SoundWave assets only; no gameplay wiring, SoundCue or MetaSound graph editing"}


def validate_plan(plan, *, allow_mock=False):
    if not isinstance(plan, dict):
        raise BridgeError("Plan must be an object")
    run_id = plan.get("run_id", "")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,79}", run_id):
        raise BridgeError("Unsafe run_id")
    if type(plan.get("mock")) is not bool:
        raise BridgeError("Plan must explicitly declare mock true/false")
    if plan["mock"] and not allow_mock:
        raise BridgeError("Mock import requires --allow-mock as well as --apply")
    assets = plan.get("assets")
    if not isinstance(assets, list) or not assets or len(assets) > 100:
        raise BridgeError("Plan must contain 1..100 assets")
    seen, normalized = set(), []
    for asset in assets:
        name = asset.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
            raise BridgeError("Unsafe asset id")
        if name.lower() in seen:
            raise BridgeError("Duplicate asset id (case insensitive)")
        seen.add(name.lower())
        if asset.get("kind") not in {"bgm", "sfx"} or type(asset.get("loop")) is not bool:
            raise BridgeError("Invalid asset kind/loop")
        path = Path(asset.get("path", ""))
        if not path.is_absolute() or path.suffix.lower() != ".wav" or not path.is_file():
            raise BridgeError(f"Expected an existing absolute WAV path: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != asset.get("sha256"):
            raise BridgeError(f"Source hash mismatch: {name}")
        with wave.open(str(path), "rb") as wav:
            if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2 or wav.getframerate() != 48000:
                raise BridgeError(f"Expected PCM16 48 kHz WAV: {name}")
            expected_channels = 2 if asset["kind"] == "bgm" else 1
            if wav.getnchannels() != expected_channels or wav.getnframes() == 0:
                raise BridgeError(f"Invalid channel count or empty WAV: {name}")
            duration = wav.getnframes() / wav.getframerate()
        normalized.append({**asset, "path": str(path.resolve()), "sha256": digest,
                           "channels": expected_channels, "duration": duration,
                           "asset_path": f"{ROOT}/{run_id}/SW_{name}"})
    return {"run_id": run_id, "mock": plan["mock"], "assets": normalized}


def import_source(plan, project):
    """Script runs in a fresh namespace; it only saves its newly imported objects."""
    payload = repr(json.dumps({"plan": plan, "project": str(Path(project).resolve())}))
    return '''import unreal, json, pathlib, hashlib, traceback
data = json.loads(PAYLOAD)
plan = data['plan']
report = {'status': 'failed', 'run_id': plan['run_id'], 'mock': plan['mock'], 'assets': [], 'scope': 'SoundWave import only'}
def dirty():
    return sorted(str(p.get_path_name()) for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
try:
    actual = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if actual != pathlib.Path(data['project']).resolve():
        raise RuntimeError('Wrong Unreal project: ' + str(actual))
    report['engine_version'] = unreal.SystemLibrary.get_engine_version()
    if not report['engine_version'].startswith('5.8.'):
        raise RuntimeError('This bridge is validated only for UE 5.8')
    if unreal.EditorLevelLibrary.get_pie_worlds(False):
        raise RuntimeError('PIE active: stop before importing')
    report['dirty_before'] = dirty()
    if report['dirty_before']:
        raise RuntimeError('Editor has unsaved packages; save or discard them yourself before importing')
    subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    for row in plan['assets']:
        if subsystem.does_asset_exist(row['asset_path']):
            raise RuntimeError('Existing asset refused: ' + row['asset_path'])
        if hashlib.sha256(pathlib.Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Source changed after preflight: ' + row['id'])
    for row in plan['assets']:
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', row['path'])
        task.set_editor_property('destination_path', row['asset_path'].rsplit('/', 1)[0])
        task.set_editor_property('destination_name', row['asset_path'].rsplit('/', 1)[1])
        task.set_editor_property('automated', True)
        task.set_editor_property('replace_existing', False)
        task.set_editor_property('replace_existing_settings', False)
        task.set_editor_property('save', False)
        task.set_editor_property('factory', unreal.SoundFactory())
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = list(task.get_editor_property('imported_object_paths'))
        expected_object = row['asset_path'] + '.' + row['asset_path'].rsplit('/', 1)[1]
        if paths != [expected_object]:
            raise RuntimeError('Unexpected imported paths: ' + repr(paths))
        sound = unreal.load_asset(row['asset_path'])
        if not isinstance(sound, unreal.SoundWave):
            raise RuntimeError('Imported asset is not SoundWave')
        sound.set_editor_property('looping', row['loop'])
        actual_duration = float(sound.get_editor_property('duration'))
        actual_channels = int(sound.get_editor_property('num_channels'))
        actual_sample_rate = int(sound.get_editor_property('sample_rate'))
        actual_loop = bool(sound.get_editor_property('looping'))
        if abs(actual_duration - row['duration']) > 0.02 or actual_channels != row['channels'] or actual_sample_rate != 48000 or actual_loop != row['loop']:
            raise RuntimeError('Imported audio duration/channels/sample rate/loop mismatch')
        if not subsystem.save_loaded_asset(sound, only_if_is_dirty=False):
            raise RuntimeError('SoundWave save failed')
        report['assets'].append({'id': row['id'], 'path': sound.get_path_name(), 'class': sound.get_class().get_name(), 'duration': actual_duration, 'channels': actual_channels, 'sample_rate': actual_sample_rate, 'looping': actual_loop, 'source_sha256': row['sha256'], 'saved': True})
    report['dirty_after'] = dirty()
    if report['dirty_after'] != report['dirty_before']:
        raise RuntimeError('Unexpected dirty packages remain; inspect before retry')
    report['status'] = 'passed'
except Exception as error:
    report['error'] = str(error)
    report['traceback'] = traceback.format_exc()
    report['partial_import'] = bool(report['assets'])
print('CAT_AUDIO_REPORT:' + json.dumps(report))
'''.replace("PAYLOAD", payload, 1)


def run_remote(client, engine, project, source, state):
    settings = state["python_remote_settings"]
    if settings.get("RemoteExecutionMulticastBindAddress") != "127.0.0.1":
        raise BridgeError("Python bridge is not loopback-bound; refusing to expose it")
    module_path = Path(engine) / "Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py"
    if not module_path.is_file():
        raise BridgeError(f"Epic remote_execution.py missing: {module_path}")
    spec = importlib.util.spec_from_file_location("cat_audio_epic_remote", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    remote = None
    changed = not settings["bRemoteExecution"]
    try:
        if changed:
            if client.tool(OBJECT, "set_properties", {"instance": SETTINGS, "values": json.dumps({"bRemoteExecution": True})}, read_only=False) is not True:
                raise BridgeError("Could not enable temporary Python bridge")
        remote = module.RemoteExecution()
        remote.start()
        deadline = time.monotonic() + 6
        nodes = []
        while time.monotonic() < deadline:
            nodes = [n for n in remote.remote_nodes if Path(n.get("project_root", "")).resolve() == Path(project).resolve()]
            if nodes:
                break
            time.sleep(0.2)
        if len(nodes) != 1:
            raise BridgeError("Expected exactly one local editor for the project")
        remote.open_command_connection(nodes[0]["node_id"])
        result = remote.run_command("exec(compile(" + repr(source) + ", '<cat-audio-import>', 'exec'), {'__name__': '__cat_audio_import__'})",
                                    unattended=True, exec_mode=module.MODE_EXEC_STATEMENT)
        if not result.get("success"):
            raise BridgeError("Unreal Python failed: " + str(result.get("result")))
        for output in result.get("output", []):
            line = output.get("output", "")
            if MARKER in line:
                return json.loads(line.split(MARKER, 1)[1].strip())
        raise BridgeError("No import report returned; inspect editor before retrying")
    finally:
        if remote:
            remote.stop()
        if changed:
            # Never persist project settings; restore the original in-memory value.
            restored = client.tool(OBJECT, "set_properties", {"instance": SETTINGS, "values": json.dumps({"bRemoteExecution": False})}, read_only=False)
            if restored is not True:
                raise BridgeError("Import may have run, but restoring Python bridge failed; inspect editor")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Read actual MCP schemas and editor state")
    imp = sub.add_parser("import", help="Validate plan; mutate editor only with --apply")
    for item in (inspect, imp):
        item.add_argument("--endpoint", default="http://127.0.0.1:8000/mcp")
        item.add_argument("--output", type=Path)
    imp.add_argument("--plan", type=Path, required=True)
    imp.add_argument("--project", type=Path, default=PROJECT)
    imp.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    imp.add_argument("--apply", action="store_true")
    imp.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args(argv)
    output = args.output
    if args.command == "import" and output is None:
        output = args.plan.parent / "unreal_report.json"
    try:
        if args.command == "inspect":
            report = inspect_editor(UnrealMCP(args.endpoint))
        else:
            raw = json.loads(args.plan.read_text(encoding="utf-8-sig"))
            plan = validate_plan(raw, allow_mock=args.allow_mock or not args.apply)
            report = {"status": "dry_run", "run_id": plan["run_id"], "mock": plan["mock"], "assets": plan["assets"], "editor_mutated": False}
            if args.apply:
                client = UnrealMCP(args.endpoint)
                state = inspect_editor(client)
                if state["pie_running"] is not False:
                    raise BridgeError("PIE active or state unknown")
                report = run_remote(client, args.engine, args.project, import_source(plan, args.project), state)
        if output:
            write_json(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] in {"connected", "passed", "dry_run"} else 1
    except Exception as error:
        report = {"status": "failed", "error": str(error), "retry_policy": "Read calls retry; mutations never automatically retry. Inspect partial assets before another run."}
        if output:
            write_json(output, report)
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
