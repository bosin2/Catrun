# Gameplay Expansion Implementation Plan

> For agentic workers: use superpowers:subagent-driven-development; scoped implementation and independent review, then final integration review.

**Goal:** Extend existing Catrun progression, movement and HUD without replacing original gameplay/art.
**Architecture:** Existing FlowSession/save writer own stage progress; LevelFlow world owns clock and lifecycle. Pawn sprint component owns stamina; existing bell action owns use timing. Current minimap presenter supplies cached markers; designer-owned UMG presents state.
**Tech Stack:** UE5.8.2 C++/Blueprint/UMG, Python editor authoring, native automation+PIE.
**Spec:** Docs/Design/GameplayExpansion_Request_2026-11-24.md

**Latest override (2026-11-25):** Stage2 intermediate persistence is cancelled. Restore chapter-unlock-only saving for Stage2, fresh ordinary-start puzzles and full time on Continue/failure/manual restart. Preserve legacy v4 decode/unlocks, ignore its Stage2 intermediate fields, retain Stage1 time persistence. Do not resurrect C/Gate11 capture relocation. Supersedes Task1/verification references to durable Stage2 solves below. Root updates docs and marker fixture; progress owner removes persistence and updates native/process tests; UI worker updates PIE expectations; independent reviewer checks the narrowed rollback before final integration.

## Global Constraints

- Preserve existing uncommitted work, audio, art, tutorial cinematics and previous visual repairs.
- Run124→134 exactly once; walk79/sneak53/enemy/cinematic/statue push speeds unchanged.
- Stamina100/20 drain/1sec delay/25 recovery, editable20 rearm; actual voluntary displacement only.
- Bell5sec, emission0.566667 and action1sec unchanged; actual accepted timestamp shared with UI.
- Continue/failure/full reset all spawn at normal stage start; only full reset clears current-stage solves; never lower unlocks.
- One progression save/writer and failure owner; silent idempotent restore. No new boss AI/enemy buffs.
- Root alone edits engine state, applies scripts, saves maps and runs builds/PIE. Workers write only assigned source/scripts/tests. No worker commits/pushes/build/editor calls. Asset application serial, backups before modifications.
- Work in current editor-connected checkout (main) with verified per-task backups; prior explicit in-place/main workflow and mixed unpublished assets are preserved. Do not create a duplicate project/worktree or commit unrelated work.
- Separate Stage2 art chat exists; inspect compact status before conflicting editor/map operations. Do not send messages to another chat without explicit user authorization. Source work can proceed independently.

## Review Focus

- Late save callbacks after explicit reset/refill: no resurrection or time rewind; T1 tests.
- Captured/timeout/exit racing and engine travel failure: one restart owner, state rollback; T1 tests.
- Held sprint against obstacles/forced travel and long delta crossing recovery: actual spend with no exhaustion oscillation; T2 tests.
- Door restore and streamed/spawned/destroyed markers: correct icon at stable world anchor, no all-actor per-frame search; T3 tests.
- Tutorial intro and options input/focus: resource HUD hidden during protected presentation and does not absorb gameplay keys; T3/T5 PIE.

### Task 1: Progress, restart and stage clock

**Owner:** progress worker, Astra. Source/Catrun/LevelFlow/{CatrunLevelFlow.*,CatrunProgressSave.*,CatrunProgressWriter.*}, new CatrunStageProgress.* if helpful; Interaction/{CatrunStatuePuzzle.*,CatrunPuzzleReset.*}; Monster/CatrunRestartSubsystem.* and only necessary capture/failure admission hooks; relevant existing/new native tests. Config/DefaultGame.ini LevelFlow settings only. Do not touch UI/SettingsWidget or pawn/Bell files.
**Interfaces:** Publish `FCatrunStageClockState` (RemainingSeconds, BudgetSeconds, bTimed, bRunning, WarningFraction, UrgentFraction); `UCatrunLevelFlowSubsystem::GetStageClockState() const` BlueprintPure; `IsGameplayTimeAdvancing() const`. WarningFraction=.3, UrgentFraction=.15 initially, editable in the same clock settings. Keep public `RestartStage()` as explicit full stage reset; failure path distinct. T3 implements `UCatrunPlayerStatusWidget`; T1 LevelFlow owns weak/strong widget pointer, resolves `/Game/UI/Gameplay/WBP_PlayerStatus`, creates once for local playable controller including Tutorial before existing early return, and releases on world teardown. Widget does its own state refresh, no LevelFlow access to its layout. T1 adds narrowly scoped UI/Gameplay cooking entry (runtime path load alone is insufficient).
- [ ] Add strict v4 fields/migration and operation-specific save mutations. Test legacy/invalid bytes, all IDs, duplicate solve, solve→reset→late callback, cross-session remaining time and unlock preservation.
- [ ] Generalize silent final restore and save completion after existing callback/revision revalidation. Preserve unsolved-reset recovery; solved pedestal cannot erase committed progress.
- [ ] Remove Gate11 relocation; accepted failure/manual reset mutations apply only on matching arrival and get persisted. Test rejected/failed travel retains old progress/time.
- [ ] Add stage clock through existing LevelFlow tick/settings, starts after arrival settles; tutorial non-failing. Reuse central failure reservation/notice/restart flow. Test pause and single timeout across capture/travel races.
- [ ] Expose editable budgets/warning values, flush time on menu/normal shutdown, document quiet checkpoint precision if used. Provisional600/900 pending T5 measurement.
- [ ] Test orderly quit with an existing asynchronous write pending; immediate disk reopen must retain last solve/time. Current Deinitialize invalidates weak/generation-gated payloads: add an explicit durable flush boundary. Menu→immediate Continue cannot resurrect prior disk time/state while latest write is pending.
- [ ] Report changed files/interfaces/tests and concerns; root builds, reviewer checks before closure.

### Task 2: Sprint stamina and authoritative bell UI data

**Owner:** movement worker, Sol. New Source/Catrun/Player/CatrunSprintComponent.* (or established pawn folder); Sound/CatrunBellComponent.*; Perception/CatrunCatStateComponent.* effective movement mode only; related tests; Scripts/GameplayRepair/author_player_resources_20261124.py. No LevelFlow/Settings/Minimap edits. No propagation/AI rules changed.
**Interfaces:** `UCatrunSprintComponent::ResolveSprintIntent(ACharacter*, bool)` BP-pure static, component getters GetStamina(), GetMaxStamina(), GetStaminaNormalized(), IsExhausted(), IsSprinting(). Attach canonical cat through authored BP component, not sound-manager one-shot latch. `FCatrunBellStatus` has CooldownSeconds, RemainingSeconds, bCanRing, Reason; enum `ECatrunBellBlockReason` separates None/Cooldown/Hidden/Busy/Airborne/CatHole/Cinematic. `GetBellStatus() const` and authoritative duration getter. Inform T3 exact header paths when ready.
- [ ] Native stamina state tests:100→0 at5sec real sprint; recovery no earlier1sec and full4sec after; zero/blocked/forced move no spend; resetfull;20 threshold.
- [ ] Read actual voluntary horizontal CharacterMovement updates, not input/velocity alone. Avoid teleport/root motion/cinematic spend. Keep existing BP one speed-writer and invoke it only on effective state boundary.
- [ ] Author BP_Cat selector124→134 idempotently, effective run query and real sprint sound mode; preserve119 statue-derived baseline/100 settings cap, walk/sneak, animation bindings. Backup/assert graph anchors before mutation.
- [ ] Read shipping BP LastBellTime and same duration for actual TryBell+HUD; preserve all action order/denials and emit timing. No HUD-driven actor scans. Tests accepted timestamp, cooldown boundary and independent blocked reasons.
- [ ] Author script dry/audit/apply/cold with exact package saves only. Report before root engine apply.

### Task 3: Minimap markers, player status UMG and confirmed restart

**Owner:** UI worker, Astra. Source/Catrun/UI/{CatrunMinimapWidget.*,new CatrunPlayerStatusWidget.*}, minimap presenter files, UI tests; Settings/CatrunSettingsWidget.*; LevelFlow/CatrunPlayHUD.* only fallback restart confirmation; Scripts/GameplayRepair/author_gameplay_hud_20261124.py plus editable SVG/PNG originals under appropriate existing UI source folder. Do not edit LevelFlow subsystem/session files or Config (coordinate contracts).
**Interfaces:** Consume T1 clock state and existing hidden-HUD predicate; T2 component/bellstatus. `UCatrunPlayerStatusWidget` BP base for `/Game/UI/Gameplay/WBP_PlayerStatus`, optional BindWidget UProgressBar StaminaBar/BellProgress + TextBlock remaining/reason/clock, images and editable style. No gameplay input handling. T1 only constructs it; widget reads same state. `RestartFromSettings()` becomes request/confirmation; explicit confirm method does old accepted restart, cancel leaves state untouched. Preserve existing Settings close/focus hooks.
- [ ] Extend presenter registration cache for real native stage exit trigger, dynamic doors+gates and actual tagged CatHole/no-bell boxes; explicit Tutorial BP exit tag/anchor via authoring, authored fixed openings distinct from shut/open doors. Current IsOpen/silent restore is source of truth; test lifecycle and restore state. Do not mark VFX portals as physical exits.
- [ ] Stage2 sliding puzzle gates are ordinary linked mesh actors, not ACatrunDoor: cache owning CatrunStatuePuzzle and read Links[].bCompleted/actual gate state. Include unresolved/restored gates. Existing Settings BP has ConfirmSettingsRestart two-click wrapper; replace/reuse it so the new confirmation occurs exactly once, not two nested confirmations.
- [ ] Shape-distinct navigational markers, green cat/red enemies. Cute candle body/face/flame source at small UI scale. Keep coordinate transforms/topright/Tab-hold and existing map textures; recolor static background once only if needed for contrast (never continuous capture). No per-frame actor enumeration.
- [ ] Create replaceable UMG resource bar using existing font, transparent restrained charcoal/warm-gray accents. Clock tutorial explanation, time warning colors; blocked Bell distinct from cooldown. Use current authoritative getters; hide menu/cinematic/pause without focus.
- [ ] Settings full-reset wording and confirmation with explicit cancel, keyboard escape behavior preserving current menu. Test no mutation before confirm.
- [ ] Author all widgets/icons/map tags through root-applied script preserving originals and exact saved package scope; validate source/tests, report asset list.

### Task 4: Tutorial doors and cat-hole arch

**Owner:** root integration / scoped worker after a slot frees. CatrunDoor.cpp/h and door tests only if verified general hinge defect; Scripts/GameplayRepair/repair_tutorial_passages_20261124.py, Tutorial and mirror maps, existing trim instances. No enemy art packages.
- [ ] Reproduce closed fit/open hinge in actual geometry/PIE. Opposite hinge width calculation may shift3.4cm because local minX=-1.7; repair general pivot/bounds math after controlled test, not per-actor offset workaround.
- [ ] Inspect frame-to-wall side seams vs leaf fit; fit dedicated jamb geometry or existing correct frame at natural scale if needed. Preserve intentional frame-only corridor and closed bedroom.
- [ ] Apply existing60x65 trim unit-scale to wall faces at x=-270,y450/480 if live shape fits. Use existing wall collision as passage filter, trim visual no collision/nav; original cat lane x=-275 remains.
- [ ] Test both door sides/armor hand-driven turn, blocked closed/open passage and sound. Cat bidirectional hole passage, armor block/route-around, camera fit; save/reload both relevant tutorial maps.

### Task 5: Integration, real paths and persistence QA

**Owner:** root engine/build; separate source-only QA helper/reviewer as slots free.
- [ ] Preflight current editor/other-art-task state, back up additional packages before authoring. Close idle editor normally only when needed for DLL linking and no concurrent editor work; build CatrunEditor -NoUBA. Reopen with MCP and separate test user storage where needed.
- [ ] Root applies scripts serially; verify blueprint compile, map saved state and idempotent reapply. No wholesale save-all of unrelated dirty content.
- [ ] Run meaningful native tests + actual PIE for all spec acceptance cases. Cross-process continue uses separate user save; compare stored remaining/solved/unlocks and ordinary start vs manual reset.
- [ ] Measure playable escape/puzzle routes with134+stamina, bell wait/candle avoidance/push timing, including stage start; choose forgiving stage budgets and publish measured basis. No NoCapture or teleport claims disguised as full play; fixtures labelled.
- [ ] Actual UI screenshots/Tab hold/release/door state; level title/options separation, tutorial art and trim comparison. Restore user's save/settings/debug value when tests end.

### Task 6: Independent final review and handoff

- [ ] Independent spec+source+evidence review; resolve significant findings and recheck affected behavior.
- [ ] Docs/Reviews/GameplayExpansion_2026-11-24.md and HANDOFF.md include measured results, limitations, editable paths and actual final status. Preserve paused audio and previous assets. Do not push without a new user request.
