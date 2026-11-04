"""Repeatable Task4c package-only setup. Existing task manifest/backups are required
when rerunning on this dirty checkout; refuses collisions with unowned new paths.
Run via ue_remote.py --isolated with PIE stopped and exclusive writer ownership.
"""
import unreal,sys,importlib
from pathlib import Path
scripts=Path(unreal.Paths.project_dir())/'Scripts/Prototype';sys.path.insert(0,str(scripts))
import task4c_assets
importlib.reload(task4c_assets)
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
armor=unreal.load_asset(task4c_assets.ARM_BP)
connected='HandleCapturePhase' in [g.get_name() for g in task4c_assets.BP.list_graphs(armor)]
if connected:
 # Rebuilding an already-connected graph after package reload can crash UE5.8's
 # BlueprintEditorLibrary. Verify the saved task-owned connection instead.
 # A mismatch stops safely; this path never silently adopts edited graphs.
 import json,re
 from decimal import Decimal
 def normalized_pins(snapshot):
  # UE serializes numeric pin defaults (0 -> 0.000000, vectors likewise).
  # Normalize only numeric default text; node identities, types and links stay exact.
  for graph in snapshot['graphs']:
   for node in graph['nodes']:
    for pin in node['input']:
     value=pin['value']
     if re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:,[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)*',value):
      pin['value']=','.join(str(Decimal(x).normalize()) if Decimal(x) else '0' for x in value.split(','))
  return snapshot
 for asset,snapshot in [(task4c_assets.ARM_BP,'armor-after.json'),(task4c_assets.CTX,'context-after.json')]:
  expected=json.loads((task4c_assets.OUT/snapshot).read_text(encoding='utf8'))
  actual=task4c_assets.dump(unreal.load_asset(asset))
  assert normalized_pins(actual)==normalized_pins(expected),'Saved graph differs from task-owned snapshot: '+asset
 for asset in task4c_assets.manifest['new']:assert unreal.EditorAssetLibrary.does_asset_exist(asset),asset
 cdo=unreal.get_default_object(armor.generated_class());cap=cdo.get_editor_property('CapturePresentation')
 assert cdo.get_editor_property('bUseBlueprintAnimation') and cap.get_editor_property('bUseBlueprintPresentation')
 assert cdo.get_editor_property('Mesh').get_editor_property('anim_class')==unreal.load_asset(task4c_assets.ARM_ABP).generated_class()
 assert cap.get_editor_property('CatPickupAnimation')==unreal.load_asset(task4c_assets.CAT_CLIP)
 print('TASK4C_EXISTING_GRAPHS_VERIFIED')
 steps=['task4c_tune_hold_final.py','task4c_reload.py']
else:
 task4c_assets.foundation()
 steps=['task4c_context_scaffold.py','task4c_context.py','task4c_armor.py','task4c_tune_hold_final.py','task4c_reload.py']
for name in steps:
 exec(compile((scripts/name).read_text(encoding='utf-8-sig'),str(scripts/name),'exec'),{'__name__':'__catrun_remote_script__'})
print('TASK4C_COMPLETE_PACKAGE_SETUP')
