"""Prepare the isolated Revision 3 project; never build or launch an editor.

Only Content/Maps is writable QA content. All other content directories, Plugins,
Source, and Scripts are junctions to the main project and MUST be used read-only.
Existing copied files are retained so rerunning preparation cannot erase QA work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from datetime import datetime, timezone


MAIN_ROOT = Path(r"C:\Users\whghk\Catrun")
CANDIDATE_ROOT = Path(
    r"C:\Users\whghk\.codex\workspaces\ElevatorRevision3_20261125_01a21074\Catrun"
)
CANDIDATE_DLL = "UnrealEditor-Catrun_ElevatorRevision3.dll"
CANDIDATE_PDB = "UnrealEditor-Catrun_ElevatorRevision3.pdb"


def normalized(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_reparse(path: Path) -> bool:
    if not os.path.lexists(path):
        return False
    return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def require_physical(path: Path) -> None:
    """Reject junction/symlink ancestors before writing any candidate file."""
    for part in (path, *path.parents):
        if is_reparse(part):
            raise RuntimeError(f"Writable path has a reparse point: {part}")


def physical_directory(path: Path) -> None:
    require_physical(path)
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError(f"Expected a physical directory: {path}")


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def copy_if_absent(source: Path, destination: Path, copies: list[dict]) -> None:
    if is_reparse(source) or not source.is_file():
        raise RuntimeError(f"Copy source must be a regular file: {source}")
    physical_directory(destination.parent)
    require_physical(destination)
    source_hash = sha256(source)
    if destination.exists():
        if not destination.is_file():
            raise RuntimeError(f"Expected copied file: {destination}")
        action = "preserved_existing_copy"
    else:
        shutil.copy2(source, destination)
        if sha256(source) != source_hash or sha256(destination) != source_hash:
            raise RuntimeError(f"Source changed during copying; inspect copy: {source}")
        action = "copied"
    copies.append(
        {
            "source": str(source),
            "destination": str(destination),
            "action": action,
            "source_sha256": source_hash,
            "destination_sha256": sha256(destination),
        }
    )


def copy_tree(source: Path, destination: Path, copies: list[dict]) -> None:
    if is_reparse(source) or not source.is_dir():
        raise RuntimeError(f"Copy tree must be a physical directory: {source}")
    physical_directory(destination)
    for entry in sorted(source.iterdir()):
        if is_reparse(entry):
            raise RuntimeError(f"Unexpected reparse point in copied tree: {entry}")
        if entry.is_dir():
            copy_tree(entry, destination / entry.name, copies)
        else:
            copy_if_absent(entry, destination / entry.name, copies)


def ensure_junction(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Junction source does not exist: {source}")
    physical_directory(destination.parent)
    if os.path.lexists(destination):
        if not is_reparse(destination) or normalized(destination.resolve()) != normalized(
            source.resolve()
        ):
            raise RuntimeError(f"Refusing to replace a different existing path: {destination}")
        return
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise RuntimeError("PowerShell is required to create Windows junctions")
    environment = os.environ.copy()
    environment["CATRUN_REVISION3_JUNCTION_SOURCE"] = str(source)
    environment["CATRUN_REVISION3_JUNCTION_DESTINATION"] = str(destination)
    subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; "
            "New-Item -ItemType Junction "
            "-Path $env:CATRUN_REVISION3_JUNCTION_DESTINATION "
            "-Value $env:CATRUN_REVISION3_JUNCTION_SOURCE | Out-Null",
        ],
        env=environment,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if not is_reparse(destination) or normalized(destination.resolve()) != normalized(
        source.resolve()
    ):
        raise RuntimeError(f"Junction verification failed: {destination}")


def write_json(path: Path, value: dict) -> None:
    physical_directory(path.parent)
    require_physical(path)
    temporary = path.with_name(path.name + ".revision3-tmp")
    require_physical(temporary)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def prepare(source: Path, candidate: Path) -> dict:
    if os.name != "nt":
        raise RuntimeError("This preparation script requires Windows")
    if normalized(source) != normalized(MAIN_ROOT) or normalized(candidate) != normalized(
        CANDIDATE_ROOT
    ):
        raise RuntimeError("This script is restricted to the reviewed main and Revision 3 paths")
    physical_directory(candidate)
    copies: list[dict] = []
    junctions: list[dict] = []
    copy_if_absent(source / "Catrun.uproject", candidate / "Catrun.uproject", copies)
    copy_tree(source / "Config", candidate / "Config", copies)
    copy_if_absent(
        source / "Saved" / "ElevatorTransition" / "cold_import_audit.json",
        candidate / "Saved" / "ElevatorTransition" / "cold_import_audit.json",
        copies,
    )
    for name in ("Plugins", "Source", "Scripts"):
        ensure_junction(source / name, candidate / name)
        junctions.append({"path": str(candidate / name), "target": str(source / name)})
    content = candidate / "Content"
    physical_directory(content)
    for entry in sorted((source / "Content").iterdir()):
        destination = content / entry.name
        if entry.name == "Maps":
            copy_tree(entry, destination, copies)
        elif entry.is_dir():
            ensure_junction(entry, destination)
            junctions.append({"path": str(destination), "target": str(entry)})
        else:
            copy_if_absent(entry, destination, copies)
    if not (content / "Maps").is_dir() or is_reparse(content / "Maps"):
        raise RuntimeError("Content/Maps must be an independent physical copy")
    binaries = candidate / "Binaries" / "Win64"
    physical_directory(binaries)
    require_physical(binaries / CANDIDATE_DLL)
    require_physical(binaries / CANDIDATE_PDB)
    manifest_source = source / "Binaries" / "Win64" / "UnrealEditor.modules"
    manifest = json.loads(manifest_source.read_text(encoding="utf-8-sig"))
    if not manifest.get("BuildId") or "Catrun" not in manifest.get("Modules", {}):
        raise RuntimeError("Main module manifest is missing BuildId or Catrun")
    manifest["Modules"]["Catrun"] = CANDIDATE_DLL
    write_json(binaries / "UnrealEditor.modules", manifest)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "main_project": str(source),
        "candidate_project": str(candidate),
        "candidate_dll": str(binaries / CANDIDATE_DLL),
        "candidate_pdb": str(binaries / CANDIDATE_PDB),
        "build_id": manifest["BuildId"],
        "writable_content_for_qa": str(content / "Maps"),
        "read_only_usage_junctions": junctions,
        "copies": copies,
        "main_manifest_sha256": sha256(manifest_source),
        "compiled": False,
        "editor_started": False,
        "warning": "Junctions are shared paths, not OS-enforced read-only mounts. "
        "QA must save only its copied Stage2 map through Unreal APIs; never save linked assets.",
    }
    report_path = candidate / "Saved" / "ElevatorTransitionRevision3" / "preparation.json"
    write_json(report_path, report)
    return {
        "candidate_project": str(candidate / "Catrun.uproject"),
        "preparation_report": str(report_path),
        "build_id": manifest["BuildId"],
        "new_copies": sum(item["action"] == "copied" for item in copies),
        "preserved_copies": sum(item["action"] == "preserved_existing_copy" for item in copies),
        "junction_count": len(junctions),
        "compiled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=MAIN_ROOT)
    parser.add_argument("--workspace", type=Path, default=CANDIDATE_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(prepare(arguments.source_root, arguments.workspace), indent=2))


if __name__ == "__main__":
    main()
