# Stage3 color correction material pipeline

The source probe reads saved Unreal graphs, actual mesh slots, component overrides,
texture import filenames, sRGB flags and PBR connections. It does not save assets.
The calibrator uses the arithmetic mean of all mip-zero source PNG texels after
IEC 61966-2-1 sRGB decoding. Each color channel is measured independently.

The shader evaluates:

`original BaseColor / SourceMeanLinear * ColorTint * Brightness`

`ColorTint` is the desired representative **linear** RGB color (the requested
sRGB byte target decoded exactly), and `Brightness` defaults to 1. The source
normalization is constant in each dedicated parent. Original texture variation
is preserved as a per-channel positive scale, and the calibrator rejects any
clipping. This metric is a full-texture material reference, not a screen average,
not an area-weighted mesh UV average, and not a lighting/exposure measurement.
GPU compression and mip filtering may introduce small runtime differences.

Original parents are duplicated under the new folder, retaining Normal, ORM,
texture sampling/UV inputs, masked occlusion and device-readability graphs. Six
nodes wrap only the old BaseColor output. Each source/role pair gets a dedicated
Material Instance; existing source instances are duplicated to retain overrides.
Only the saved Stage3 actors' component material overrides change. No mesh,
original material/texture, actor transform, collision, or gameplay setting is edited.

Wall, pillar, floor, diamond and final-gate decorative stone are classified by
actual mesh and material slot, so shared source limestone is not globally tinted.
Both dark-stone and mid-stone floor insets use the diamond target. The whole pillar
(base, shaft, capital) uses the pillar target. Grout/mortar remains original to
retain seam contrast. Brass includes Stage3 armor brass; steel, armor joints,
charcoal cloth, leather, wax/flame, guardian statue and unrequested furnishing /
puzzle stone remain original and appear in the explicit preserved-slot ledger.

## Reproduce

1. Root reserves a read-only UE process slot and runs
   `Scripts/Stage3/ColorCorrection/Materials/probe.py` through the existing
   `Scripts/Stage3/run_editor.ps1` commandlet launcher, with a distinct log name.
2. Run `python Scripts/Stage3/ColorCorrection/Materials/calibrate.py` in the project
   root (Pillow and numpy required). Inspect `calibration.json` and independent QA.
3. Root obtains the writer slot and executes
   `Scripts/Stage3/ColorCorrection/Materials/apply_saved_stage3.py` in a coordinated
   commandlet. Alternatively, with Stage3 already loaded in the intended editor,
   import `materials` from `Scripts/Stage3/ColorCorrection` and call `main()`.
4. Root runs lighting, independent cold reload QA and actual-camera comparisons.

Run data is under `Saved/Stage3MaterialCorrection20261125/Materials`. Only new
packages under `/Game/Environment/Stage3/ColorCorrection_20261125` and Stage3 map
material overrides are saved. Existing unowned destination names are rejected.
Inputs must be regenerated when source graphs, PNGs or component slots change.
The writer rejects stale texture hashes and material/mesh bindings before applying.

UE 5.8's bundled `MaterialEditingLibrary.cpp` vector/scalar instance setters
return false even when the write succeeds (`bResult` is never set true). The
writer therefore verifies both parameters through actual getter readback.

Do not run legacy `Scripts/Stage3/finalize_map.py` on the corrected map: it
reassigns release-housing readability materials and resets Stage3 lighting, and
would overwrite these corrections. It is a historical initial integration step.
If rebuilding intentionally, rerun this correction pipeline and independent QA
after the legacy build/finalize sequence.

Before taking PIE comparisons, execute `Editor.AsyncAssetCompilationFinishAll`
after loading Stage3 and before starting PIE. This bundled engine console command
waits for registered asset managers including shaders. Without that barrier,
the first corrected-map captures showed temporary checkerboard fallback on
flagstone and pillar capitals despite no shader compile errors. The later
`ColorAfterReady` captures retain original stone texture correctly with no
material edits. `CatrunAuthoringLibrary.finish_asset_compilation()` is equivalent
for commandlets only; its implementation rejects normal editor/PIE calls.
