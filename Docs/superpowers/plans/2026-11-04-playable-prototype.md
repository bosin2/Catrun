# Catrun playable prototype implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task by task. User approved execution in chat.

**Goal:** A playable MainMenu-to-Stage2 prototype with restored cinematics, coherent AI/interactions and editable presentation.
**Architecture:** Keep the single Catrun module. Shared lifecycle and gameplay state stay native; presentation assets consume explicit events/settings. One writer at a time; main coordinates editor and integration.
**Tech Stack:** Unreal Engine 5.8 C++, Blueprint/AnimBP, Unreal Python and MCP.
**Spec:** Docs/superpowers/specs/2026-11-04-playable-prototype-design.md

**Current checkpoint:** Tasks1–3 and4a–4d have passed independent reviews. Task4d acceptance-script fix round1 is Approved. Task5 live input/real exit overlap checks are recorded, while AI collision integration, fresh full build/automation, selected-map cook and standalone verification remain in progress. The detailed ledger and test boundaries are in `.superpowers/sdd/2026-11-04-playable-prototype/progress.md`; unchecked original steps below are the original plan, not the current completion authority.

## Global Constraints
- Preserve pre-existing local changes, art/layout except requested tutorial placement, and original tutorial gameplay camera.
- C++ owns state/calculation/collision; BP/AnimBP owns simple presentation. Audio assets are deferred. No Stage3 or awakening system.
- Actual live MCP and rendered runtime verification are required; do not infer success from file edits.
- One implementation agent at a time; independent task review then final whole-change review. No remote push.
- Exact denial copy: `방울을 울릴수없습니다`.

## Review Focus
- Fresh menu start vs capture restart must choose different tutorial presentation while preserving playable spawn.
- Multiple action locks and interrupted animations must not leave camera, movement or collision stuck.
- Static settings alone do not prove Stage2 actor/event initialization or propagation visuals.
- Puzzle snapping and sinking gate must not tunnel through actors or retain stale navigation/sound obstacles.
- Existing dirty files are baseline work, not changes attributable to this task.

### Task 1: Runtime flow, restart, feedback and camera settings
**Files:** Source/Catrun/LevelFlow/CatrunLevelFlow.*, CatrunPlayHUD.*, new focused presentation/settings files in LevelFlow if required; Source/Catrun/Monster/CatrunRestartSubsystem.*; Source/Catrun/Sound/CatrunBellComponent.*, CatrunNotice.*; Source/Catrun/LevelFlow/Tests/LevelFlowTests.cpp.
**Interfaces:** Expose Blueprint-callable restart-intro query through the existing LevelFlow subsystem and a short bottom feedback message callable from native/BP bell denial. Store restart intent across level reload. Stage camera settings must be editable, and temporary view targets must not become gameplay camera baselines.
- [ ] Inspect actual code and historic bell denial; preserve existing correct native guards.
- [ ] Implement capture restart intent, first-start clearing, exact denial message, debug-only explanation panels and stage camera tuning. Preserve menu functionality.
- [ ] Add behavior tests for restart-intent consumption and stage profile mapping; build and run focused tests when editor is released by main.
- [ ] Report changed files, interfaces, test evidence and needed BP hooks. Independent review.

### Task 2: AI, collision, capture presentation and basket correctness
**Files:** Source/Catrun/Monster/CatrunArmor.*, CatrunCandle.*, CatrunMarkSubsystem.*; Perception/CatrunCatStateComponent.*; Sound/CatrunSoundSettings.*; Interaction/CatrunBasketInteractionComponent.*, CatrunBasketExitPreview.*; focused native helper/components/tests if needed.
**Interfaces:** Consume Task1 lifecycle hooks. Expose capture phase/animation requests to BP/AnimBP with validated grab/end notifications and fallback timeout. Keep all configurable animation assets and timing editable. Do not change shared API silently.
- [ ] Reproduce/classify current AI and basket faults; inspect capsule responses and existing animation contract.
- [ ] Fix priority/resume and candle wall occlusion, actual capsule blocking and safe capture cleanup; separate capture camera and animation presentation from decision logic.
- [ ] Improve turning timing without double-applying root rotation; optimize basket only measured redundant work.
- [ ] Test sound-vs-mark decisions, LOS, simultaneous/aborted capture and restore, basket blocked exits; build. Independent review.

### Task 3: Weighted statue mechanics and cinematic contract
**Files:** Source/Catrun/Interaction/CatrunStatuePuzzle.*, CatrunPuzzleReset.*, Tests/StatuePuzzleTests.cpp; focused presentation helper if needed.
**Interfaces:** Explicit snap/seat/gate-opening/completion/reset events with puzzle ID; native safety determines gate movement, BP presentation coordinates reveal. Shared input/view ownership follows earlier task interfaces.
- [ ] Add acceleration/deceleration, 80% overlap and swept socket seating; latch state per linked puzzle.
- [ ] Lower gate completely beneath floor, check open/close sweeps, invalidate dynamic obstacles only on actual changes.
- [ ] Implement cancellation/reset-safe cinematic hooks and optional fallback so missing effects cannot trap gameplay.
- [ ] Test threshold boundaries, sideways contact, blocked snap, frame-rate independence and room reset; build. Independent review.

### Task 4: Unreal assets, original intro and unified playable route
**Files:** Scripts/Prototype/*; affected Content/Blueprints, Characters, Systems/Interaction/Puzzles, UI and Maps assets; Config/DefaultGame.ini; relevant Docs/Design.
**Interfaces:** Consume verified native APIs from Tasks1-3. Only this task writes shared maps/BPs. Use current Git object history as recovery input and preserve local originals in Saved/Prototype20261104/Backups.
- [ ] Compare historical intro/sequences/bindings and original maps vs test maps. Restore actual animation sequence and fresh-start playback; skip both intro and key hints on capture restart.
- [ ] Integrate working systems into a single normal map route, fix Stage2 manager/grid/ripple/AI bindings, no-bell-zone placement and tutorial armor placement.
- [ ] Connect AnimBP/capture hooks, camera settings, eye MID, letterbox and dust reveal; keep audio optional. Verify capsule dimensions against models.
- [ ] Compile affected BPs and test real menu button, original sequence animation, progression and restart. Independent review.

Execution split (same approved scope, one writer and independent review per unit):
- Task4a: saved original intro bindings/retry branch. Completed first at user's explicit priority; actual OS Start and independent review passed.
- Task4b: canonical maps/config, tutorial armor placement, no-bell zones and live sound/actor integration. Brief in the plan workspace `task-4b-maps-brief.md`.
- Task4c: armor AnimBP/pickup and cat caught/held presentation, tunable assembly and rendered capture checks. Brief `task-4c-animation-brief.md`; actual metadata preflight is available.
- Task4d: statue eye/letterbox/gate dust and camera presentation, consuming reviewed Task3 interfaces. Prepare the focused brief from Task3's final report before dispatch.

### Task 5: Whole-prototype verification and handoff
**Files:** Scripts/Prototype/verify_*; Docs/Reviews/Prototype_2026-11-04.md; progress ledger.
- [ ] Fresh CatrunEditor build and full project automation suite; inspect errors rather than count only tests.
- [ ] Rendered PIE actual inputs: MainMenu -> Tutorial intro -> Stage1 -> Stage2; capture restart skips intro; stage/puzzle completion, no-bell denial, AI and basket transitions.
- [ ] Capture evidence of camera framing, cinematic sequence, mutually blocking capsules and gate effects. Record automation shortcuts explicitly.
- [ ] Independent whole-change reviewer; main fixes and integrates findings. Preserve a resumable handoff if runtime or usage limits prevent completion.
