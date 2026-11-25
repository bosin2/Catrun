"""Validate Revision 3 and optionally activate its DLL for the NEXT editor launch.

Default is a dry run: only a report under the candidate project's Saved directory
is written. --apply stages the tested underscore DLL/PDB and atomically updates
only the main manifest's Catrun mapping. It never changes maps, native sources,
the canonical DLL, other module mappings, or any running editor.
"""

from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
from prepare_revision3_candidate import (  # noqa: E402
    MAIN_ROOT,
    CANDIDATE_ROOT,
    CANDIDATE_DLL,
    CANDIDATE_PDB,
    normalized,
    physical_directory,
    require_physical,
    sha256,
    write_json,
)


EXPECTED_QA_RUN = "revision3_isolation_blend_peek_arrival"
VERIFY_SCRIPT = MAIN_ROOT / "Scripts" / "ElevatorTransition" / "verify_runtime.py"
ENGINE_MANIFEST = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.modules")
MAIN_MANIFEST = MAIN_ROOT / "Binaries" / "Win64" / "UnrealEditor.modules"
MAIN_DLL = MAIN_ROOT / "Binaries" / "Win64" / "UnrealEditor-Catrun.dll"
OWN_SOURCE = (
    MAIN_ROOT / "Source" / "Catrun" / "LevelFlow" / "CatrunElevatorTransition.h",
    MAIN_ROOT / "Source" / "Catrun" / "LevelFlow" / "CatrunElevatorTransition.cpp",
)
CORE_CHECKS = {
    "entry_hides_room_before_F",
    "entry_keeps_cat_and_cabin_visible",
    "isolated_floor_retains_collision",
    "leaving_cabin_restores_scene",
    "F_camera_moves_through_intermediate_view",
    "F_blend_observed",
    "jump_waits_for_camera_blend",
    "below_face_shot_holds_three_seconds",
    "below_camera_stays_on_floor",
    "below_shot_tracks_rising_face",
    "normal_travel_reaches_Stage3",
    "arrival_restores_input",
    "stage_title_after_blend",
    "skip_travel_and_arrival_restore",
    "direct_stage3_does_not_replay",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def identity(path: Path) -> dict:
    require(path.is_file(), f"Required file does not exist: {path}")
    return {"path": str(path), "size": path.stat().st_size, "sha256": sha256(path)}


def records_by_path(records: object, label: str) -> dict:
    require(isinstance(records, list), f"Missing build snapshots: {label}")
    result = {}
    for item in records:
        require(isinstance(item, dict) and isinstance(item.get("Path"), str), f"Invalid snapshot: {label}")
        key = normalized(Path(item["Path"]))
        require(key not in result, f"Duplicate snapshot: {label}: {key}")
        result[key] = item
    return result


def require_snapshot(records: object, path: Path, label: str) -> dict:
    lookup = records_by_path(records, label)
    item = lookup.get(normalized(path))
    require(item is not None, f"Missing snapshot for {path}: {label}")
    current = identity(path)
    require(str(item.get("SHA256", "")).lower() == current["sha256"].lower(), f"SHA256 mismatch: {path}: {label}")
    require(item.get("Length") == current["size"], f"Length mismatch: {path}: {label}")
    return current


def within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def required_qa_checks() -> set[str]:
    tree = ast.parse(VERIFY_SCRIPT.read_text(encoding="utf-8-sig"))
    names = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "check"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    require(CORE_CHECKS <= names, "Current QA script is missing required Revision 3 coverage")
    return names


def validate(build_path: Path, qa_path: Path, qa_log: Path) -> tuple[dict, bytes, dict]:
    require(os.name == "nt", "This publisher requires Windows")
    require(within(build_path, CANDIDATE_ROOT / "Saved"), "Build report must belong to the candidate project")
    require(within(qa_path, CANDIDATE_ROOT / "Saved"), "QA report must belong to the candidate project")
    build = read_json(build_path)
    qa = read_json(qa_path)
    require(build.get("Status") == "linked_candidate_pending_cold_qa", "Build report is not a completed candidate link")
    require(build.get("CompileExitCode") == 0 and build.get("LinkExitCode") == 0, "Compile/link did not succeed")
    require(build.get("MainProtectedUnchanged") is True, "Build did not prove main binary/manifest preservation")
    require(build.get("OwnSourceContentUnchanged") is True, "Build did not prove native source stability")
    require(normalized(Path(build.get("MainProject", ""))) == normalized(MAIN_ROOT), "Unexpected main project in build report")
    require(normalized(Path(build.get("CandidateProject", ""))) == normalized(CANDIDATE_ROOT), "Unexpected candidate project in build report")

    protected = []
    for path in (MAIN_MANIFEST, MAIN_DLL):
        for label in ("MainProtectedBefore", "MainProtectedAfterCompile", "MainProtectedAfter"):
            require_snapshot(build.get(label), path, label)
        protected.append(identity(path))
    sources = []
    for path in OWN_SOURCE:
        for label in ("OwnSourceBefore", "OwnSourceAfterCompile", "OwnSourceAfter"):
            require_snapshot(build.get(label), path, label)
        sources.append(identity(path))

    binaries = CANDIDATE_ROOT / "Binaries" / "Win64"
    candidate_outputs = []
    for name, report_key in ((CANDIDATE_DLL, "CandidateDll"), (CANDIDATE_PDB, "CandidatePdb")):
        path = binaries / name
        require_physical(path)
        require(normalized(Path(build.get(report_key, ""))) == normalized(path), f"Unexpected {report_key}")
        candidate_outputs.append(require_snapshot(build.get("CandidateOutputs"), path, "CandidateOutputs"))
        require(path.stat().st_size > 0, f"Empty candidate output: {path}")

    require(qa.get("success") is True and qa.get("error") is None, "Cold QA did not finish successfully")
    require(qa.get("run") == EXPECTED_QA_RUN and qa.get("phase") == "shutdown", "Unexpected or incomplete cold QA run")
    checks = qa.get("checks")
    require(isinstance(checks, list) and bool(checks), "Cold QA report has no checks")
    require(all(isinstance(item, dict) and item.get("passed") is True for item in checks), "A reported QA check did not pass")
    required = required_qa_checks()
    reported = {item.get("name") for item in checks}
    missing = sorted(required - reported)
    require(not missing, "Required QA checks are missing: " + ", ".join(missing))
    finished = datetime.fromisoformat(build["FinishedUtc"].replace("Z", "+00:00"))
    require(qa_path.stat().st_mtime >= finished.timestamp(), "QA report predates this completed build")
    require(qa_log.stat().st_mtime >= finished.timestamp(), "QA log predates this completed build")
    log = qa_log.read_text(encoding="utf-8-sig", errors="replace").replace("\\", "/").lower()
    loaded_dll = (binaries / CANDIDATE_DLL).as_posix().lower()
    expected_load = f"internalloadlibrary: 'catrun' ('{loaded_dll}')"
    require(expected_load in log, "QA log does not prove a cold load of this candidate underscore DLL")

    original_bytes = MAIN_MANIFEST.read_bytes()
    main_manifest = json.loads(original_bytes.decode("utf-8-sig"))
    candidate_manifest_path = binaries / "UnrealEditor.modules"
    candidate_manifest = read_json(candidate_manifest_path)
    engine_manifest = read_json(ENGINE_MANIFEST)
    build_id = main_manifest.get("BuildId")
    require(isinstance(build_id, str) and bool(build_id), "Main manifest has no BuildId")
    require(build_id == candidate_manifest.get("BuildId") == engine_manifest.get("BuildId") == build.get("BuildId"), "Engine/main/candidate/build BuildId mismatch")
    require(main_manifest.get("Modules", {}).get("Catrun") == MAIN_DLL.name, "Main Catrun mapping changed; do not replace another publication")
    require(candidate_manifest.get("Modules", {}).get("Catrun") == CANDIDATE_DLL, "Candidate manifest does not identify the tested DLL")
    require(not CANDIDATE_DLL.startswith(MAIN_DLL.stem + "-"), "Candidate filename matches the current hot-reload watcher prefix")
    require("Catrun" in CANDIDATE_DLL and CANDIDATE_DLL.endswith(".dll"), "Invalid staged module name")
    main_other = {k: v for k, v in main_manifest["Modules"].items() if k != "Catrun"}
    candidate_other = {k: v for k, v in candidate_manifest["Modules"].items() if k != "Catrun"}
    require(main_other == candidate_other, "Candidate manifest differs in another module mapping")
    next_manifest = copy.deepcopy(main_manifest)
    next_manifest["Modules"]["Catrun"] = CANDIDATE_DLL
    for name in (CANDIDATE_DLL, CANDIDATE_PDB):
        destination = MAIN_MANIFEST.parent / name
        require_physical(destination)
        if destination.exists():
            require(sha256(destination) == sha256(binaries / name), f"Refusing to replace different existing staged file: {destination}")

    evidence = {
        "build_report": identity(build_path),
        "qa_report": identity(qa_path),
        "qa_log": identity(qa_log),
        "qa_verifier": identity(VERIFY_SCRIPT),
        "publisher": identity(Path(__file__).resolve()),
        "main_protected": protected,
        "native_sources": sources,
        "candidate_outputs": candidate_outputs,
        "candidate_manifest": identity(candidate_manifest_path),
        "build_id": build_id,
        "qa_run": qa["run"],
        "required_check_count": len(required),
        "required_checks": sorted(required),
        "reported_check_count": len(checks),
        "verified_cold_load_log_line": expected_load,
        "next_manifest": next_manifest,
    }
    require(hashlib.sha256(original_bytes).hexdigest() == protected[0]["sha256"], "Main manifest changed while validating")
    return evidence, original_bytes, next_manifest


def exclusive_write(path: Path, data: bytes) -> None:
    require_physical(path)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def stage_immutable(source: Path, destination: Path, expected_hash: str) -> dict:
    require_physical(destination)
    if destination.exists():
        require(sha256(destination) == expected_hash, f"Different staged file exists: {destination}")
        return {**identity(destination), "action": "reused_identical_file"}
    temporary = destination.with_name(destination.name + ".revision3-" + uuid.uuid4().hex + ".tmp")
    require_physical(temporary)
    with source.open("rb") as src, temporary.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    require(sha256(temporary) == expected_hash, f"Staged copy failed hash validation: {temporary}")
    # On Windows rename fails if destination already exists; it cannot overwrite an
    # alias another process created between the earlier check and this operation.
    os.rename(temporary, destination)
    require(sha256(destination) == expected_hash, f"Published file failed hash validation: {destination}")
    return {**identity(destination), "action": "staged_new_immutable_file"}


def unchanged(items: list[dict]) -> None:
    for item in items:
        path = Path(item["path"])
        require(sha256(path) == item["sha256"] and path.stat().st_size == item["size"], f"Concurrent change detected: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--qa-report", type=Path, default=CANDIDATE_ROOT / "Saved/ElevatorTransition/Runtime/report.json")
    parser.add_argument("--qa-log", type=Path, required=True, help="Actual cold QA log containing the candidate DLL load path")
    parser.add_argument("--apply", action="store_true", help="Publish the validated DLL/PDB and change the next-launch mapping")
    arguments = parser.parse_args()
    report_dir = CANDIDATE_ROOT / "Saved" / "ElevatorTransitionRevision3" / (
        "Publish_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]
    )
    physical_directory(report_dir)
    report_path = report_dir / "publish-report.json"
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "apply_requested": arguments.apply,
        "main_project": str(MAIN_ROOT),
        "candidate_project": str(CANDIDATE_ROOT),
        "manifest_committed": False,
        "status": "validating",
        "scope": "Next-launch Catrun DLL/PDB and manifest mapping only; no editor or map operations",
    }
    try:
        evidence, original, next_manifest = validate(arguments.build_report, arguments.qa_report, arguments.qa_log)
        report["evidence"] = evidence
        report["status"] = "ready_dry_run"
        write_json(report_path, report)
        if arguments.apply:
            backup = report_dir / "UnrealEditor.modules.before"
            exclusive_write(backup, original)
            report["original_manifest_backup"] = identity(backup)
            report["staged_outputs"] = []
            for item in evidence["candidate_outputs"]:
                source = Path(item["path"])
                report["staged_outputs"].append(stage_immutable(source, MAIN_MANIFEST.parent / source.name, item["sha256"]))
                write_json(report_path, report)
            # Final optimistic concurrency check, immediately before atomic commit.
            unchanged(evidence["main_protected"] + evidence["native_sources"] + evidence["candidate_outputs"])
            unchanged([evidence[key] for key in ("build_report", "qa_report", "qa_log", "qa_verifier", "candidate_manifest")])
            replacement = (json.dumps(next_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            temporary = MAIN_MANIFEST.with_name("UnrealEditor.modules.revision3-" + uuid.uuid4().hex + ".tmp")
            exclusive_write(temporary, replacement)
            require(MAIN_MANIFEST.read_bytes() == original, "Main manifest changed immediately before commit")
            os.replace(temporary, MAIN_MANIFEST)
            report["manifest_committed"] = True
            require(MAIN_MANIFEST.read_bytes() == replacement, "Committed manifest does not match the reviewed mapping")
            unchanged([item for item in evidence["main_protected"] if normalized(Path(item["path"])) != normalized(MAIN_MANIFEST)])
            report["published_manifest"] = identity(MAIN_MANIFEST)
            report["status"] = "published_for_next_launch"
            report["running_editors_reloaded"] = False
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path), "manifest_committed": report["manifest_committed"]}, indent=2))
        return 0
    except Exception as error:
        report["status"] = "failed_after_manifest_commit" if report["manifest_committed"] else "blocked_no_manifest_commit"
        report["error"] = str(error)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
        print(json.dumps({"status": report["status"], "error": str(error), "report": str(report_path)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
