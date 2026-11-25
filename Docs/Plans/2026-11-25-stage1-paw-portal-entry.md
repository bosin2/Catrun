# Stage1 portal investigation and committed jump

User request, 2026-11-25: replace the standing and old jump-preparation interval after the existing four-second blue-lit front walk. The cat tests the floor light once, turns an ear and tilts its head, waits visibly, then lowers its shoulders, performs two small pelvic wiggles with planted forepaws, compresses its hind legs and jumps upward into the portal. Keep the whole departure between 9 and 12 seconds.

Animation production is explicitly delegated to the existing **고양이 모델 구성 확인** chat (`01a2107b-42cf-7283-91ba-0c114fc29bba`, host `local`). That chat owns the two new rigged animation clips and Blender/FBX evidence. This worktree owns Unreal import into new assets, sequence/camera/light integration and actual exit-trigger playback. Do not replace shared skeletons, meshes, existing animations, maps or another task's work.

Implemented 30 fps timing (339 frames / 11.3 seconds):

| Interval | Beat |
|---|---|
| 0–57 | Existing door/face opening |
| 57–177 | Existing four-second front walk and blue-light progression |
| 177–189 | Existing stop/settle |
| 189–211 | Single cautious forepaw tap (contact at 201), small local light response, paw returns |
| 212–237 | Ear first, head tilt, final 0.53-second stillness |
| 237–273 | Shoulders down, two small pelvic wiggles, hind-leg compression |
| 273–282 | Delivered 0.3-second takeoff bridge; last hind-foot support at 279 |
| 282–321 | Existing PortalJumpIn source frames 18–36; high upward portal trajectory |
| 321–339 | Portal occlusion and existing fade/travel |

The probe uses a low front-side three-quarter view showing the paw and both ears. The camera holds during the watchful pause. At the end of the tilt, cut to a low rear-side three-quarter view with the entire cat and portal opening visible. Keep this same shot through the last wiggle, compression, extension and final hind-paw liftoff. No butt-only crop, repeated crouch or instant straightening at the animation seam.

Required animation receipt: `.blend`, two distinct animation-only FBXs, 30 fps ranges and skeleton/axis/scale contract, contact frame and position, matching PortalJumpIn source time, last hind-paw liftoff, natural-speed full-body preview and grounding/joint-deformation QA. Preserve the approved BlackCat appearance. The previously rejected unnatural RigV2 animation is not an approved substitute.

Received and integrated: two requested clips (1.6 s probe/ear/pause and 1.2 s crouch/wiggle/compression), plus a 0.3 s pose-matching takeoff bridge from the same production chat. The bridge avoids replaying the original crouch and meets the original PortalJumpIn at source frame 18. The original 78-bone rig, skin weights and existing animation assets remain unchanged. Source receipt and hashes are in `SourceArt/BlackCat/PortalEntry20261125/contract.json`.

The rear camera holds through frame 279; upward/forward root travel and camera follow begin after that support frame. The new clips use a dedicated least-destructive compression asset because the default compressor removed small planted-foot keys and reduced the second wiggle. Runtime forepaw displacement is below 0.001 cm after this correction.

Final validation uses the actual Stage1 exit overlap in an isolated PIE process. Only the initial approach is a fixture; cinematic completion is not called directly. Record continuous normal-speed motion from first paw contact to portal entry, inspect all beats and pose seams, and verify normal travel and control restoration. The preceding Stage2 readability fix is a separate already-authorized change; this additional production scope is Stage1 departure only.
