# Final integration evidence

- `AutomationSummary.json`: final native Catrun run, 159 passed including 10 with warnings. Entries retain warning context.
- `BlueprintCompile.json`: final project allowlist, 51 Blueprints, no compilation errors/warnings/failed loads.
- `SavedMapChecks.json`: final saved Stage3, 37 checks including all enemy spawn clearances.
- `Stage3PIE.json`: final DX12, normal multithreaded real PIE, 53 checks; checkpoint positions and enemy isolation are explicit in `scope`.
- `CampaignTransitions.json`: original tutorial presentation and real exit transitions through Stage1, Stage2, Stage3; NullRHI checkpoint-assisted test.
- `Stage2ExpansionPIE.json`: actual legacy-v4 continue/capture/restart/timeout regression and preserved slot bytes, isolated UserDir.
- `StageProgressProcess.json`: four independent save/load/reset/readreset processes.
- `animation_report.json`, `fbx_roundtrip.json`: original cat identity/rig hash, every-frame measurements and independent export roundtrip.
- `source_hash_validation.json`: 1192 final-delivery FBX/PNG hashes checked before import.
- `import_report.json`, `collision_repair.json`: engine import and aperture-aware collision correction.
- `Visual/`: native final engine overview/device/gate images, and final DX12 contact/pull/completion frames. These are engine renders, not generated concept art. Contact/pull show the dedicated housing fade; overview is an authoring camera, not the player camera.

The full scope, warning interpretation and unverified manual play/balance/package
limits are in `../Stage3Integration_2026-11-25.md`. Full transient execution logs
remain in `Saved/Stage3Integration20261125` and are not needed to play the committed map.
