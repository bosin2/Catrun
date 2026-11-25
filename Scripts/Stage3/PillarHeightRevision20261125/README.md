# Original decorated pillar height restoration

Latest user request replaces the previous requirement to hide every pillar top.
Selected A: original shaft0..840cm plus60cm capital = **900cm complete height**.
Alternative600cm would compress the upper shaft's540cm into240cm and its UV
appearance, so it was not selected. No mesh/material source changes are needed.

`prepare.py` imports inertly. Root loads the latest saved Stage3 in its isolated
editor, then explicitly calls `apply(expected_map_sha=<latest SHA>)`. The helper
does not load or save packages. Root owns backup, disk-drift guard, save and QA.
It moves10 capitals to840..900, retires50 continuation actors reversibly, and
updates only40 active components' CPD16..23 to the visible stack0..900 bounds.
Retirement uses a non-GrandPillar label prefix so a later cutaway refresh cannot
accidentally union hidden upper parts into the live stack. Object paths remain.
Base/lower/upper transforms, all collision/shadows/materials, actor count, sound
grid, near-4000/far10000 and width900 are checked unchanged. Current capital
NoCollision/noShadow settings are retained; this patch does not add new shadows.

Root source-contract updates outside this folder:

- `Scripts/Stage3/layout.py`: `GATE_PILLAR_TOP_CM = 900`, explain original complete height.
- `Scripts/Stage3/IntegrationRevision20261125/apply_core.py`: future initial-core
  application should pass900 rather than3450. This script must never be rerun
  on the already-integrated map; its existing ownership/plan guards stay intact.
- Keep `build_map.py` existing-map regeneration prohibition intact.
- Previous GateHall projection/runtime/GPU artifacts describe the historical
  3450cm requirement. Do not overwrite their evidence or claim they validate
  this900cm saved map. This folder supplies the current contract instead.

Root QA after saving:

1. Fresh `prepare.readback()` validates10 active four-part stacks plus50 hidden
   NoCollision/noShadow retired components, CPD, and unchanged camera values.
2. Optional minimal actual GPU: `gpu_occlusion.main()` with fresh
   `CATRUN_PILLAR_HEIGHT_GPU_PASS`. Two controlled BaseColor cases (one pillar,
   foreground cut/background opaque), all10 CPU/CPD checks, static interactive
   opaque-material checks, no assets/maps saved. Controlled transient capture
   is not a final Lit play view. GPU success is not claimed until root runs it.
3. Root captures actual possessed cat GateMiddle and GateExtreme Lit only,
   same fixed camera: inspect decorated capitals, absence of clipped shaft
   sections, and foreground visibility. Existing capture helper may temporarily
   place the cat/freeze enemies; disclose fixture use, not manual playthrough.

Offline `projection.compare()` calculates top AABB projection (not GPU): at
900cm a complete top fits the frame at both specified views; at600cm more fit
at GateExtreme. World occlusion may still hide projected geometry. These
counts are not substitutes for the two actual Lit images.
