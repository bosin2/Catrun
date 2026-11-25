# Stage3 lighting correction candidate

Run `lighting.py` by itself only for a read-only probe. The director owns the
Unreal writer slot and applies lighting **after** material calibration. This
worker has not applied, rendered or visually approved these settings.

## Proposed first pass

| Exact actor label | Measured original | Proposed |
|---|---:|---:|
| S3_KeyLight | 1.4 | 0.45 |
| S3_FillLight | 1.7 | 0.14 |
| S3_AmbientSkyLight | 2.0, daylight cubemap | 0.35, T_GreyAmbient |
| S3_LocalLight0..4 | 220 cd | 18 cd |
| S3_LocalLight5..8 | 500 cd | 40 cd |
| S3_Exposure | Histogram; min/max 1/1; bias not overridden | Manual; physical exposure off; bias 0 overridden |

Key falls 68%, fill 92%, and sky intensity 83%. The old fill exceeded the key;
the new fill/key ratio is 0.31, restoring surface shape. Key 0.45 lies between
Stage1's 0.32 and Stage2's 0.8, while sky 0.35 is below Stage1's 0.6. These values
follow the requested darker, restrained appearance. Gray cubemap is the same
neutral engine asset used in Stage1; no cubemap asset is edited.

Stage3's local lights use **candelas**, whereas Stage2 uses **lumens**. Comparing
the raw numbers 220 and 180 is invalid. An ideal isotropic source emits total
flux `4*pi*intensity`: 220/500 cd corresponds to approximately 2765/6283 lm;
18/40 cd approximately 226/503 lm. This comparison is a diagnostic scale, not a
promise of identical rendered illuminance: attenuation, source shape, inverse
square settings, placement and occlusion also matter. Existing local positions,
warm colors, attenuation 550, source radius, shadow flags and units are retained.
The brighter hall fixtures still retain their approximately 2.2:1 hierarchy.

Manual exposure disables adaptation as a confounding variable. The min/max
brightness properties remain as found because manual exposure ignores them.
No exposure gain is added to compensate for incorrect Base Color. Material
targets must be verified independently in Base Color, then lit appearance
reviewed from actual gameplay. Proposed settings are not measured output colors.

## Director use

```python
import sys
sys.path.insert(0, 'C:/Users/whghk/Catrun/Scripts/Stage3/ColorCorrection')
import lighting
# Stage3 must already be loaded. No camera changes or level switching occur.
result = lighting.apply(allow_write=True, save=False)
# Inspect result, compare actual player camera, then explicitly save Stage3.
# Undo just the lighting values without reverting newer materials/geometry:
lighting.restore(result['snapshot'], allow_write=True, save=False)
```

`save=True` is available only when the director explicitly wants this script to
save the current level. `normalize_locals=False` allows the same global pass with
original locals for a controlled comparison. That comparison can expose local
overexposure; it is not the preferred candidate.

Each apply makes a timestamped directory under
`Saved/Stage3MaterialCorrection20261125/Lighting/`, containing the last saved
Stage3 map backup + SHA256, a pre-mutation property snapshot, and a before/after
report. Disk backup is **not** a copy of unsaved editor material assignments;
property restore preserves those assignments. Do not replace the map file while
the editor has it loaded. Prefer property restore. Only Stage3's exact named
light components and exposure fields are changed; no actors are added/deleted.
Any mutation/validation exception attempts to restore the original properties.

The script asserts actor counts/paths, all actor and component transforms, mesh
references, material-slot assignments, camera post-process/FOV/arm length and
local fixture radii/colors/units/shadows remain unchanged. Independent QA still
owns comprehensive gameplay-property validation and saved-map inspection.

## Validation required before declaring completion

1. Check `probe.json` or apply report identifies `/Game/Maps/Stage3` and current
   exposure overrides. Validate script execution in the director's writer slot;
   this worker performed syntax checks only.
2. Use identical actual player poses/camera, resolution and game settings for
   before/after. Include entry floor/wall junction, corridor pillar, warm fixture,
   gate hall iron/brass/banner and a dark side wall. Retain camera actor yaw 45,
   original transform, arm pitch -55 and zoom 900. Do not use legacy
   `capture_map.py` as player-camera proof: it uses separate scene captures and
   forces exposure bias +1, masking the gameplay post-process result.
3. Check wall texture remains visible, pillar/floor colors separate, fixtures
   have a bounded pool, and black iron retains shape without white stone faces.
   Judge darkness and navigation from the player camera, not overhead previews.
4. Record clipping/darkness per comparable material ROI, excluding UI, player,
   emissives and strong metallic highlights. Treat these as image diagnostics,
   never as proof of Base Color accuracy. Report any unavailable player view.
5. If too dark after correct materials, first inspect effective camera/volume
   exposure and fixture contribution. A measured small lighting adjustment is
   preferable to silently changing Base Color, adding exposure bias, or moving
   the approved camera. Save only after the director accepts the comparison.
