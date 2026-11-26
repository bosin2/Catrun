# Stage2 to Stage3 elevator implementation

Approved scope: build the walkable dark corridor and tall warehouse, assemble the delivered human freight elevator, and play the existing-rig cat cinematic after ceiling-ring interaction. Source authority: visualization handoffs under `C:/Users/whghk/.codex/visualizations/2026/11/25/01a21074-96cb-7900-8565-a34c591a144f`. Preserve unrelated staged work, tutorial, portal arrival, Stage3 objectives and original cat assets. No publishing.

## Tasks
1. Inspect live project/dirty packages and Stage2 exit/Stage3 entrance; snapshot affected packages before authoring.
2. Import delivered static meshes/materials and animation-only clips with existing skeleton into new ElevatorTransition folders. Verify scale, collision and root trajectory.
3. Add native elevator director with remapped interaction, corridor protection, selective visibility, cabin/chain/lamp movement, camera shots, blackout, travel/arrival and robust cleanup. Reuse current flow ownership; preserve Stage1 route.
4. Author Stage2 corridor/warehouse and Stage3 minimal receiving dock, using tagged references. Preserve old map content except explicitly superseded exit blockers/trigger. Add editable LevelSequence presentation assets where appropriate.
5. Compile, run real PIE normal/skip/cancel/re-entry flow and verify collision, input, timer, camera and Stage3 gameplay restoration. Capture actual room/cinematic evidence and report remaining animation defects truthfully.

## Contracts and rulings
- Existing source cat, rig and materials remain unchanged. New animations only; delivered C05 has no radial tail puff and skin folding needs visual review.
- Root trajectory is baked into clips. Do not add Actor jump on top. Import conversion and mesh scale must be measured.
- Cabin floor 220 x 200 cm, pillar 336 cm. Chain translates downward 18 cm; ceiling hides separately. Front open, other sides closed. One overhead shaft beam and cabin iron lantern, dusty air, no bright exterior.
- Departure clips C01-C07, blackout, arrival loaf C08 for readable 1-1.5 sec after gentle stop, delayed docking clank then C09.
- Runtime coding and offline asset authoring can be delegated under subagent-driven-development with disjoint ownership; only coordinator controls the live editor and builds.
- Work directly in the user's active `C:/Users/whghk/Catrun` project: it contains approved deliveries and extensive uncommitted latest work absent from the stale initiating worktree. This is necessary to implement the user's requested live-map changes; never reset, commit or publish the existing index.

## Progress
- Source contracts read. Live MCP and Python verified project Catrun, current map Stage3. No implementation mutations yet.
- Imported 35 meshes / 38 authored UCX hulls / 8 materials / 21 textures / 10 clips. Cold audit passes; original cat mesh and skeleton SHA256 unchanged. New clip root scales normalized against existing Idle; C06 trajectory restored from delivered CSV.
- Native runtime and letterbox compiled successfully. Reviewer found missing latch jolt and destroyed-mark skip guard; fixes ready for incremental build.
- Saved Stage2 201 new tagged actors and Stage3 49 actors. Opened only old Stage2 dark closure and Stage3 start-end wall/trim; original actors disabled, backups retained in Saved/ElevatorTransition/Backups.
- Added corridor cutaway, tall warehouse, 12 crates, single overhead volumetric footprint, drifting dust, local lighting channel and tall elevator. New fixed warehouse camera widened after review to retain entry cat.
- Local provisional 3-cue mechanical Foley uses Cat Audio Director run CAD_20261125_053416_46364406. Numeric QA passed; no new BGM, no paid generation, no AI-hearing changes. Art/listening approval remains separate.
- Actual PIE normal/F/input-lock/timer-lock/cancel/pause/skip/travel checks passed. Saved functional_pass_before_visual.json preserves this run. Latest minimap hide/restore build passed. Camera/light polish and final visual recheck remain pending; the user is currently playing Stage2 in PID 12376, which locks the map. Do not interrupt their play. Scripts/ElevatorTransition/run_runtime.ps1 uses isolated saves and offscreen windows.

- Follow-up: two parallel read-only reviewers checked runtime cleanup and scene framing. Corrected warehouse entry wall/lintel occlusion by moving the camera inside the room; widened near-entry framing. Saved both maps and Foley bindings. Latest PIE passed 21 checks including minimap hide/cancel restoration. Native camera aspect bars disabled in E23 cameras so F-triggered Slate bars own the cinematic effect. Final aspect-adjusted captures reviewed: entry cat visible, no pre-F camera bars, actual F letterbox and hidden minimap confirmed. RuntimeFinal02 passes all 21 checks.

## Revision 2: approved arrival walk and persistent weighted cabin
- Softer cream lighting, lantern 125 to 35, overhead 1100 to 400; warehouse dust 55 to 160 soft grains, plus 32 moving grains per cabin. Applies only E23 assets and lights.
- New derived 3.2-second ArrivalLookAround clip on the same 78-track skeleton. Original mesh, skeleton and PortalInspect hashes retained. Root and paws remain stationary; head/neck scan plus/minus 24 degrees with matching endpoints.
- Grounded cautious exit to the original supported release (150,-110,26.2), using existing in-place CautiousWalk at 2x and measured 26 cm/s. Existing PlayerStart remains unchanged. Look, 1.1s cubic blend to actual gameplay camera, then existing Stage3 title presenter.
- Cabin remains a collidable, re-enterable object without interaction. Ground-supported character mass drives a bounded spring: reference 4 cm sag, maximum 6 cm down and 1.25 cm up; airborne overlap is excluded. Gameplay reentry hides the ceiling, two camera-facing board panels and corner frame visually, preserving their collision; the floor and far wall remain visible. Crafted shots retain all panels.
- Final native tests: 5 passed (3 weight, Stage2 title regression, Stage3 title timing). Expanded real PIE: 39 passed, including actual walking reentry, floor carrying the cat, first-unloading rebound, title after camera blend, skip and direct Stage3 arrival. Final cutaway walking test: 8 passed, and actual inside/outside screenshots show the cat and the restored cabin. All task-owned test editors exited normally.
- Reproduce base geometry with author_scene.py, then run author_revision2.py to restore arrival bindings, light/dust overrides and the stage title actor.

- First expanded real PIE run passed 32 checks. Its measured first unloaded rebound peaked at +0.649 cm; loaded transient minimum -4.646 cm, then settled. Last visual fixes: truck the exit camera with the walking cat; preserve a clear release position for the actual gameplay camera; offset only the live Stage3 arrival title below the existing clock.
- Forced regeneration/recompile of the elevator headers and generated translation unit resolved a cold map-load GC crash after the private class layout changed. Cold authoring then succeeded; no source cat assets needed replacement. Exact original crash cause is not proven beyond this successful rebuild/reload.

## Revision 3 (2026-11-25 23:35 KST): applied to main and verified after restart
- Floor-level face shot restored, surroundings/minimap hidden from cabin entry, and F camera blend before the jump. Scope and limits: `ElevatorTransition_Handoff_20261125.md`.
- Main Stage2: `E23_Shot_Below` moved to `(729,-1310,14)` with FOV 36, plus 31 visibility tags. 33 editor mutations; only `/Game/Maps/Stage2` saved. Receipt `Saved/ElevatorTransition/live_departure_apply.json`; read-only recheck after saving passed.
- Active module is `UnrealEditor-Catrun_ElevatorRevision3.dll` (manifest committed, canonical DLL unchanged). The editor was closed normally with no unsaved changes and relaunched; PID 43664 loaded it.
- Main-project offscreen PIE with isolated saves: 58 checks passed on d3d12 (`MainRevision3_02_D3D12.log`, `Runtime/report.json`); floor face shots inspected and matched against the candidate. The d3d11 run also passed 58 but rendered the face nearly black, probably missing indirect light, so use `-RHI d3d12` for visual review.
- Limits: entry points are placement fixtures, not a full manual playthrough. No commit or push.
