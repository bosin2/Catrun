# Stage3 authoring and validation

The published level is `/Game/Maps/Stage3`; ordinary play does not require these
scripts or the external CastleKit delivery. Engine assets and the cat animation
are committed. `Docs/Design/Stage3/IntegrationDecisions.md` records authority and
deliberate provisional choices.

Use Unreal 5.8 with this project's current C++ editor build. These runners start
hidden, isolated processes. Run map writers sequentially, after every other
editor holding that map has exited. A runner returning a PID only proves launch;
inspect the named log and JSON result for completion.

To rebuild from the original delivery, set `CATRUN_STAGE3_SOURCE` to its
`Production02_20261125` directory. The frozen manifest is committed in
`Docs/Design/Stage3/DeliveryManifest_20261125.json`. Run these Python scripts with
`run_editor.ps1 -Script Scripts/Stage3/<script> -Name <unique-log-name>`, waiting
for each process to exit:

1. `import_assets.py` imports reviewed FBX/material/texture assets and the committed
   animation FBX. Existing assets outside the dedicated Stage3 destination are
   not reimported.
2. `repair_collision.py` restores the delivery's required aperture-aware collision.
3. `build_map.py` builds only its owned Stage3 map, using the animation's measured
   mouth samples. It refuses unrelated existing map content.
4. Run `python Scripts/Stage3/make_floorplan.py` in the repository to generate the
   floorplan image from the map report.
5. `finalize_collision.py` applies final lighting, readable device materials,
   spawn corrections and minimap, then checks the saved map. This finalization
   step is required, including on a fresh rebuild.
6. `capture_map.py` with `-Render` produces native engine overview/device/gate
   images; `import_thumbnail.py` imports the gate image for chapter selection.

`run_pie.ps1 -Name PIE_DX12 -Renderer d3d12` runs the actual Stage3 functional
regression in an isolated UserDir. `-SingleThread` is an optional diagnostic
override, not the normal performance configuration. The test explicitly uses
checkpoint placement and disables enemies after observing patrol movement;
it is not an uninterrupted manual difficulty assessment.

`run_pie.ps1 -Script verify_campaign.py -Name Campaign -NullRHI` exercises original
tutorial and campaign transitions. `run_automation.ps1` runs native Catrun tests;
`run_blueprint_compile.ps1` compiles the project Blueprint allowlist without saving
packages. The separate Stage2 legacy-save regression requires the documented
isolated v4 seed and is not interchangeable with an ordinary user save.

`collect_evidence.py` archives only completed successful reports and final images.
It fails if the latest required report is absent or unsuccessful. Full logs remain
under `Saved`; compact reviewed evidence is committed under `Docs/Reviews/Stage3Evidence`.
