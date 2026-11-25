"""Single-writer visual revision; save only after every selected module succeeds."""
import importlib.util,json,os,sys,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3GothicRevision20261125'
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import dressing,visuals,characters,occlusion,camera
spec=importlib.util.spec_from_file_location('gothic_qa',str(ROOT/'Scripts/Stage3/GothicRevision/verify.py'))
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LE.load_level('/Game/Maps/Stage3')
result={'success':False,'mechanisms':os.environ.get('CATRUN_GOTHIC_MECHANISMS','0')=='1'}
try:
    if not (OUT/'QA/before/snapshot.json').exists():qa.snapshot('before')
    result['visuals']=visuals.apply(include_mechanisms=result['mechanisms'])
    result['dressing']=dressing.apply()
    result['characters']=characters.apply()
    result['occlusion']=occlusion.apply()
    result['camera']=camera.apply()
    if result['mechanisms']:
        import connections
        result['connections']=connections.apply()
        import presentation
        result['presentation']=presentation.apply()
        import interactive_visibility
        result['interactive_visibility']=interactive_visibility.apply()
        import floor_recess
        result['dock_recess']=floor_recess.apply()
    import reference_lighting
    result['reference_lighting']=reference_lighting.apply()
    u.CatrunAuthoringLibrary.finish_asset_compilation()
    assert LE.save_current_level()
    result['success']=True
    print('GOTHIC_APPLY_SAVED')
except Exception:
    result['error']=traceback.format_exc()
    raise
finally:
    (OUT/'application.json').write_text(json.dumps(result,indent=2),encoding='utf8')
