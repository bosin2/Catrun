# Catrun playable prototype — approved scope

Approved in chat on 2026-11-04; user authorizes autonomous implementation, runtime checks, editor launch, local refactoring and asset changes. Record decisions requiring further design approval instead of stopping routine work. Do not publish remotely.

## Outcome
MainMenu -> original tutorial intro -> playable Tutorial -> Stage1 -> Stage2, with capture/restart, bell lure, candle marks, baskets, cat holes and statue puzzles working together. Stage3 is excluded. Use original maps with tested systems migrated, or replace their playable roles with validated maps; do not leave the game split between a functional test route and a broken normal route.

## Binding requirements
- Prove Unreal MCP with a live level/scene query before edits. Verify actual rendered gameplay, not only source or configuration.
- Preserve all pre-existing local work and level art. Historical Git versions are recovery references; do not broadly reset the project.
- Restore original tutorial animation/cinematic structure from Git. Main menu fresh starts show it. Capture restart uses the original playable start and skips intro and key instructions.
- Move tutorial armor back enough for a feasible cat-hole route. Cat, armor and candles block passage through each other using correctly sized collision capsules; capture deliberately overrides then restores collision.
- Keep latest mark call rule: nearest eligible armor within 1500cm, independent of intervening walls/doors; actual movement obeys walls and opens doors. Candle discovery must respect walls.
- Centralize AI information priority (near detection > sound > mark), original sound position vs live mark position, safe action interruption and resume. Improve fast natural turning and capture animation. C++ owns calculations/state/safety; BP/AnimBP owns configurable presentation.
- Cat-hole bell denial must exist and cover actual input plus delayed emission. Display the exact bottom message `방울을 울릴수없습니다` when denied. Preserve original tutorial UI on fresh start; explanatory replacement HUD is debug-only.
- Tutorial gameplay camera unchanged; Stage1 farther, Stage2 farther again. Editable per-stage settings. Capture camera remains, with obstruction-safe framing of both characters.
- Basket: diagnose actual failures/cost before optimization; preserve opening direction, blocked exit checks, mark clearing and complete restoration of state.
- Stage2: weighted push, approximately 80% overlap triggers collision-checked exact seating, eyes turn red. Letterbox and input lock, camera moves to gate, gate sinks completely below floor with dust/visual rumble, camera returns and input restores. A/B/C and room reset work; no duplicate triggers.
- Audio assets are deferred by latest user instruction. Leave optional sound hooks/settings, do not source new audio in this pass.
- Source/asset work must be maintainable and tunable. No speculative framework rewrite or new Stage3/awakening systems.

## Approved defaults and implementation rulings
- 80% means planar overlap of the smaller contact footprint, with same-height and socket-axis validation. Seat latches until room reset. Reset restores eyes, gate and cinematic state.
- During the noninteractive gate reveal suspend hostile gameplay, not the global world clock; allow presentation to run. Restore only owned locks and timer state. Restart/travel takes precedence.
- Stage camera starting factors 1.0 / 1.15 / 1.30; validate projection and collision in the actual BP before applying.
- Sound investigation replacement/resume is a documented gameplay ruling: larger stimulus while travelling, any stimulus during looking, resume valid mark after investigation; near perception dominates. Do not continuously replace a bell target with live cat coordinates.
- Use stock materials/particles and existing eye parameters before adding assets. Any external asset requires recorded source/license and Unreal import verification.

## Validation
Relevant native regression tests, fresh editor build, BP compile, rendered PIE with real input. Check first launch vs restart, transitions, door/cat-hole passage, bell denial and allowed bell, sound field vs visual, candle-to-armor call, basket exits, simultaneous action interruptions, puzzle threshold/reset, collision and capture framing throughout animation. Standalone checks for loading behavior where PIE cannot prove it. Report automated teleport/function-call checks separately from actual gameplay.

## Open design record
Additional design decisions, unverified outcomes and deferred work go in the progress ledger and final handoff; never mark all tasks complete based on code alone.
