import sys,json,shutil
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
OUT.mkdir(parents=True,exist_ok=True)
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name()=='/Game/Maps/Stage3.Stage3'
assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
backup=OUT/'Stage3_before.umap'
assert not backup.exists()
shutil.copy2(ROOT/'Content/Maps/Stage3.umap',backup)
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import verify
verify.OUT=OUT/'QA'
verify.snapshot('before')
actors=u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
extra={}
for a in actors:
    if a.get_actor_label().startswith('S3_GothicPresentation'):
        vals={}
        for key in ('ForkOpen','ForkClosed','PinOpen','PinClosed','ChainTerminalOpen','ChainTerminalClosed'):
            try:vals[key]=a.get_editor_property(key).export_text()
            except:pass
        extra[a.get_actor_label()]=vals
extra['dirty_maps']=[x.get_path_name() for x in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
(OUT/'probe.json').write_text(json.dumps(extra,indent=2),encoding='utf8')
print('LAYOUT_LIVE_BASELINE',len(actors),extra)
