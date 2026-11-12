# Stage2 completion and visual repairs

## Spec / Global Constraints
- Latest user request: play remaining Stage2 puzzles through completion, fix cat wall occlusion and rendering-warning causes, align minimap with the gameplay camera angle and remove Tab hint text only.
- Preserve existing dirty work, audio pause, gameplay sound/perception values, original tutorial/cinematics, map collision and puzzle rules. No commit/push. Root alone owns engine/UI/builds and saved assets. User permits Computer Use.
- Minimap uses the whole existing map footprint, projected to match gameplay camera yaw and pitch; map and markers stay registered. Markers remain readable, compact/expanded layouts fit, Tab toggle stays but hint text is removed. No gameplay remapping.
- Diagnose before repairing; do not hide warnings or indiscriminately increase budgets or lower graphics. Restore any test-only save/settings changes.
- Existing project is the authorized dirty main checkout; stay there so live UE assets and existing changes are preserved. Snapshot touched files for per-task diffs. Independent review and root integration required.

## Tasks
### Task 1: Minimap camera projection
Inspect CatrunMinimapWidget and WBP authoring. Implement mathematically consistent yaw/pitch projection for background and all markers, fitting full map to compact/expanded viewport. Source projection/math in C++; appearance/bindings and removal of Tab label in widget authoring. Avoid stretching marker artwork. Only minimap source/tests and a dedicated authoring script may be edited by implementer; root runs scripts. Add meaningful projection tests. Report exact files, no builds/editor/commits/subagents.

### Task 2: Wall occlusion diagnosis and repair
Trace current quarter camera wall-hiding behavior and reproduce actual blocked cat views. Determine why blockers remain, implement targeted general correction preserving collision/perception and restoring original render states. Avoid individually deleting walls or treating one basket as a special case. Validate with real before/after viewpoints and relevant regression coverage.

### Task 3: Rendering warning diagnosis and repair
Attribute always-resident ray tracing geometry to assets/settings with engine evidence. Repair the originating asset/config problem with smallest justified change. Compare actual before/after allocation and rendering. Preserve required visuals; record any environment limitation accurately.

### Task 4: Stage2 completion and integration
Root plays C/B/A and exit through real character movement/push/interaction with AI enabled; position fixtures must be reported separately and do not count as uninterrupted play. Check locks, reveal ownership, capture/recovery, puzzle reset, final exit. Fix observed blockers, build and run appropriate suites; independent final review. Update HANDOFF and report.
### Task 4 observed seating repair ruling
Normal B push reproduced 83.345% overlap with19.711cm lateral drift from inertia, rejected by12cm axis tolerance, and wall prevented push-back correction. Adjust shared axis tolerance to24cm (maximum coast20.833cm plus small margin) while preserving80% overlap/height/rotation/swept collision. Update both authoring and verification values and add regression; this is a common puzzle tuning fix, no per-statue exception.
