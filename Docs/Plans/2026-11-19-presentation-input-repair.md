# Tab input, armor range outline, Stage2 arrival repair

## Latest user clarification — Stage2 cat-eye POV

The statue and pressure-plate reveal must be from the cat's eye level, not an overhead or quarter view. Keep the face cut, then cut to a perspective eye-level view of the statue, pan the cat's gaze toward the floor plate, cut back to the face, and finally return to the gameplay camera. Probe the actual cat pose and obstruction/framing before migrating the existing puzzle camera binding. Preserve the portal choreography, gameplay pawn, puzzle state and other camera cuts. Earlier overhead statue/plate framing and its visual acceptance are superseded by this clarification; their lifecycle evidence remains useful.

## Specification / approved intent

User reports Stage1/2 Tab minimap hold not working, requests dotted armor range circles and a corrected calm Stage2 portal arrival cinematic. Plan presented before implementation. Previous gameplay and presentation work is the baseline; repair these three issues locally.

## Global constraints

- Tab is hold-to-enlarge 240 to 300 in the upper-right, release-to-collapse; local cat-centered map, camera-aligned image/markers and no Tab hint remain.
- Pause/settings/cinematics/focus loss must clear enlargement; UI navigation/key rebinding must retain their own input behavior. Verify the actual Slate/viewport input route, not only a helper bool or forced widget state.
- Armor visualization is a thin dashed circle at the existing effective detection boundary. Preserve detection, capture, obstacles/LOS, sound, candle fans and AI state. Keep visual parameters editable and the visible sectors clipped by existing blockers.
- Stage2 arrival: a wide readable cat emergence/landing, clear first statue C / plate / closed Gate11, restrained same-side camera movement, short portal closure before the reveal, smooth handoff to the original gameplay camera. No 108-degree reverse cut, foreground-wall occlusion or exterior portal remnant.
- Keep original pawn/spawn/checkpoint, anim BP, puzzle/door states and travel qualification. Continue/capture/manual restart skip arrival. C++ owns input and lifetime/routing, BP/Sequence/materials own presentation. Preserve existing stage title.
- Preserve preexisting dirty files and paused audio work. Work in the existing main workspace authorized in this continuing project session. Do not delete old evidence or modify unrelated maps/settings. The user subsequently authorized pushing the completed reviewed scope to GitHub main.
- Root alone owns editor/MCP, builds and binary asset authoring; other agents write only assigned code/scripts. No concurrent implementers. Separate task reviewers and a final independent review follow implementation.
- Back up user saves/settings, use dedicated local MCP if packaged Unreal tools are unavailable, restore test state after owned editor shutdown. Keep current evidence in Saved/PresentationFix20261119.

## Task 1: Reliable minimap hold input

Ownership: Source/Catrun/UI/CatrunMinimapWidget.h/.cpp and UI tests; minimal related input code only if justified by diagnosis. Read Saved/PresentationFix20261119/minimap-diagnosis.md.

Trace owning viewport/focus, Slate Tab navigation and key caching. Add a regression which sends Tab through the real input routing path and proves press/hold/release, settings/cinematic suppression, focus loss and Stage1/2 travel reinitialization. Root runs the failing test before the production fix. Replace the fragile polling edge with the smallest lifecycle-safe input source. Keep per-player ownership and avoid consuming UI Tab. Expose no gameplay debug controls solely for the test. Provide self-review and verification instructions; root runs build/engine checks.

## Task 2: Dashed armor detection outline

Ownership: visual-only armor/fan display code and meaningful display tests, plus a new armor-ring authoring script under Scripts/GameplayRepair. Read Saved/PresentationFix20261119/armor-diagnosis.md.

Reuse current detection-distance texture/blocking logic; create a dedicated armor material copied from existing fan material, leaving candles unchanged. Render a thin inward annulus (start with 5 cm width, 24 evenly spaced dashes), outer radius exactly the effective detection boundary. Preserve trace/depth/ground behavior and current actor controls; tune visual opacity only after actual floor renders. Reference the material so it cooks. Root creates/saves the material in Unreal after reviewing the script. Tests must demonstrate unchanged perception boundaries and wall occlusion plus style separation; actual render verifies empty disk, dashed rim and candle preservation.

## Task 3: Repair Stage2 arrival choreography

Ownership: arrival-only authoring/graph/render/verification scripts; native route code only if a proven lifetime defect needs it. Read Saved/PresentationFix20261119/arrival-diagnosis.md and the prior arrival specification.

Write a revised restrained 10–12 second shot plan from actual scene dimensions. Use a consistent camera side/direction, show cat contact and all three first-puzzle elements, move portal inside a physically valid visible aperture and close/remove it before the later reveal. Eliminate real-pawn/sequence-cat visibility flashes using balanced presentation ownership. Preserve original route admission, pause/abort/stop/end-play cleanup, gameplay camera and inputs. Root runs authoring, cold reload, sample renders, actual Stage1 portal→Stage2 runtime and restart/abort regressions. Compare camera trajectory and screenshots rather than relying on compile-only success.

## Integration and completion

Root assembles reviewed changes, performs a fresh Editor build, targeted actual input/visual/arrival checks and appropriate regression automation. Independent reviewer assesses both source and saved runtime evidence. Record exact passes and remaining limits in a review report and HANDOFF; restore original user save/settings and close owned Unreal processes. No publishing requested.

## User steering during implementation (2026-11-19)

The user expanded the scope after Task1 passed. The following replaces the previous same-side continuous Stage2 camera requirement; use intentional cuts for face/statue shots as requested. Task1 input fix remains accepted and Task2 continues unchanged. Additional independent read-only diagnosis precedes serial implementation.

- Task1b minimap presentation: display a wider cat-centered neighborhood with simpler readable paths/markers, preserving camera alignment, upper-right hold enlargement, translucent background and thin metallic frame. Confirm serialized BP defaults as well as C++ values; no Tab hint/toggle.
- Task3a Stage1 portal departure: CLEAR the candle detection state itself at accepted exit cinematic entry (user explicitly corrected visual suppression). Clear mark, timer, marker/light and mark-specific tracking ownership through the existing authoritative state API; do not hide-and-restore the old mark on abort. Preserve unrelated AI perception and future detection. Provide enough actual/cinematic corridor space for a deliberate walk instead of starting beside the portal. Hide the rear approach with a dark closure/closing door if appropriate. Sequence: distant frontal cautious cat walk (rear corridor visible, blue face lighting); stop near portal, ears/head reaction; pull back to a low-angle grand cat-and-portal two-shot; side view and preparation, dynamic slow-motion jump into portal. Preserve route admission, save/fade/travel and basket rules; don't change animation identity/rig. Show plan before authoring and verify genuine rendered composition, complete mesh occlusion after entry, bounds/collision/walk/contact and abort.
- Task3b Stage2 arrival: show portal before the cat emerges; cat jumps out, walks a little while camera sees its back; cut to face close-up; cut to statue focus; move camera to plate focus; cut back to cat face; smoothly move to the normal gameplay camera. Preserve first-puzzle states, original pawn/start/checkpoint, one-time qualification, cleanup and stage title. Correct arrival-only portal placement/closure and preserve asset source.

Task1b and Task3a/b get separate owned implementation/review packages. Root remains sole engine and binary asset operator; no concurrent implementers. Existing uncommitted work stays preserved. No push requested.
# Additional visual request (2026-11-19, while implementation is active)

User supplied four stock-image references and requested a very saturated, bright, mysterious portal with small sparkling particles orbiting around it. Continue the existing mark/cinematic fixes first. A separate agent plans the portal treatment; root integrates it after stable cinematic timing to prevent overlapping asset migrations. Use the images as visual references, not imported source textures.

Target: saturated cyan/blue rim and runes, ultramarine/violet flowing interior, compact bright highlights and small slow orbiting sparks outside the cat's primary silhouette. Share editable material parameters across Stage1/Stage2, preserve the existing depth-core occlusion, collision and travel logic. Stage2 sparkle fade must obey the portal close/despawn timing. No audio production or publishing added.
