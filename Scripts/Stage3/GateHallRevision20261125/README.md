# Root integration handoff

No script has been run in Unreal by this worker. These files prepare an in-place
Stage3 edit and offline evidence; they do not authorize a save or claim visual QA.

The gate hall proposal keeps canonical Y2900 fixed and extends its far end from
4000 to4600cm. Its resulting15x17m size interprets the request for five pillars
per side; it is not a user-specified exact dimension. Existing rows3150/3450/3725
remain; rows4025/4325 are added. World Y is negative canonical Y.

## Execution order for the single root editor writer

1. Back up the latest map including the approved altar B1 and preserve E23 work.
2. Load `corners.py` with a unique importlib module name. Call `apply_corners()`.
   It validates active original wall bounds, creates9 short30x30cm body returns
   and60 noncolliding molding pieces, and does not save. Two already bridged
   T-junctions, canonical(700,800) and(950,1950), are deliberately left alone.
3. Load `apply.py` with a unique importlib module name; do not reuse another
   Stage3 script's cached generic `apply` module. Call
   `apply(pillar_top_cm=3450, refresh_cutaway=True, rebuild_grid=True)`.
   This copies the existing material/mesh assignments, moves gate/goal/routes,
   extends the rug actor, and adds five upper continuation pieces per pillar.
   It updates all cutaway groups and the sound grid, but does not save the level.
4. Read the resulting `applied_unsaved.json`. Run `minimap.render()` offline,
   then call `minimap.assign()` in Unreal. The new texture is isolated under
   `/Game/Environment/Stage3/GateHallRevision_20261125/Minimap`.
5. Root verifies and saves Stage3; capture a fresh snapshot and actual player
   views. Update the canonical layout definition separately after acceptance;
   do not call whole-map `build_map.py`, `dressing.apply()` or old `finalize_map.py`.

Each mutating function is explicit, refuses duplicate application, and validates
the current affected originals. If it fails midway, the editor may hold partial
unsaved changes: reload the root backup instead of rerunning over them.

## Evidence and limits

- `plan_validation.json`:8 offline checks pass; floor extension exactly90m2,
  side walls continuous, gate/goal/landing translated together, altar/D2 excluded.
- `projection.json`:320 cap-corner/pose pairs. Minimum cap top3365.79cm;
  with50cm vertical reserve and rounding, use3450cm. Worst pose is cat
  (-970,-4570,26.2), first right pillar corner(295,-3075). Its screen X is within
  the viewport. Fixed camera width900, aspect16:9, pitch-55/yaw-135 are preserved.
- Original pillar geometry/shadows from Z0..840 remain. Above840, reuse four
  full540cm shaft modules plus390cm final module; move60cm capital to3390..3450.
  New high pieces and capital are NoCollision and do not cast shadows. Every
  pillar part has one final name suffix, keeping the existing cutaway grouping.
- New candle rectangle paths clear the ten pillar bases by at least28cm after
  subtracting the measured22cm blocking capsule radius. Full-scene native AI
  regression is still required. Armor patrols follow the final gate by600cm.
- The original900cm rug is stretched to1500cm with its source mesh, UVs and
  materials untouched. Ornament proportions stretch; root must inspect the
  actual camera result before calling art quality complete.
- D2 and its locks remain fixed. Native objective leaf starts initialize in
  BeginPlay; final gate leaves, trigger and landing move together. Altar B1/E3
  are outside this script's scope.
- The9 body corner patches repair point-only joins, not nine proven holes a
  character could walk through. A separate existing30cm edge join needs only
  molding returns. Retired walls0001/0002 and E23 actors are excluded.
- Pending runtime checks: foreground/behind-pillar occlusion, raised-cap pixels,
  gate objective/exit, route movement, corner clearances, basket access, rug and
  light consistency. Offline arithmetic is not proof of these outcomes.
