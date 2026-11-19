# Presentation and transition repair — 2026-11-19

Implementation and verification record. Final cold/PIE evidence is appended below.
Base: `0b564e714f3015e9e9922624d8a3250650650ce5` on `main`.
User authorized publishing the completed scope to GitHub main on 2026-11-19. Existing audio and unrelated local work are excluded from this publication and preserved.

## Minimap input and appearance

- Reproduced the Stage1/Stage2 Tab problem through real saved HUD widgets and the viewport/Slate input route. Tab navigation transferred focus to a passive HUD and cleared the viewport key cache. The old widget then collapsed the panel during a hold.
- Input preprocessor now owns only eligible plain Tab holds. Key release, focus loss, settings/console interaction, cinematic lock, and travel clear the hold. Repeats cannot initiate a new hold. UI/rebinding and modified Tab remain available.
- Compact/held/released panel sizes are 240/300/240 in the upper right. Neighborhood coverage increased from 1.30 to 1.80; the panel keeps camera alignment and cat centering. No Tab hint was added.
- Saved panel uses a fixed translucent dark backdrop, existing thin metallic border, and clearer map lines. Existing floorplan textures and map markers were preserved.

Evidence under `Saved/PresentationFix20261119`:

- `Red01/Report/index.json`: one failed test, 45 assertions reproduced the input defect.
- `Green01/Report/index.json`: routed test passed after the input fix.
- `MinimapStyleRouted01/Report/index.json`: same actual saved-HUD route passed with wider view; six frames under `Frames`.
- `MinimapStylePreview01/Report/index.json`: six clean UI test successes including offscreen alpha checks.
- `MinimapStyleAuthor02`, `MinimapStyleCold01`, `MinimapStyleRerun01`: saved the owned panel only, cold audit passed, rerun saved nothing and retained the same hash. All 27 protected packages unchanged.
- Independent source reviews passed, including fixes for author ownership checks, asynchronous texture compilation, and preserving historical preview files.

Input evidence uses synthetic events routed through Slate; it is not a physical-keyboard/manual end-to-end playthrough. The routed test includes ordinary map travel, not the portal sequence.

## Armor detection ring

- Dedicated `/Game/Systems/Sound/M_ArmorDetectionRing` renders a thin 24-dash circle with an empty center. The outer radius stays at the actual 165 cm cat-center detection boundary; existing wall occlusion remains active.
- Armor uses this material while candles retain their filled vision material. Perception, capture, propagation, range, and opacity are unchanged by the display work.
- Actual rendered Stage1 showed the original color was too faint; ring-only emissive gain was adjusted to 12. The saved material is visible in `MinimapStyleRouted01/Frames/Stage1-compact.png`.
- `ArmorTests01/Report/index.json`: 31 AI tests passed (28 clean, three with warnings), including material parent, radius, blocked/open distance texture, and detection boundary assertions.
- Material author/cold reports verify no final shader errors and 932 protected packages unchanged. Independent review passed.

## Mark state and cinematics

The user explicitly requested clearing candle detection state at accepted Stage1 portal entry, not hiding and restoring its visual. Rejected entry must retain the mark; an admitted but cancelled cinematic must not resurrect it. A fresh later candle detection may mark normally.

- `MarkRedBuild02.log`: test-only build succeeded.
- `MarkRed01/Report/index.json`: two new regressions reproduced the missing accepted-entry call, uncleared follower timers/target cache, and an arrived follower stuck after presentation suspension. The admission fixture was corrected to provide a valid tagged floor before green evidence.
- `MarkGreenBuild.log` succeeded. `MarkGreen01/Report/index.json`: 32 clean and three warning-successes, zero failures/not-run, covering LevelFlow and Monsters. Both new regressions passed cleanly. Independent Astra native review passed; the saved BP hookup subsequently passed actual candle/armor PIE below.
- Stage1's corridor is now 600 cm long (one additional 200 cm modular bay). Its 575-frame sequence uses a slower approach, head/ear inspection, low portal two-shot, side crouch and slowed jump. Actual evaluated approach speed is 28.06 cm/s, without the earlier opening speed surge. The accepted portal call clears the native mark; a collisionless cinematic door proxy closes at the measured hinge while preserving the original door's gameplay collision.
- `DepartureColdRender03` cold audit changed none of 933 packages. Actual sequence evaluation checked support/capsule/camera paths and delayed entry. Render report `DepartureFrames/20261119-162716-393458/report.json` passed framing/restoration checks. RGB comparison found zero visible-cat versus hidden-cat differences at frames 554/558/561/562, proving the cat is behind the portal before the frame-562 hide key. These are evaluated/rendered sequence checks, not manual play.
- Actual `DepartureLightingPIE01` accepted a candle-marked cat, logged native mark removal, and retained the cleared state after abort while restoring input and the door. The revised full denied/abort/re-mark/travel fixture exposed a rollback re-entry defect: after leaving the trigger during the sequence, restoring the starting position could re-enter it during lease cleanup and disturb camera ownership. The new `BlocksExitQualification` guard now covers acquisition, active presentation, cleanup and EndPlay before exit qualification or rearming. The actual teleport/overlap regression reproduced seven failures before the fix and passed after it. Earlier fixture attempts stopped on unsupported placement or real armor capture; these are not counted as passes.
- Stage2 `Stage2CutAuthor02` changed only the existing arrival sequence and director BP. `Stage2CutColdRender01` cold audit changed nothing, preserved the three original gameplay/cosmetic/portal binding GUIDs, and rendered 39 frames with actor restoration and spawnable cleanup. Dedicated fixed face cuts frame 200/306, statue cut 230, statue-to-plate pan, four-second camera pullback and two-second native handoff follow the accepted shot plan. The original version passed full actual PIE lifecycle checks; the subsequent cat-eye POV correction is described below.
- The first arrival PIE screenshot route returned the editor viewport, so those images are explicitly rejected as visual evidence. A bounded probe confirmed an explicit local-controller raw game-viewport route on Stage1; 114 later images used the local-controller raw game viewport. The first five were still stale editor frames and are rejected; actual Stage2 imagery starts at about 0.46 seconds. Therefore zero initial-frame pawn flash is not proven. The cosmetic actor's broad collision flag remains true, as before, while its actual primitives have no collision/overlaps; validation now checks effective query/physics state.

## Bright portal and orbit sparks

- Shared portal shaders now expose saturated blue/cyan/violet color, flow, opacity and intensity controls. The masked depth core retains its original mask and clipping contract. Existing camera/map lighting was not increased globally.
- A single 96-card mesh and unlit additive material provide orbiting small sparks through vertex animation, with no per-particle actors or Blueprint Tick. Both portal presentations use one collisionless, non-overlapping, non-navigation, shadowless component. Arrival shrink/hide/despawn follows frames 62–91.
- Actual transient engine probe passed mesh build, shader compilation, render-buffer UV/normals/colors, component flags and no-dirty-content checks (`Stage2CutRuntime01/portal-probe-passed.json`).
- `PortalStyle/20261119-165759-167074/report.json` author passed and saved exactly eight owned packages (two new), with no unexpected Content changes. First author failed before any save on unconstructed template SCS pointers; final validation checks the actual spawned component/material references. Fresh-process cold reload, no-op author rerun, both sequence renders and actual Stage2 PIE subsequently passed. The final energy-only adjustment and POV revision are recorded below.

## Known boundaries and preservation

Existing Nanite/translucent-wall, Blueprint metadata, and spawn warnings occurred before these changes. Passing tests with warnings are explicitly distinguished from clean passes. No claim of a full manual Stage2 puzzle run is made here.

Original save and editor settings are backed up in `Saved/PresentationFix20261119/Before/manifest.json`; all three were restored byte-for-byte after owned editor shutdown (`restored-user-state.json`). Generated evidence is in `Saved`, and production author scripts are under `Scripts`.

## Final integrated checks and latest user correction

- Full native build succeeded (`RollbackGreenBuild.log`). `FinalAutomation01/Report/index.json` passed **124 tests: 118 clean and 6 warning-successes, zero failures/not-run**. The rollback regression was red before the native change and green afterwards.
- Actual canonical Stage1 PIE `DepartureRuntime/20261119-171706-068124/report.json` passed real candle marking and armor following, busy admission retaining state, accepted admission clearing state, abort camera/door/input restoration, fresh re-mark, full frame-574 departure and qualified Stage2 arrival. Capture-only debug protection was scoped/restored; detection and following used actual game code. The pursuing armor was reset to its original collision-checked transform between independent admission scenarios.
- `DepartureMirrorRuntime/20261119-172703-969415/report.json` passed the same denied/accepted-abort checks on SoundTest_Stage1. Both door bindings resolved to that PIE world, the proxy closed to yaw zero, and original collision/visibility/input restored.
- Actual Stage2 `Stage2ArrivalRuntime/20261119-165823-255079/report.json` passed all 11 shot windows, movement restoration, restart, Continue, real armor capture/reload, abort, direct-load skip, owner deletion, external-camera Stop and possession cleanup. Puzzle transforms remained unchanged and cinematic actors were removed. The first 0.46 seconds lack valid game-backbuffer imagery; they are not visual acceptance evidence. Final native return has a measured one-frame 0.73% ortho-width backstep from cached outgoing camera sampling, followed by the smooth return to width 1170.
- Latest user clarification supersedes the old overhead statue shot: **frames 230–305 use the cat's measured eye position `(1374.727, 3680.140, 33.6515)` and perspective projection**. Only gaze and FOV change from the statue to the pressure plate; the camera does not translate to a quarter view. Face shots, rear walk, portal timing and later gameplay-camera return remain unchanged. The cat stays visible; paired render controls found no visible self-occlusion. `Stage2ArrivalAuthor/20261119-172651-092358/report.json` changed only Puzzle/PuzzleLens and saved only LS_Stage2_PortalArrival.
- `PortalStyleMotion/20261119-171205-765781/report.json` measured eight actual world-time pairs. Sparks changed over time and added 2145–2347 brightened pixels per pair without asset writes. Arrival spark closure uses the portal's existing shrink/hide/despawn timing.
- The first brightness probe was invalid because material instances had not warmed in the live render. It was rejected. The corrected paired probe `PortalStyleEnergy/20261119-172245-826329/report.json` matches original Energy=1.0 and tests 1.8/2.4 at frames 0/23/32. Selected Energy=2.4 raised frame-0 colored p95 luminance from .572 to .743 with no near-white clipping; cyan/violet and the cat outline remain distinct. `PortalStyle/20261119-172616-669164/report.json` changed only the existing scalar in three shared materials. Rim strength, camera/map lighting, depth mask, AI and spark count were preserved. References informed the style only; no stock image was imported.

- `FinalAuthorNoop01` exited zero; Stage2 author `20261119-172804-474496` and portal author `20261119-172813-141592` both saved nothing and changed no Content hashes.
- `FinalColdRender01` exited zero after independent process reload. Stage2 cold `20261119-172959-846238` and portal cold `20261119-173008-289626` passed with saved/changed empty. Final Stage2 render `20261119-173012-581318` passed 43 images and all 76 eye-level perspective frames; final Stage1 render `20261119-173023-436259` passed with actor restoration and no asset writes.
- The six warning-successes include fixture missing-grid/eye-bone warnings, intentionally exercised Blueprint/blocked-path/native-turn fallbacks, and a full-suite RHI reserved virtual-memory budget warning (258 GB reservation versus 256 GB budget). That warning is recorded, not asserted to be a confirmed gameplay VRAM leak or a resolved issue.

- Final changed-version actual PIE `Stage2ArrivalRuntime/20261119-173201-699929/report.json` passed with success=true, error=null, 107 game-backbuffer images and 12 actual POV samples. The live controller projection check confirmed perspective; the eye stayed at the measured height. Root inspected image 51 (statue), 60/61 (plate), 56 (pan) and 10 (bright portal/emergence). The shot metadata records screenshot request time: request 62 at plate frame 300 was rendered after the face cut, so that image is not used as plate evidence. Neighboring 60/61 show the actual complete plate view. Restart/Continue/capture/abort/external camera/possession cleanup passed again.
- Independent Astra source and content review passed after the POV and energy changes. User save and both editor setting files were restored to their original SHA256 values after the owned editor exited. No Catrun editor process remains. `git diff --cached --check` passed before publication.

Publication includes only this repair's source, saved assets, author/verification scripts, plan, review, and new HANDOFF entry. Existing audio, local tool settings, and older unrelated audit edits remain local.
