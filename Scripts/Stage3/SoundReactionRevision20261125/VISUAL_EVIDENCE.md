# Native device wave evidence

`visual_native_test.py` wraps the unchanged physical interaction and AI response
test with observations only. Root launches it using the normal isolated PIE
launcher with a real renderer (`d3d12`, no NullRHI).

For the finalized saved map/settings:

```powershell
$env:CATRUN_SOUND_TEST_MODE='saved'
$env:CATRUN_SOUND_TEST_PASS='saved_visual01'
$env:CATRUN_SOUND_OBSTACLE_FIX='none'
$env:CATRUN_SOUND_VISUAL_CAPTURE='1'
```

Artifacts are under
`Saved/Stage3SoundReactionRevision20261125/saved_visual01/Visual/`:

- `blueprint_graphs_readonly.json`: actual source pin links in controller,
  burst and ripple graphs, including event Budget to MaxRadiusCm and duration.
- `report.json`: live spawned ripple identity, source location, maximum radius,
  duration, per-frame MID `Radius`, captured propagation texture and world rect,
  plane visibility/scale, unchanged camera pose and shared package SHA.
- `Radius20.png`, `Radius55.png`, `Radius90.png`: actual player/reveal-camera
  GPU frames triggered from measured MID radius, not assumed elapsed time.

The native source sends the same LastBudget to sound and `OnSoundEmitted`.
Its picture distances use LastBudget + two grid cells to avoid edge clipping.
At a 25cm cell size, an 1800cm event therefore has 1850cm of picture interpolation
data, while its actual maximum should remain 1800cm. The snapshot helper rejects
a mismatched event budget. It copies distances into a transient linear-data
texture; it does not change sound propagation.

Expected BP parameters at SoundSpeed=600cm/s:

| Device budget | MaxRadiusCm | Budget / speed |
|---|---:|---:|
| Previous | 500 | 0.8333s |
| Revised | 1800 | 3s |

For direct A/B GPU evidence, run a separate **candidate** pass with budget500
on the same final geometry and camera, then the saved1800 pass. Candidate mode
changes only isolated process settings and preserves the player bell override.
The 500 native AI test can correctly fail the original reach/approach checks;
do not report that comparison pass as gameplay success or weaken its criteria.
Each pass requires a new evidence name. The observer itself never changes the
budget, emits a stimulus, or creates/repositions a camera.

Root must view the PNGs before accepting visual readability. A material radius
and nonempty PNG prove parameters/rendered output exist, not that every wave
pixel is readable. A 3.6x weighted-range increase does not imply 3.6x on-screen
diameter: walls, propagation costs, field-of-view and clipping affect shape.
This helper creates no audible content and uses no paid provider.
