"""Root final Stage3 pass: four patrol references, gate impact and minimap."""
import hashlib
import importlib.util
import json
import os
import shutil
import traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
PASS=os.environ.get('CATRUN_STAGE3_EFFECTS_PASS','Effects01')
assert PASS.replace('_','').isalnum()
OUT=ROOT/'Saved/Stage3IntegrationRevision20261125'/PASS
OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'result.json').exists()
MAP=ROOT/'Content/Maps/Stage3.umap'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
EA=u.EditorAssetLibrary
R={'success':False,'level_saved':False,'phase':'preflight'}
def sha():return hashlib.sha256(MAP.read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def persist():(OUT/'result.json').write_text(json.dumps(R,indent=2),encoding='utf8')
try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert not ED.get_game_world() and ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
    R['before_sha']=sha();shutil.copy2(MAP,OUT/'Stage3_before.umap')
    R['phase']='repair_gate_patrol_references';persist()
    R['gate_patrol_repair']=module('s3_gate_patrol_repair','Scripts/Stage3/GateHallRevision20261125/repair_gate_patrol.py').apply()
    R['phase']='prepare_gate_effect';persist()
    R['effects']=module('s3_gate_impact_author','Scripts/Stage3/GateFXRevision20261125/author.py').prepare()
    R['phase']='assign_updated_minimap';persist()
    R['minimap']=module('s3_gate_minimap','Scripts/Stage3/GateHallRevision20261125/minimap.py').assign()
    assert sha()==R['before_sha'],'Stage3 changed on disk during effects pass'
    for path in R['effects']['root_save_list_after_review']:
        if path!='/Game/Maps/Stage3':assert EA.save_loaded_asset(EA.load_asset(path))
    assert LE.save_current_level()
    R['level_saved']=True;R['after_sha']=sha();R['success']=True;R['phase']='saved_pending_effect_runtime_qa'
except Exception:R['error']=traceback.format_exc()
finally:
    persist();print('STAGE3_EFFECTS_RESULT',json.dumps({k:R.get(k) for k in ('success','phase','level_saved','error')}))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
