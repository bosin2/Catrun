# Stage3 material correction — current user authority

The user's latest instruction supersedes the preceding layout-rebuild request:
**do not change map structure or game logic**. Do not rebuild Blender meshes.
Correct Stage3 materials in Unreal using dedicated Material Instances, preserve
source texture detail, Normal, ORM and UV. Never change Stage1/2 shared originals.
The earlier explicitly requested Stage3 camera reversal is already saved: actor
yaw -135 → 45 degrees, original location/scale/arm pitch/zoom retained.

Final Base Color targets, sRGB bytes (not Multiply input values):

| Role | R | G | B |
|---|---:|---:|---:|
| Wall | 101 | 97 | 95 |
| Pillar | 119 | 115 | 109 |
| Floor | 150 | 146 | 139 |
| Floor diamond | 112 | 108 | 102 |
| Gate hall decorative stone | 81 | 77 | 75 |
| Black iron | 52 | 50 | 54 |
| Brass | 150 | 134 | 107 |
| Banner | 101 | 49 | 62 |
| Wood | 89 | 72 | 61 |
| Carpet | 73 | 67 | 74 |

Expose adjustable ColorTint and brightness parameters. Compute the sRGB/linear
conversion and calibration against the actual source base-color signal; a raw
byte-normalized Multiply constant does not satisfy the request. Preserve texture
variation, and explicitly state the representative-color measurement used.
Normalize excessive lighting/exposure after material correction. Verify with the
actual player camera and report before/after.

## Parallel responsibilities and integration order

1. Material authoring worker: own `Scripts/Stage3/ColorCorrection/materials.py`
   and supporting files in `ColorCorrection/Materials/`; author the isolated
   Stage3 material/instance pipeline and quantitative calibration manifest.
2. Lighting worker: own `Scripts/Stage3/ColorCorrection/lighting.py` and
   `ColorCorrection/Lighting/`; inspect measured reference lighting, prepare
   restrained lighting/exposure correction preserving actor layout and camera.
3. Independent QA worker: own `Scripts/Stage3/ColorCorrection/verify.py` and
   `ColorCorrection/QA/`; verify color math, role coverage, unchanged geometry,
   source textures/materials, gameplay properties, and before/after evidence.
4. Root: preserve baseline, control all editor mutations, capture actual camera,
   integrate sequentially (materials → lighting → QA), review and publish scoped
   corrections under the user's existing main-push authorization.

No worker may mutate the running editor or save Unreal packages without root
coordination. Read-only independent inspection and owned script edits can run in
parallel. No agent commits, pushes, changes Source/, or edits other workers' files.
Run data goes under `Saved/Stage3MaterialCorrection20261125`; shared baseline
lighting is already at `Saved/Stage3Correction20261125/lighting_reference.json`.
The live editor currently has `/Game/Maps/Stage3` loaded and no PIE.

## Evidence and decisions

- Baseline main is bdcddbc. Existing camera-only edits and lighting probe belong
  to root; unrelated audio/local metadata stays untouched.
- Previous Stage3 key/fill/sky intensities were 1.4/1.7/2.0, sky used a daylight
  cubemap, and exposure was histogram with 1/1 limits. Stage1 key is .32 with gray
  sky .6 and manual exposure; Stage2 key/fill .8/.32 and manual exposure.
- Comparison captures must use identical player poses/camera/settings across
  before and after. Base Color verification must be separated from lit appearance.

## Completed evidence

- 18 dedicated parents, 24 MIs, 716 assigned slots; 379 unspecified slots preserved.
- Independent calibration 172/172, saved graph/slot checks 85/85, GPU target checks
  24/24 (worst 1.2134 sRGB bytes), and updated Stage3 DX12 PIE regression 53/53.
- 452 actor identities, transforms, meshes and collision preserved; full T3D
  gameplay-property diff empty outside exact material/light/exposure changes.
- Final six-view captures wait for shader compilation. Identical cat positions
  and camera angles; actual follow-camera positions differ by at most 4.57 cm.
  Three additional player views verify dark-carpet and unobstructed-lobby visibility.
- Original iron and corrected iron both have flat sampled GPU BaseColor at 256
  and 1024 px; this pre-existing characteristic is disclosed, not hidden.
- Seven concurrent basket-file hash deltas belong to another active chat and are
  retained in QA evidence, excluded from this correction's commit.
- Final report and untouched captures: `Docs/Reviews/Stage3ColorCorrection20261125/`.
