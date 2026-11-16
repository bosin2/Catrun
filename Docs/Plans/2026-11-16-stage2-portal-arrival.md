# Stage 2 portal arrival cinematic

## Spec / screenplay

User request: "2스테이지 포탈나와서 상황보여주는 시네마틱 대본짠다음에만들어줘".
Screenplay shown before implementation. Approximately 12 seconds, silent visual presentation:

| Time | Picture | Purpose |
| --- | --- | --- |
| 0–3 s | Wide view of the north entrance: blue portal, cat emerges and lands, then moves into the room. Existing `~ 마법회랑 ~` chapter title appears. | Establish arrival without a face close-up. |
| 3–7 s | Slow, broad reveal of the first statue, pressure plate and closed Gate11. | Establish the immediate obstacle without solving it. |
| 7–10 s | Hold the gate view during 7–8 s, then ease toward the player room during 8–10 s. | Show the route ahead and return without a fast orbit or flying through walls. |
| 10–12 s | Return gently to the actual gameplay view and real cat at the original playable start. | Restore control and HUD without a camera snap. |

Timing and composition can be adjusted after rendered inspection. No dialogue or new audio.

## Global constraints

- Preserve accepted Stage1 departure sequence and all prior uncommitted minimap/audio work.
- Trigger only on the existing qualified Stage1 portal → Stage2 travel. Continue, capture restart, menu restart and ordinary direct Stage2 loading skip it.
- Blueprint and editable LevelSequence own choreography, timing, animation, camera and presentation. C++ only owns route qualification and resource/lifetime safety. No native cinematic tick clock.
- Reuse existing art and animation; new assets under `/Game/Cinematics/Stage2/Arrival`.
- Preserve puzzles, doors, AI/perception/sound rules, save semantics and spawn/checkpoint locations.
- Reuse the existing balanced exit presentation lease for input, camera ownership and hostile suspension. Finish, abort, destruction and ownership loss must restore gameplay.
- A sequence-owned cosmetic cat may act while the real pawn remains safely at its start. Its hide track must restore on every stop; no permanent mesh/AnimBP changes.
- Keep the existing stage title presentation. It may run over the opening wide shot; no new duplicate title.
- Work in this already-authorized main workspace without committing/pushing. Root alone runs Unreal and writes binary assets; another project editor is running and must remain untouched.
- Test in hidden/offscreen processes; don't take over the desktop. Disable auto MCP start for commandlets to avoid the other project's server.

## Task 1: Qualify the arrival route

Owner: native implementer. Files: `Source/Catrun/LevelFlow/CatrunLevelFlow.h/.cpp` and narrow LevelFlow automation tests.

1. Add `FromStage1Portal` only to an accepted `CompleteStageForExit` Stage1→Stage2 request; keep tutorial option unchanged.
2. Expose `UCatrunLevelFlowLibrary::IsStage2PortalArrival(WorldContextObject)` as a pure query: exact configured Stage2 destination + explicit URL option + no restart/continue intent. Do not use "not skip intro" as admission by itself.
3. Tests: qualified travel marker, unqualified route and direct load absence, continue/restart isolation and preserved tutorial option.
4. No build, editor, commits, asset writes; root runs those after integration.

## Task 2: Author editable arrival presentation

Owner: authoring implementer. Files: new `Scripts/GameplayRepair/author_stage2_arrival.py` and supporting new arrival-only scripts. Script only until root runs it.

1. Probe current Stage2 geometry, pawn/mesh transform, gameplay camera and source clips. Back up before authoring, audit saved assets in a fresh process.
2. Create 30fps ~12s LevelSequence and a BP director. Use `IsStage2PortalArrival`, per-world one-shot and bounded acquisition retry; acquire `UCatrunExitTransitionComponent` lease. Bind real pawn visibility and use a collision-free sequence-owned visual cat for emergence/landing/walk; preserve the actual pawn start.
3. Reuse existing portal visuals without modifying their source. Prefer a sequence-spawned portal, so gameplay geometry and maps' other entries remain unchanged.
4. No automatic audio, saves or travel. Normal finish restores view smoothly; abort/EndPlay/lease loss release owned resources idempotently. Remember active cinematic cameras before release. Own all spawned visuals and overlays.
5. Place only a director + non-autoplay sequence actor in canonical Stage2, plus mirror if identical safe integration. Do not move existing actors.
6. Fresh-process saved audit checks BP compilation, bindings, track ranges/restore modes and map references; source asset hashes unchanged. Root will render actual sequence samples before acceptance.

## Task 3: Integrate, verify, review

Owner: root; independent final reviewer.

1. Review source/script and build CatrunEditor, preserving other project editor.
2. Run probe → author → cold asset audit; separate map loads to avoid retained-UWorld leak.
3. Render actual sampled sequence frames; adjust visibly obstructed/too-close/fast shots. Inspect emergence, contact, environment reveal, handoff.
4. Test route admission and lease cleanup, and run relevant regression suites. Exercise actual director in a game world/offscreen runtime when feasible; distinguish these from manual play.
5. Independent review of specification, code/graphs and runtime/render evidence. Resolve actionable findings.
6. Update HANDOFF and review report with exact evidence/remaining limits. Close only owned Catrun processes, restore any user save/settings touched by tests.
