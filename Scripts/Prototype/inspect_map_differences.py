"""Read-only original/test map transform and actor membership comparison."""
import unreal,json
from pathlib import Path
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world()
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
result={}
for stage in ['Tutorial','Stage1','Stage2']:
    snapshots=[]
    for name in [stage,'SoundTest_'+stage]:
        assert levels.load_level('/Game/Maps/'+name)
        actors=unreal.GameplayStatics.get_all_actors_of_class(editor.get_editor_world(),unreal.Actor)
        rows={}
        for a in actors:
            v=a.get_actor_location();r=a.get_actor_rotation();s=a.get_actor_scale3d()
            rows[a.get_actor_label()]={'class':a.get_class().get_name(),'transform':[round(x,3) for x in [v.x,v.y,v.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z]]}
        snapshots.append(rows)
    before,after=snapshots
    result[stage]={'original_count':len(before),'test_count':len(after),'added':{k:v for k,v in after.items() if k not in before},'removed':{k:v for k,v in before.items() if k not in after},'changed':{k:{'before':v,'after':after[k]} for k,v in before.items() if k in after and v!=after[k]}}
(out/'map-differences.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:{'original_count':v['original_count'],'test_count':v['test_count'],'added':list(v['added']),'removed':list(v['removed']),'changed':list(v['changed'])} for k,v in result.items()},ensure_ascii=False))
