# Stage2 → Stage3 elevator transition

## Where to open
- Active project: `C:/Users/whghk/Catrun/Catrun.uproject`.
- Maps: Content Browser `/Game/Maps`, levels `Stage2` and `Stage3`.
- Search Outliner for `E23_Director`, `E23_View_Warehouse`, `E23_Shot_Ring`.
- Imported models/materials: `/Game/Environment/ElevatorTransition`.
- Animation-only imports: `/Game/Cinematics/ElevatorTransition/Animations` (existing BlackCat skeleton).

## Interaction
Walk out of Stage2 into the safe corridor; pursuit is cleared. The camera-facing corridor wall and roof hide while the cat and floor remain opaque. Continue into the tall, dark storage room. Cabin entry reveals its interior; it does not start the cinematic.

Use the current Interact binding (default F) in the cabin. Input/timer ownership, animated top/bottom letterbox, preparation/jump/pull/landing shots, swaying ascent and fixed below-camera shot are handled by `ACatrunElevatorTransition`. Space skips. Travel uses the existing level-flow subsystem with `FromStage2Elevator`; direct Stage3 entry and restarts do not replay the arrival.

Arrival holds the loaf after the gentle stop, then gives the delayed latch jolt and rise. The cat cautiously walks onto the landing, glances left and right, and the camera blends back to gameplay before the existing Stage3 title appears. The cabin remains walkable with no further F interaction: supported character weight lowers it, and unloading gives a small damped rebound.

## Preservation and validation status
- Original cat mesh and skeleton SHA256 unchanged; 78-bone tracks retained.
- Cold import audit passed: 35 static meshes, 38 authored collision hulls, 10 animation sequences, 8 materials and 21 textures.
- C06 root trajectory reconstructed from delivered 30Hz CSV to match the existing UE skeleton's scale convention; source animation files untouched.
- Source build passed including actual letterbox, dynamic jump camera, latch jolt and invalid-mark skip guard.
- Stage2 201 tagged actors and Stage3 49 actors authored. Superseded doorway actors disabled rather than deleted. Original map backups: `Saved/ElevatorTransition/Backups`.
- Real PIE functional pass: real F input, movement/timer lock, cancellation and exact mesh restoration, pause, normal Stage3 arrival, input/timer restoration, re-entry and Space skip. Evidence: `Saved/ElevatorTransition/Runtime/functional_pass_before_visual.json`. Placement fixtures move the cat between entry points; this is not a full manual corridor traversal.
- Latest incremental build including minimap hide/restore passed. Actual PIE passed all 21 checks, including hidden minimap during the cinematic and original visibility after cancellation (`Runtime/functional_minimap_pass.json`).
- Camera/lighting polish and all three Foley references saved on both Stage2 and Stage3 (`audio_report.json`). Jump/hang, dark ascent and arrival loaf frames reviewed. Final viewport-aspect correction verified in `RuntimeFinal02`: warehouse view has no forced black bars, F adds top/bottom bars and hides the minimap, and all 21 checks pass again. Warehouse entry cat is visible. Latest captures use suffix 00002 (warehouse 00003).

## Known production limits
- Delivered C05 contains startle/tail motion but **no radial tail puff**. Some delivered poses have skin-fold intersections; original appearance/rig remain unchanged.
- Three mechanical cues are provisional local synthesis, not final approved Foley. Cat Audio Director run `CAD_20261125_053416_46364406` passed PCM/loudness/peak/hash QA. New BGM and AI sound-propagation changes are out of scope.
- Final Stage3 reveal is intentionally a short return to the existing playable entrance; the broader vista remains an art-direction choice.

## Reproduction
`Scripts/ElevatorTransition/import_assets.py` imports/validates the isolated assets; set `CATRUN_ELEVATOR_COLD_AUDIT=1` for read-only audit.
`author_scene.py` regenerates only E23-tagged actors and the explicit superseded openings. Do not run while any other editor holds these maps. `import_audio.py` binds the three isolated cues. `run_runtime.ps1` uses isolated saves and real injected F/Space input; no user save slot is used.

Evidence is under `Saved/ElevatorTransition`: `cold_import_audit.json`, `author_report.json`, `Runtime/report.json`, and actual viewport captures.

## Initial handoff (2026-11-25, before revision 2)
Two parallel read-only reviewers checked runtime ownership/cleanup and scene framing. The normal editor was restarted with the latest DLL and Stage2 opened. RuntimeFinal02 completed successfully; no task-owned test editor remains. Original staged work was not committed or published.

## Revision 2 (2026-11-25): gentle arrival and weight response
- Softer cream practical lights: cabin 35 (previous 125), overhead 400 (previous 1100), dimmer bounces. 160 soft drifting warehouse grains and 32 grains traveling with each cabin. A minority of larger foreground motes makes the dust readable at gameplay distance.
- Existing CautiousWalk uses measured stride speed 26 cm/s at 2x, followed by the new same-skeleton 3.2s left/right glance. Original mesh/skeleton/source sequence hashes unchanged. Normal arrival walks out using supported capsule sweeps; it no longer teleports to the release mark.
- Camera trucks with the cat, holds the look, then blends to the real gameplay camera over 1.1s. Existing Stage3 title style appears once afterward, shifted beneath the clock for this arrival only.
- Arrival cabin persists with blocking floor and walls. F has no second interaction. Standing inside loads the spring; leaving unloads it. Ground contact is required; airborne overlap is ignored. During gameplay reentry, the ceiling, two camera-facing board panels and corner frame cut away while their collision remains. The platform and far wall stay visible; the complete cabin restores when the cat leaves. Crafted cinematic shots retain all panels.
- Final expanded PIE passed all 39 checks (`Runtime/revision2_functional_final.json`): F/cancel/pause/normal travel, walk/look/blend/title timing, real walking reentry, moving-base support, rebound, no second interaction, skip and direct Stage3 entry. The first-unloading assertion uses actual support loss, because the rebound peaks near Y=72 before the slowly walking cat reaches Y=50. Measured rebound +0.650 cm.
- Final native weight/title checks: 5 passed with no failures (`ArrivalNativeFinal03/Report/index.json`). Cold map authoring/load/save passed (`ArrivalSceneCold04/run.log`). Final cutaway walking test passed all 8 checks (`Runtime/reentry_visibility_final.json`, `ArrivalReentryVisualFinal02.log`); actual inside/outside captures reviewed, cat visible and complete cabin restored afterward.
- Reproduction: author_arrival_look.py is a separate one-time animation commandlet; author_revision2.py reuses that clip and applies the scene changes. Existing validated dust material is reused on later runs.
- Latest visual evidence: `Runtime/12_CarefulStepOff00002.png`, `13_LookAroundLeft00001.png`, `13b_LookAroundRight00001.png`, `11_Stage3Gameplay00004.png`, `17_ReentryVisibleCat00001.png`, `18_ReentryRestoredCabin00001.png`. These are actual offscreen PIE editor captures, not concept renders. The 39-check run is fixture-assisted at the initial entry points; reentry/exit use real character movement.
- Original BlackCat mesh, skeleton and source PortalInspect SHA256 rechecked unchanged. Task-owned test editors exited normally; no commit or publication was made.
