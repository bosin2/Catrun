# Gameplay expansion — 2026-11-24

Authority: latest user request in this chat; continuation explicitly authorized after a short pause. These requirements supersede older GDD conflicts about per-run awakening, numeric timers, Stage2 C checkpoints, and stage-start continue semantics. Preserve all unrelated current work and art.

## 2026-11-25 latest override — Stage2 intermediate saves cancelled

User: `스테이지 2 중간저장 롤백해 처음저장방식으로되돌리셈`.
This overrides the Stage2 persistence portions below. Keep chapter unlock/selection and onboarding saves. Stage2 Continue, capture/timeout and manual restart begin at the ordinary authored stage start with initial puzzle/door states and the full configured stage time. Do not reintroduce the older C/Gate11 relocation. Stage2 puzzle completions, countdown, menu return and shutdown do not save intermediate progress. Existing v4 slots remain readable for chapter unlocks, but their Stage2 solved mask and remaining time are ignored; no whole-save deletion or automatic migration write. Stage1 clock persistence and all other requested work remain in scope. The original persistence proposal below is historical where it conflicts with this override.

## Required behavior

1. Find tutorial frame/leaf mismatch using actual transform, scale, pivot, hinge and animation bindings. Repair closed fit and natural opening without changing door rules, armor interaction, collision or sound blocking. Deliberately frame-only corridor must remain frame-only/open; bedroom door remains closed until normal interaction.
2. Inspect existing CatHoleTrim geometry/material. Reuse if it fits at a natural scale, otherwise create through Blender MCP and apply. Preserve cat passage, armor exclusion, camera clearance and sound. Current measured candidate Stage1 trim has clear60x65cm, matching hole; unit scale is preferred, no forced stretching.
3. Keep top-right minimap and press-and-hold Tab enlargement/release. Show actual exit, open/closed doors, cat holes and existing cat/armor/candle. Cat green, enemy red. Candle becomes a readable cute vector-style body+flame icon; exit/door/hole differentiated by shape. Low-saturation charcoal/warm-gray terrain is the adopted proposal, with contrast ahead of ornament. Preserve world mapping, use cached actors/events; no per-frame all-actor scans or ongoing background rendering.
4. Actual BP run124 becomes134 once. Walk79, sneak53, enemies, cinematic and statue pushing remain unchanged. Stamina max100, moving-sprint drain20/sec, recovery after1sec without drain at25/sec. Exhausted switches to walk; rearm at20 (implementation choice, editable). No drain stationary, against a wall, during forced/root motion, cinematics or suspended gameplay. Fresh start/capture/timeout/manual restart full. UI reads that same component; tuning editable.
5. Bell actual5sec cooldown retained. Shipping BP LastBellTime and existing accepted action are authority; emit delay0.566667sec and duration1sec preserved. Display icon/progress/seconds; distinct hidden/busy/airborne/cat-hole/cinematic denials. No second UI clock or new propagation/perception changes.
6. Adopt per-stage remaining-time proposal for Stage1/2. Tutorial explains the clock with no timeout failure. Start countdown only after initial cinematic/arrival readiness and control; pause options/world pause/loading/cinematics/failure, including puzzle reveals. Ordinary bell waits, hiding, observation and stamina recovery consume time. Solve/save never refills. Continue restores remaining; capture/timeout restart preserves progress but refills stage allocation. Full reset clears current progress and refills. Timeout says `마왕이 깨어났다` through existing failure/restart presentation; one owner prevents capture/timeout/exit double restart. No enemy buffs or new boss AI. Configurable budget and warning levels. Provisional build defaults Stage1=600sec, Stage2=900sec; final values require route measurement including waits and starting travel, not declaring config alone complete.
7. Save each newly permanent Stage2 puzzle completion once, including linked statue seat/plate/gate final state. No save for temporary normal door movement, duplicate completion, or unsolved partial statue positions. Continue and gameover start at ordinary stage start and restore all solved links; remove C/Gate11 relocation. Settings `스테이지 처음부터 다시 시작` confirms before clearing only current stage progress/time; retain other-stage progress, all unlocks and onboarding. Restore silently without replay/reward/resave. Fresh enemies/marks/capture/cinematics on reload. Existing save schemas/unlocks compatible; failed/unknown save never overwritten.
8. UI/look/tuning editable via BP/UMG/assets. C++ owns state, persistence and calculations using current managers. No duplicate progression/timer manager. Play HUD hidden in menu/cinematics, nonfocusable and clear of stage title/options. Preserve prior visual repairs, tutorial presentation, audio work and others' edits.

## Persistence decisions

- Extend existing strict v3 scalar archive to v4 with explicit A/B/C solved mask and per-stage remaining milliseconds; preserve legacy v1–3 values. No arbitrary actor snapshots.
- Ordered stage mutations differentiate solve, countdown, failure refill and explicit reset, so stale merges cannot resurrect cleared progress or time.
- Save new completions and accepted reset/refill arrivals; flush current time on menu return and orderly session shutdown. Periodic coalesced quiet time checkpoint may bound unexpected-exit loss without save toasts; document precision and avoid constant writes.
- Direct PIE stays isolated from the user's real slot. Real cross-process persistence verification uses a separate test user directory/backend.

## Deliverable evidence

Actual door opening/closing/armor use and bidirectional cat-hole passage; cached markers+real state+Tab; actual134 run and drain/recovery/exhaustion; bell timestamp/UI agreement; solve→save→failure→start+restored; fresh-process continue; confirmed manual reset retaining unlocks; paused/resumed clock and timeout races; changed-movement puzzle/escape route measurements. Preserve raw failures, fix genuine defects, distinguish fixtures from full traversal.
# 2026-11-25 user clarification

Apply matching cat-hole arch changes in both Tutorial and MainMenu. Inspect each map's actual wall/opening first; preserve MainMenu presentation and existing architecture.
