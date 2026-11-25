# Independent QA: Stage3 material correction, 2026-11-25

The correction passes the independently checked scope. Whole-workspace hash
equality does **not** pass because concurrent basket work changed seven protected
files; those exact exceptions remain in the original comparison report.

## Completed evidence

- Source calibration: **172 checks passed**. Independent PNG channel histograms
  recompute the equal-texel linear mean after IEC sRGB decoding. All ten exact
  requested sRGB targets and all 1,095 slot dispositions are covered. Texture
  hashes, nonzero source variation, and independently predicted zero clipping pass.
- Saved shader/slot inspection: **85 checks passed**. Actual shader BaseColor is
  `original texture * inverse source mean * ColorTint * Brightness`. Actual
  ColorTint values are the decoded target colors; Brightness is 1. All original
  texture references, UV inputs, links, and non-BaseColor outputs are preserved.
  All **716 changed + 379 preserved** slots match their expected materials.
- GPU BaseColor: **24/24 material instances** meet the fixed **2.5 sRGB-byte**
  tolerance; worst measured error is **1.2134 bytes**. Floor measures
  **150.591 / 145.534 / 138.720**, target **150 / 146 / 139**. Deferred GBuffer
  capture into RGBA16F separates this measurement from lighting and tone mapping.
  All stone materials retain visible variation in the rendered samples.
- Iron diagnosis: five iron MIs have zero sampled BaseColor variance. Direct
  unchanged-original vs corrected-iron GPU comparison measured zero variance for
  **both** at **256 and 1024** pixels. This is pre-existing imported/rendered
  behavior, not new detail loss. Exact compression/mip cause remains unclaimed.
  Source texture, Normal, ORM and UV remain unchanged. Raw failure flags are
  retained; the analyzed result passes preservation relative to original.
- Scene: **452 actor identities** and all checked actor/component transforms,
  static meshes, collision settings and component layout match the baseline.
  The full saved-world T3D comparison is identical after removing only exact
  manifest material slots and authorized light/exposure properties. The
  normalized `gameplay.diff` is **empty**; camera yaw 45 already existed in the
  baseline and remained unchanged.
- New parent and MI assets exist only under the isolated correction folder.
  Original FinalGuard materials, textures and meshes are hash-identical.

## Concurrent protected-file exceptions

The director identified these as another chat's basket work. QA observed and
retained the hash changes; this task did not edit or restore them:

1. `Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Shared/Materials/M_Cloth_Stage1.uasset`
2. `Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage1/Meshes/SK_HideBasket_Stage1_Cloth.uasset`
3. `Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage2/Meshes/SK_HideBasket_Stage2_Cloth.uasset`
4. `Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage3/Meshes/SK_HideBasket_Stage3_Cloth.uasset`
5. `Source/Catrun/Interaction/BasketExitMath.h`
6. `Source/Catrun/Interaction/CatrunBasketInteractionComponent.cpp`
7. `Source/Catrun/Interaction/Tests/BasketExitTests.cpp`

## Evidence files

All under `Saved/Stage3MaterialCorrection20261125/QA/`:

- `calibration_independent.json`: source math, hashes, coverage.
- `loaded_materials.json`: actual saved graph/parameter/slot reads.
- `before/snapshot.json`, `after/snapshot.json`, corresponding `world.t3d` files.
- `comparison.json`, `world.diff`, `gameplay.diff`: exact changes and exceptions.
- `basecolor_gpu.json`: original raw 24-MI measurements, including variance flags.
- `iron_detail_gpu.json`: four original/corrected GPU diagnostic captures.
- `gpu_analysis.json`: reviewed GPU result (`success: true`) with limitations.
- `BaseColor/*.hdr`: native shader BaseColor swatches.

Actual player-camera appearance and campaign/runtime regression remain separate
director evidence. These GPU probes ran in disposable D3D11/SM5 commandlets;
they do not by themselves establish D3D12/SM6 warmup or final player appearance.
