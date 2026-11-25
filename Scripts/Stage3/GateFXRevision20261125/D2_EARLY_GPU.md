# Focused D2 native-camera capture

Root alone launches `d2_early_gpu_entry.py` through the existing isolated GPU PIE
launcher. Set `CATRUN_GATE_FX_D2_PASS=D2EarlyGPU03` or another fresh name. Importing
`d2_early_gpu.py` alone is inert. Output is
`Saved/Stage3GateFXRevision20261125/<pass>/` and cannot overwrite an earlier run.

This performs the three actual device releases and one actual native P2 push.
It does not repeat D1, resets, or replay. NPCs are disabled and the cat has four
independent collision-checked staging fixtures. Native camera, gate timing,
collision, FX counters and presenter functions remain untouched. Saved Stage1,
Stage2, Stage3 and presentation package hashes must remain identical.

Warmup: three PIE game seconds; FinishAll; ten wall seconds and sixty callbacks;
FinishAll again. During gate opening and impact all report writes are deferred.
The first native Completed/active dust event is recorded in memory only, without
a screenshot. Exactly one PNG is requested at the first observed dust age >= .045 s.
It must retain eight visible cards, nonzero rumble and age < .26 s, and its effect
origin must project inside the actual gameplay viewport. No fixed frame rate,
camera pause, altered time dilation or direct FX activation is used. A missed
early window fails; it is not replaced by a later or staged camera image.
The next frame's game/wall delta is recorded to quantify capture-induced hitch.
Natural native cleanup and saved-package SHA checks remain required.

`D2EarlyGPU01` remains a failed harness-initialization record (empty cycle list
before skipping D1). `D2EarlyGPU02` remains a failed two-shot experiment: its
age-zero screenshot caused a .4166667 s next-frame jump, and its second request
had zero rumble and an offscreen effect origin. Revision 03 removes that age-zero
screenshot, not the early-dust condition. Neither previous result is overwritten.

## ResetReplay01 diagnosis

The existing 54 passing checks prove native reset/replay behavior. They do not
establish that its D2 PNGs show the gate impact clearly.

Both D2 completions were first observed at age 0 and rumble .00055. The old
harness then called check twice and phase once; each synchronously serialized
and wrote the entire growing report, and screenshot logic ran next callback.
The subsequent game delta was .28308 s / .31565 s, already beyond rumble duration.
The completed report is 2,400,965 bytes with 2,886 samples. A local read-only
benchmark of three JSON serializations (excluding disk writes) at the relevant
sample counts took .1703 s / .2335 s. These are indicative current-machine
measurements, not an exact profiler trace of the original run.

Native `GateOpened` immediately transitions to Returning, whose original .6 s
SmoothStep interpolation continues. Therefore the old screenshot requests were
approximately 47% / 53% into camera return. This is consistent with the D2 gate
leaving frame. No camera or native timing change is justified by this harness
artifact.

## Reading evidence

`first_active`, `focused_samples`, and screenshot request metadata include
native phase, actual gate Z, effect age/rumble and gameplay camera position.
Screen projection errors are reported explicitly and fail the capture prerequisite.
Request-time metadata is not a GPU pixel measurement. Inspect the PNG before
claiming D2 dust is visible; retain any offscreen/occlusion limitation honestly.
