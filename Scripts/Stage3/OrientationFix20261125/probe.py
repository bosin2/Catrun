"""Read actual user editor before changing the plan/world handedness."""
import sys,json,shutil
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3OrientationFix20261125'
OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
assert not ED.get_game_world()
assert not (OUT/'probe.json').exists()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'));import verify
verify.OUT=OUT/'QA';verify.snapshot('before')
shutil.copy2(ROOT/'Content/Maps/Stage3.umap',OUT/'Stage3_before.umap')
extra={'dirty_maps':[p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'actors':{}}
for a in ACT.get_all_level_actors():
    label=a.get_actor_label()
    if not (label.startswith(('S3_Release','S3_GothicConnections','S3_GothicVisual','S3_Lock','S3_GothicPresentation')) or label in ('S3_D0','S3_FinalExit','S3_FollowCamera')):continue
    row={'class':a.get_class().get_path_name(),'transform':a.get_actor_transform().export_text(),'parent':a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None,'properties':{}}
    for key in ('InteriorDirectionLocal','ForkOpen','ForkClosed','PinOpen','PinLowered','PinClosed','ChainTerminalOpen','ChainTerminalClosed','PatrolRelativePoints'):
        try:row['properties'][key]=str(a.get_editor_property(key))
        except Exception:pass
    row['components']=[{'name':c.get_name(),'transform':c.get_world_transform().export_text()} for c in a.get_components_by_class(u.SceneComponent)]
    extra['actors'][label]=row
(OUT/'probe.json').write_text(json.dumps(extra,indent=2),encoding='utf8')
print('ORIENTATION_BASELINE',len(extra['actors']),extra['dirty_maps'])
