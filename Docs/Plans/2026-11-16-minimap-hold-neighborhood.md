# Minimap hold, neighborhood and metallic presentation

## Spec and global constraints

Latest user requests: Tab held slightly enlarges the existing corner minimap; releasing returns to compact. Compact map follows the cat and covers more than the gameplay view. Background more transparent, thin shiny metallic border. No Tab hint and no centered modal expansion.

Defaults: hold size multiplier 1.25; neighborhood coverage 1.30 times gameplay camera width (square map also covers the gameplay height); retain gameplay yaw/pitch and upright markers. Keep authored top-right anchors, margins and compact size. Background alpha approximately 0.10, thin silver-blue metallic rim with restrained highlights. Appearance remains editable in UMG/assets; math and input in C++.

Preserve unrelated audio/tool files, maps, settings and gameplay rules. User's other-project UnrealEditor must not be controlled or closed. Main workspace is previously authorized; no commit/push requested now. Root alone runs Catrun commandlets/build. No desktop input needed. Tests must distinguish isolated/runtime automation from actual manual play.

## Task 1: Native behavior and regressions

Own Source/Catrun/UI/CatrunMinimapWidget.h, .cpp, and UI/Tests/CatrunMinimapTests.cpp only. Replace press-toggle/input bindings with per-widget-frame held Tab sampling guarded by current gameplay eligibility and viewport focus. Raw FSceneViewport key state is cleared on focus loss/deactivation; remove unneeded input-stack mutation. Settings/cinematic/catch/transition interruption resets compact, including while the marker timer is paused. Keep settings keyboard navigation independent.

Replace centered expansion with 1.25 scaling of compact dimensions preserving anchors/alignment/offsets and bounded by available viewport. Keep no animation overengineering.

Add player-centered local camera projection using actual orthographic camera width/aspect. Screen plane coverage is 1.30 times actual gameplay footprint, square map. Handle invalid/no pawn/camera without nonfinite transforms. If perspective fallback is required derive a sensible ground-plane footprint from actual view, not an unrelated magic zoom. Reuse full-map texture; apply the same affine transform to texture and marker positions. Texture translation must be converted to pixel units for Slate rendering while marker UVs stay normalized. Clip at MapSurface, hide off-window markers rather than clamp them. Expose tuning defaults in widget Blueprint. Preserve existing capture orientation and actor lifecycle cache. Avoid per-frame enemy scans.

Meaningful tests: held/released/repeated Tab and focus/interruption reset policy (real viewport dispatch if feasible); 1.25 anchored layout with small viewport clamps; moving cat remains center; near enemies registered with map and outside local window hidden; local footprint contains gameplay camera footprint; arbitrary capture yaw/rectangular capture; geometry-level image/marker registration at both sizes and noncentral cat. Update obsolete tests asserting centered/latching behavior. Do not run engine/build; root will. Report APIs new authoring script must set and test limitations. No commits or subagents.

## Task 2: Authored frame and saved widget

Own Scripts/Menu minimap authoring/migration scripts only, create new migration for owned existing WBP_Minimap_Floorplan. Update rework_minimap_20261112.py and author_minimap_camera_projection.py expectations as necessary so rerunning tools preserves new behavior. New owned frame texture under /Game/UI/Minimap/Textures (no external asset required), generated deterministically with a thin silver-blue metallic bevel, restrained static glint, alpha 0.10 background. Use a 64px source with 8px9-slice margins to preserve the 2px rim at both widget sizes. The frame was changed from procedural UI material after controlled actual rendering showed material draws omitted and texture draws working; no engine or graphics-setting workaround. The existing floorplan floors are opaque: set MapBackground color alpha 0.68 so actual map does not remain a solid block; keep marker alpha unchanged. Source constants provide color/opacity tuning. Root runs actual asset creation. MapSurface clips transformed image and markers, frame keeps padding 10. Set current C++ defaults explicitly and preserve no hint, markers/classes, dimensions/anchors and all maps. Ownership/source-hash metadata and read-only audit/idempotency required. Root handles actual offscreen UMG rendering and rim/fill pixel checks; do not fake a gameplay screenshot. No engine/editor processes, commits or subagents.

## Verification and integration

Root builds CatrunEditor with -NoUBA, runs relevant native automation and cold asset audit; renders actual saved UMG offscreen if available. Independent reviews for requirements and correctness, final broad review. Preserve/restore any test-modified user save/settings. Update HANDOFF with exact evidence and limitations. Do not claim manual gameplay unless actually performed.
