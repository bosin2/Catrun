# Mechanisms03 import handoff

`import_mechanisms.py` owns only new mechanism textures, parents, material instances,
and static meshes. The root writer alone runs Unreal. It never edits levels,
actors, source packages, project settings, or original gameplay collision.

## Prepare the current delivery outside Unreal

```powershell
python C:/Users/whghk/Catrun/Scripts/Stage3/GothicRevision/import_mechanisms.py --freeze
```

The preparation requires Pillow in the external Python interpreter. Unreal only
uses the standard library. All 24 source FBX and blend hashes must match the
manifest; metadata, relevant numeric QA, README, BRIEF, final QA if present, and
15 imported textures are frozen and rehashed after calibration. A stale manifest
or any subsequent source drift refuses import. A final QA file arriving after a
freeze also requires a new freeze. This command is appropriate at each scheduled
delivery check; it does not launch Unreal or import anything.

The immutable freeze path is printed and referenced by
`Saved/Stage3GothicRevision20261125/MechanismImport/latest_freeze.json`.
Missing final QA, stale captures, and unestablished user art approval are recorded
separately; they are not silently relabeled as passed. Root can import a verified
technical batch while final documentation is pending, or pass
`require_final_qa=True` to require the final report's presence. That flag does not
interpret the contents as an approval.

## Root writer: execute in UE Python

```python
import sys, importlib
sys.path.insert(0, 'C:/Users/whghk/Catrun/Scripts/Stage3/GothicRevision')
import import_mechanisms
importlib.reload(import_mechanisms)
report = import_mechanisms.main()  # Or freeze_path=r'.../freeze_<sha256>.json'
assert report['success'] and report['mesh_count'] == 24
```

Destination:
`/Game/Environment/Stage3/GothicRevision_20261125/Mechanisms_<inputhash16>`.
An identical batch resumes only assets bearing matching ownership/hash metadata.
A changed batch creates a separate revision, preserving previous assets. The root
must take mesh paths from the report rather than assume a fixed revision path.

Root-facing report:
`Saved/Stage3GothicRevision20261125/import_report.json`.
The complete batch-specific report remains in `MechanismImport/import_report_<sha256>.json`.
Each `meshes[name]` includes `path`, `bounds`/`bounds_cm`, `materials`, material
slots, collision primitive counts, source bounds, source exporter evidence, and
`axis_mapping_candidates`. AABB symmetry can leave several axis candidates;
those are explicitly ambiguous, not claimed to establish orientation. Check the
asymmetric arch and assembly references before assigning actor rotations.

BaseColor is sRGB; Normal_DX uses normal-map compression with sRGB off and no green
flip; ORM uses masks compression and sRGB off. The new material equation is:

`BaseColor_linear / mean(BaseColor_linear) * ColorTint_linear * Brightness`.

Targets (sRGB bytes): steel 72/71/74, iron 52/50/54, brass 150/134/107,
limestone 119/115/109, dark stone 89/86/82. `ColorTint` and `Brightness` are exposed
on each new MI, with parameter readback checked. ORM channels connect to AO,
roughness, metallic; no emissive output is introduced. Parent materials are
recompiled and all new assets are saved.

Authored UCX primitive counts must match metadata. No automatic collision or
complex-as-simple fallback is introduced. Root can attach visuals to existing
puzzle actors and explicitly disable child-actor collision as required, leaving
the original gameplay colliders authoritative.

## Preparation evidence

Seven offline checks passed: complete 24-mesh freeze, exact linear histogram mean,
missing final QA reporting, drift rejection, stale-manifest rejection, unique
asymmetric Y-axis reflection inference, and 100x-unit mismatch rejection.
Python compilation passed. No Unreal import, shader/runtime verification, or map
save was performed by the preparation agent.

Initial live preparation was correctly refused because the manifest's DockArch
blend hash was stale while the producer was still updating that asset. Read
`MechanismImport/freeze_attempt_report.json` for the latest failed scan; rerun the
freeze after the producer refreshes the delivery manifest.
