# Stage3 device sound investigation

The first two intended responders are `S3_Armor_LobbyPost` at (-180,-650) and
`S3_Armor_LobbyPatrol`, which patrols (340,-650)–(620,-650). Device 1's initial
ring is approximately (90,-327); the exact release-time sound origin moves with
the ring and is recorded by the native interaction test.

`ACatrunStage3Objectives::CommitRelease` emits Device/Device/Large to Minion.
`ASoundGridManager::EmitSound` uses Settings.LargeBudget for that event, computes
weighted traversable distance, then schedules hearing by distance/SoundSpeed.
The default LargeBudget in source is 500 cm; the probe reads the serialized value.
The left lobby armor requires a path around the lobby partition, so straight-line
distance is insufficient. Closed-door cells remain blocked at any budget. Cat
holes transmit sound by the authored design; armor width still forces a detour.

The proposed 1800 cm device budget is a candidate until native results are read.
`prepare_settings.prepare()` duplicates the current settings into the dedicated
Stage3 folder, increases only LargeBudget, and explicitly retains the existing
effective player bell range through PlayerBellBudgetOverride. Small/Medium,
sound speed, collision, door rules and other stages' shared settings are retained.
The preparation script does not save; root reviews and saves the new asset/map.

Validation is split deliberately:

1. `probe.py`: diagnostic direct native propagation from all three ring origins,
   original/1000/1400/1800/2200 budgets, D0 closed/open, door-cell and H1 controls.
2. `native_test.py`: the real TryRelease → alignment → pull animation →
   CommitRelease path. No direct EmitSound/OnSoundHeard. Records actual remaining
   budgets, weighted distance, expected arrival delay, native heard log lines,
   response states, concurrent investigation, running speed and physical approach.
3. Run `native_test.py` in `saved` mode after root saves the isolated asset/map.

`CATRUN_SOUND_TEST_MODE` selects baseline/candidate/saved; default candidate.
`CATRUN_DEVICE_SOUND_BUDGET` defaults to 1800.
`CATRUN_SOUND_TEST_PASS` selects a new evidence folder (default mode01).

Native private Destination is not Python-reflected in the current source, so the
test does not pretend to read it. It reports the single committed sound origin,
the native hearing log, state change and actual movement toward that origin.
Capture is disabled only in isolated tests; armor ticks and collisions remain on.
No C++ or other agent-owned files are modified by this work.
