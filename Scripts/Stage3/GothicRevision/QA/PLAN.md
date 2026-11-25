# Gothic revision independent QA

Authority: complete `Saved/Stage3GothicRevision20261125/user_brief.txt` and
`Docs/Plans/2026-11-25-stage3-gothic-revision.md`. No commit/push. Root executes
all Unreal operations; QA writes only its script and review documents.

## Before/after entry point

With saved `/Game/Maps/Stage3` already loaded outside PIE, import `verify.py` and
call `snapshot('before')` before the first writer. Call `snapshot('after')` after
the final saved map is cold-loaded, then `compare()`. Snapshots refuse overwrite.
Outputs go to `Saved/Stage3GothicRevision20261125/QA`.

Checks intentionally permit new visual actors/lights/materials and replacement
presentation. They preserve original collision components and their transforms,
meshes, collision channels, shape settings, actor identities, puzzle/objective
references, native bounds, seven warehouse blockers and patrol routing. New
ornament/mechanism visuals must not add collision or visibility-trace blockers.
Six requested wallside furniture colliders are allowed but individually reported
for real traversal and LOS verification; static equality alone does not pass them.
Any desired physical
mesh replacement needs an additional explicit collision-equivalence audit;
matching only visual size is insufficient.

## Native traps and safe visual replacement

- `CatrunStatuePuzzle.cpp:48-58` reads **all** registered primitive component
  bounds, including hidden and NoCollision components, for statue, plate and
  gate. It derives the push extent/center, docking seat center, overlap region
  and gate travel from those bounds. `GetActorBounds(False, False)` measures the
  same native quantity; compare center and extent within 0.01 cm.
- Therefore keep the existing actor/root/collider and hide its original mesh
  presentation. Attach a **separate StaticMeshActor** for the counterweight or
  dock visual, with NoCollision and no navigation contribution. Do not add a
  primitive component to the puzzle actor and do not swap its collider mesh.
  Ordinary separate attached actors are outside native own-component bounds.
- Weight visuals must follow the existing statue actor through push, coast,
  seat and reset. Plate visuals must follow its 2 cm press travel. Wall docking
  frame belongs to a separate fixed actor; it must not descend with the plate.
  New visual floor guides must be shallow and must not imply an impassable lip.
- `CanMoveStatue` sweeps a box derived from those bounds, checks blocking Pawn
  responses, and tests floor support with Visibility traces. A supposedly
  decorative collider or a Visibility blocker can silently prevent pushing.
- `Stage3Objectives.cpp:54-82` uses Housing front-local-Y, Ring world position,
  Housing rotation and a fixed mouth track. Keep Housing/Ring/Pin actor transforms
  and links exact; attached visuals cannot shift the actual interaction face.
- `UpdateChain` places each linked actor procedurally. New chain decoration must
  not replace or reorder those references without a new mechanics change.
- Each LockBolt moves **local +Z 16 cm** on release. Attached new bolt visuals
  must move in that direction. Keepers and gates must preserve their existing
  attachment relation; a fixed decorative overlay must not conceal the opening.
- Seven warehouse blocker colliders retain the original positions and LOS roles.
  Hide original furniture presentation and attach changed visuals separately.
  Preserve the original `SoundObstacle`/floor tags and existing perception grid.
- Native notice strings still say statue/plate. No Source edits are authorized
  for this visual task; record this terminology limitation instead of silently
  rewriting gameplay messages.

## Runtime regression required

1. Both original push lanes: forward/reverse/side access, coast stop, exact dock,
   gate opening, child visual follows without leaving a ghost old statue.
2. P2 remains externally locked until all three release devices complete.
3. E1/E2/E3: approach from original valid side, ring reach and bite alignment,
   chain/pin movement, bolt direction, interrupted release and reset.
4. D1/D2/EXIT clearance and exit transition; H1/H2/H3 cat passage and armor block.
5. Warehouse seven-blocker navigation and candle LOS; no new visual affects
   collision/Visibility. Native data equality supports but does not replace play.
6. Enemy skeletal mesh/animation/silhouette preserved; only Stage3 materials differ.

### Dock presentation endpoints and reset

Use native `IsPuzzleSeated(PuzzleId)` as the read-only presentation authority.
It returns initialized link `bPressed`; seating moves the plate before the native
Seated event. Do not infer success from gate height: P2 may be seated while its
external lock remains active. Do not call gameplay setters from the visual BP.

Source endpoints are `Mechanisms03_20261125/Dock/Assemblies/Dock_Approach.json`
and `Dock_Latched.json`. Values below are centimetres, measured relative to each
fixed dock origin. Imported source Y maps to world minus Y; rear remains world
minus Y for both docks. These are endpoint deltas, not additional actor offsets.

| Part | Approach | Latched | Required change |
| --- | --- | --- | --- |
| Capture fork | Z157 | Z138 | Z -19 |
| Cross pin | source Y-7.2, Z157 | Y0, Z138 | world Y -7.2, Z -19 |
| Pressure deck | Z+0.15 | Z-1.85 | Native plate Z -2; avoid applying twice |
| Chain terminal | Z119.836736 | Z125.683999 | Z +5.847263; XY unchanged |
| Arch, floor frame, sheave | Initial fixed pose | Same pose | No movement |
| Short chain | OpenPose mesh visible | Latched mesh visible | Exactly one pose visible |

For each of P1 and P2, record the native seated flag, actor/component transforms,
mesh/visibility state and native bounds before seating, after animation settles,
and after reset. Endpoint tolerance: 0.05 cm for authored targets; native bounds
still require 0.01 cm against baseline. Assert the inverse deltas on reset, no
accumulation across two seat/reset cycles, and no lingering hidden or duplicate
chain. Record positions as world values if the presenter uses separate actors;
do not compare relative transforms from different attachment parents.

Also reset during the cosmetic transition, then seat again. The final pose must
follow the current native state rather than a stale timer/timeline callback.
Saved/checkpoint restoration into an already seated state must show the closed
pose without requiring a fresh interaction event. Invalid/uninitialized puzzle
references must produce a safe open pose without an access error. All new
presentation pieces remain NoCollision and outside native own-component bounds.

### Foreground cutaway

The shader is an absolute-world camera-to-cat cylinder of radius 185 cm, from
camera to 65 cm beyond target `Cat.xyz + (0,0,35)`. It excludes positions below
`Cat.z-26` and is disabled while `Cat.a < 0.5`. It is a hard opacity-mask cut,
not a distance fade or a sphere. Check actual Lobby, Entrance and GateHallExit
views while moving across the cut boundary: cat visible, no dither grain,
no unintended whole-room exposure or detached floating fixtures, stable shadows.
The mask is also evaluated in shadow passes; preserving the original lighting
requires evidence or a dedicated shadow-pass override, not only unchanged
BaseColor/Normal/ORM graph roots. Review already-seated dock and E-device views
to ensure the new cut does not obscure mechanism state with surviving fixtures.
The current shader has `if(IsShadowDepthShader()) return 1.0`; verify its saved
material and the actual moving-camera shadow result rather than expecting a
camera-following hole in the wall shadow.

## Visual evidence required

The director's capture script covers Entrance, Lobby, LowerHall, Exhibition,
Warehouse, CentralCorridor, CatBypass, Altar, UpperCorridor, GateHall,
GateHallExit and Weight1. Obtain all 12 in Lit, BaseColor and DetailLighting.
Compile all assets before capture; prior uncached shaders displayed checkerboard
fallback despite a correct material graph. Use actual possessed player camera.

Review each mode for its own purpose: BaseColor checks material separation and
stone detail; DetailLighting checks local lights/shadows/geometry; Lit checks
black-cat and enemy silhouette, warm fixture motivation, military prop identity,
functional chain connections and clear critical paths. Compare exact saved cat
poses and camera rotations; report any camera-follow positional drift.

Use all **11** current BaseColor targets, including chain/pulley metal 72/71/74.
Representative source-color math and actual rendered BaseColor remain separate.
Original iron may already show no sampled BaseColor variance; compare original
before attributing this to a material correction.

## Final independent review checklist

- Capture validity: use a fresh output folder; reject checkerboard/default
  materials, missing files and images carried over from earlier attempts.
  `capture.py` now waits for 3 PIE game seconds, finishes compilation, lets the
  viewport render for 10 wall seconds and at least 60 Slate callbacks, then
  finishes again. Each view/mode gets its own post-render compilation barrier
  and at least 2 seconds/30 callbacks of settling. Callback counts are not
  claimed as GPU frame counts. Inspect the first Entrance image explicitly.
- Verify process logs contain `Current view mode: Lit`, `VisualizeBuffer`, and
  `Lit_DetailLighting` as appropriate. The old `buffervisualization` VIEWMODE
  token is invalid in installed UE 5.8 and cannot support BaseColor evidence.
  The correct commands are `viewmode VisualizeBuffer` followed by
  `r.BufferVisualizationTarget BaseColor`, and `viewmode Lit_DetailLighting`.
  JSON mode names alone are not proof of active renderer mode. DetailLighting
  should replace diffuse/specular material colors while retaining normal detail;
  it is distinct from LightingOnly. Check CheatManager presence because the
  game viewport silently ignores VIEWMODE without it in non-Debug builds.
- Source basis: UE `ShowFlags.cpp:990,1007` names both modes;
  `GameViewportClient.cpp:3977` dispatches VIEWMODE; `ShowFlags.cpp:403` sets
  DetailLighting diffuse/specular override. `AssetCompilingManager.cpp:674`
  visits registered compilers; `ShaderCompiler.cpp:2827` blocks shader jobs and
  processes pending maps. A pre-PIE barrier cannot cover first-render requests.
- Record saved camera collision-test state after the director's camera update.
  Compare final actual camera yaw/pitch/position and cat positions; disclose the
  camera collision change and resulting framing differences from baseline.
  No static capture or frozen-NPC fixture establishes gameplay traversal or LOS.
- Review all 12 Lit views individually, particularly Lobby cat silhouette,
  Entrance material detail, Warehouse north doorway, both dock approaches and
  GateHallExit contrast. Check room-specific military furnishing, mounted
  weapon contact, dark-stone weight identity, and continuous visible mechanism
  connections. P1 left bypass and P2 east-side clearance remain real runtime
  checks; do not silently reinterpret source rear-world-minus-Y geometry.
- Both dock latch states must show connected routes to gate/bolt, including the
  terminal's 5.847263 cm rise. A fixed route endpoint at the open terminal pose
  requires a visibly adequate junction/stroke housing or a presentation update.
  Follow the endpoint/reset criteria above and confirm the old statue/plate
  presentation does not remain visible underneath new visuals.
- `GPU/report.json` currently records all 12 requested actual GPU cases passing.
  Retain means, target errors, resolution and limitations; this proves material
  representative colors only, not stone grain, final lighting or art approval.
- Cold saved-map structural comparison must pass original room transforms,
  native puzzle bounds/links, E-device references, seven warehouse blockers and
  routes. Report exact protected-hash exceptions caused by other concurrent
  work; never restore or conceal them. No source changes from this visual task,
  no Stage1/2 original substitutions, and no commit/push.
