# Stage3 D1/D2 gate completion impact

Root-only authoring and test launch. This package does not run Unreal, save a map,
or change source gameplay code by itself. It references Stage2's in-progress
`GateFX/author_gate_fx.py` style, but does not load, duplicate or edit that isolated
Stage2 work's packages.

## Prepare

In the root-owned editor with `/Game/Maps/Stage3` loaded and PIE stopped:

```python
import importlib.util
p = 'C:/Users/whghk/Catrun/Scripts/Stage3/GateFXRevision20261125/author.py'
s = importlib.util.spec_from_file_location('stage3_gate_impact_author', p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
report = m.prepare()
```

The default fresh destination is
`/Game/Environment/Stage3/GateFX_20261125/Run01`. On a failed unpublished build,
use a new generation (`CATRUN_GATE_FX_GENERATION=Run02`) in a clean editor rather
than deleting or reusing a loaded Blueprint class. Existing presenter actors
cause a fail-closed assertion; do not create overlapping presenter sets.

Root must check Blueprint/material compilation and review `prepared.json`, then
explicitly save only its `root_save_list_after_review`. The helper has no save
calls. It compares all pre-existing actor transforms/collision flags and native
reveal tuning, and hashes Stage1/2/3 plus shared presentation packages.

## Runtime contract

- Two cosmetic actors, eight preallocated NoCollision dust cards per gate.
- `OnPhaseChanged(ToGate)` records the native session. `GateOpening` arms an
  effect but does not show dust. `Completed` requires that session, revision and
  actual recessed gate Z, then starts exactly one impact and disarms.
- Dust rises/fades once over at most **0.78 s**. No fractional-time looping.
- UV rumble peaks at **0.00055**, decays quadratically to zero by **0.26 s**.
  Its new unbound postprocess component samples scene color unchanged at zero.
  No camera transform, projection, width, blend weight or timing is written.
- Returning preserves the impact age. Reset, Inactive, EndPlay and lost session
  clear it. Stage3's shorter native camera return may end dust before 0.78 s;
  this deliberately preserves that existing camera timing.
- No sound/perception event, gate/cat collision or gameplay trigger changes.
- Scope: D1/D2 vertical recessed gates only. The final horizontal sliding gate
  has a separate native objective implementation and is excluded in this pass.

## Root-run validation

After saving and cold loading, run the existing isolated PIE launcher with
`-Script GateFXRevision20261125/observe_regression.py` and a unique `-Name`.
Use `CATRUN_GATE_FX_TEST_PASS=Regression01` (new name for each run). This wrapper
retains the native layout/orientation suite (previously 188 checks), adds
per-frame FX observations, and writes:

`Saved/Stage3GateFXRevision20261125/Regression01/{report.json,fx_observation.json}`.

It verifies no BeginPlay effect, native Completed at actual floor clearance,
one impact per gate, visible card pool, decayed rumble, Inactive cleanup, stable
component counts, preserved reveal tuning and unchanged saved-map/package SHA.
Inherited deterministic puzzle fixtures and NPC disabling remain in use; this
does not claim an unassisted campaign or enemy-difficulty playthrough.

The observer now reads the approved B1 six saved wall actors, measures its
125/125/230cm openings, and adds six physical cat traversal legs (three round
trips) to the unchanged baseline routes. E3 interaction uses the linked
Housing's current position/axes. Terminal approach and exit movement derive
from the current linked gate leaves and FinalExit trigger, including the hall's
600cm extension; no old terminal goal is used as a movement destination.

Additional root inspection before declaring full FX approval:

1. At actual D1/D2 completion, inspect a frame within 0.1–0.2 s from the existing
   player/reveal camera. Dust must stay near the floor and not hide the cat.
2. Run the separate `GateFXRevision20261125/reset_replay_entry.py` with fresh
   `CATRUN_GATE_FX_RESET_PASS=ResetReplay01`. Its inert implementation module is
   `reset_replay.py`. Each gate is solved twice through continuous cat input and
   native statue Tick. During the first visible completion burst it calls native
   ResetStatue, checks immediate dust/rumble zero, revision change, statue/plate
   restoration and native closing; the next native opening must fire once.
   D2's three prerequisites use actual TryRelease/physical clips/CommitRelease.
   No effect function, counter write, fake delegate, TryPushStatue call, statue
   teleport or camera edit is used. Seven clearance-checked cat relocations
   establish independent cases; NPC tick/collision is disabled as disclosed.
   Four GPU frames maximum show each gate before Reset and during replay.
   `CATRUN_GATE_FX_RESET_CAPTURE=0` disables those four captures if needed.
   **Neither this prepared harness nor the main observer is a runtime pass
   until root executes it and reviews its report.**
3. Interrupt the reveal / stop PIE and confirm no effect remains. EndPlay's
   cleanup graph is authored; runtime interruption evidence remains required.

Local syntax/AST checks only are not Unreal compilation or visual acceptance.
