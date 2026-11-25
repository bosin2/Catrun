# Independent Stage3 correction verification

`../verify.py` separates source calibration, loaded shader graph, scene invariants,
and GPU evidence. A configuration report alone is not a rendered-color pass.

1. In the Stage3 editor, import `verify.py` and call `snapshot('before')` before
   applying changes. It exports the complete world T3D and hashes original files.
   No packages are saved and no editor selection or world changes occur.
2. In ordinary Python, run `verify.py self-test` and `verify.py calibration`.
   The latter independently computes 256-bin PNG channel histograms and the
   equal-texel arithmetic mean after IEC sRGB decoding. All ten user targets are
   final sRGB bytes. Texture variation is preserved, so individual pixels vary.
3. After applying and saving, use a fresh read-only Stage3 load and call
   `loaded_materials()` and `snapshot('after')`. The graph test follows the actual
   BaseColor chain, compares original texture/UV links and all non-BaseColor
   outputs, checks parameters, and checks all actual component slots.
4. In ordinary Python, run `verify.py compare`. Review both `world.diff` and
   `gameplay.diff`. Only material override lines, known Stage3 light intensity,
   the Stage3 sky cubemap, and six explicit exposure fields are excluded from
   the gameplay text comparison. All actor identities, geometry, collision,
   gameplay properties, camera transform and other fields remain checked.
5. The director may run `render_readback.py` in a disposable unattended rendering
   commandlet after application. It creates transient test geometry only in that
   disposable process, renders every applied MI through deferred `SCS_BASE_COLOR`
   into RGBA16F, and reads raw linear pixels. It never saves packages. It exports
   HDR swatches and a quantitative JSON report. This tests actual imported GPU
   textures and compiled materials, independently of tone mapping and lighting.
   The initial tolerance is 2.5 sRGB bytes per channel, with nonzero detail and
   no black background pixels. Any failures require investigation, not a wider
   tolerance chosen after observing the failure.

6. Run `analyze_gpu.py` in ordinary Python to summarize target accuracy separately
   from visible variance. In this run five iron instances had zero BaseColor
   variance. `iron_detail.py` was therefore run in the same disposable rendering
   setup: BOTH unchanged original iron and corrected iron had zero variance at
   BOTH 256 and 1024 pixels. This establishes a pre-existing rendered behavior.
   The analyzed report passes correction accuracy and preservation relative to
   baseline while retaining that limitation. `basecolor_gpu.json` is immutable
   raw evidence, including its original strict nonzero-variance failure flags;
   `gpu_analysis.json` is the reviewed result. No target tolerance was increased.

Evidence is written under `Saved/Stage3MaterialCorrection20261125/QA`.
Source proofs use the complete PNG mip0; GPU proof uses 256px UV0 sampling, so
compression, lower mip selection, and GBuffer quantization may produce a small
representative-color difference. The final source target is exact; a lit player
camera screenshot is appearance evidence and is not an RGB calibration sample.

Concurrent work must remain visible in the reports. In this run the director
reported another chat editing basket C++ and a shared basket cloth material.
Those exact hash changes must be listed separately and must never be restored,
attributed to this task, or silently treated as unchanged.
