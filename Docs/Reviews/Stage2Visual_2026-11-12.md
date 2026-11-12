# Stage2 visual verification — 2026-11-12

User stopped further verification and requested main publication at the current saved state. Audio production remains paused. This report distinguishes saved implementation from remaining acceptance.

## Saved changes
- Minimap map texture and all marker positions share a camera yaw/pitch affine projection; icons keep upright dimensions. The existing Tab expansion input remains; its hint label was removed from WBP_Minimap_Floorplan. Native math regression and panel authoring passed.
- Stage2 Gate frame and Room1 bookshelf material coverage: 13 actors use four new masked temporal-dither variants under Environment/Shared/Castle/Architecture/OcclusionRepairs. Original masters, bars, placement, collision and perception are unchanged. Live bookshelf occluded/clear/restored views and Gate04 view passed. The rejected translucent trial was fully restored and its four generated assets deleted.
- Shared statue socket-axis tolerance is24cm instead of12cm. Actual normal B push reached83.345% overlap with19.711cm lateral drift, but the old axis condition rejected seating. The new tolerance accommodates maximum inertial coast20.833cm plus margin;80% overlap, height, rotation, swept collision and floor support remain. Settings DA was explicitly saved24, C++ default and author/verify scripts match.

## Verification
- Stage2VisualBuild/Build02.log: CatrunEditor build succeeded. Initial C4458 local-name shadow was fixed by a local rename and rebuilt.
- Stage2VisualTests/AutomationReport/index.json:117 successful tests (113 ordinary,4 warning-success),0failed/0not-run. Includes camera projection/Slate registration and measured B seating regression.
- MinimapAuthor.log: UMG authoring commandlet exited0 and saved updated panel with UMGToolSet enabled.
- Independent spec/quality reviews and final Astra source review found no remaining blocking source defect.
- Before the final build, normal Enhanced Input movement/pushes with AI enabled solved C and A. Bell lure reached B; its83.345% rejected seating led to the common tuning fix. The old exit route acquired Candle02/Candle01 marks and Armor01 captured the cat. This was not a completed Stage2 run. All capture restarts observed restored the C checkpoint and reset A/B.
- Visibility fixtures repositioned the player only for matched render checks; those are separate from normal progression evidence.

## Rendering-warning cause
The exact108.0092MiB always-resident warning was reproduced after warming different maps in the editor; it is the20% diagnostic of a400MiB pool, not total-pool exhaustion.90unused Stage2 geometries account for46.252MiB. The engine reference chain identifies the Stage2 bookshelf as unreachable but retained by editor GARBAGE_COLLECTION_KEEPFLAGS. Ordinary obj gc leaves the same allocation. Fresh Stage2-only PIE was51.9944MiB and stayed identical after two normal capture restarts. No warning suppression, pool inflation or gameplay graphics downgrade was made. A separate -game process was launched and its first CSV captured, but the user stopped further verification before comparison/travel completion.

## Remaining work
1. New-build normal Stage2 C/A/B solve through final exit, including B gate05 east detour and normal sneak near Armor03/04. Route notes remain in local .superpowers/sdd/2026-11-12-stage2-visual-verification/play-strategy.md.
2. Live compact/expanded minimap visual acceptance and cold panel/settings reads.
3. Stage1 spawn visibility:4/6 body rays hit opaque S1_Door_LowerHall_East_Open;2hit the existing ArrivalStair occlusion material. The authoring script supports the confirmed structural door material, but Stage1 door repair was NOT applied/saved. Inspect stair visibility after the door trial rather than changing its math speculatively.
4. SoundTest_Stage2 still needs the same new frame/bookshelf variants; Stage1/SoundTest_Stage1 coverage is also pending. Shared puzzle DA24 affects both Stage2 maps.
5. Separate-game ray allocation comparison. Editor-only unused asset retention should not be addressed with game runtime GC hacks or warning suppression.

## Session cleanup and interruption
At22:57 a root verification helper saved Stage2 then called LoadLevel while retaining its old editor World in a Python local. EditorServer deliberately terminated for World Memory Leaks; the preceding Stage2/variant saves completed. Future map loads must be separate remote calls after save references have gone out of scope. This was an inspection harness failure, not evidence of a gameplay travel defect.

A later physical Escape stopped Computer Use. No further UI control is performed. A subsequent read-only process check confirmed all UnrealEditor/UnrealEditor-Cmd processes had exited. The original user save and two settings files were then restored, and all SHA256 hashes matched their Before copies (restored-hashes.json). All local evidence is under Saved/GameplayRepair20261112/Stage2Visual01; Saved evidence and paused audio tooling are excluded from publication.
