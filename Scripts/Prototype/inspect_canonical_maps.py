"""Read-only geometry, dependencies and installed editor API inspection."""
import unreal,json
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/CanonicalMaps'
out.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
def vec(v):return [round(v.x,3),round(v.y,3),round(v.z,3)]
result={'dirty':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()], 'maps':{}}
for stage in ['Tutorial','Stage1','Stage2']:
    assert levels.load_level('/Game/Maps/SoundTest_'+stage)
    rows=[]
    for a in unreal.GameplayStatics.get_all_actors_of_class(editor.get_editor_world(),unreal.Actor):
        row={'label':a.get_actor_label(),'name':a.get_name(),'class':a.get_class().get_name(),'location':vec(a.get_actor_location()),'rotation':str(a.get_actor_rotation()),'scale':vec(a.get_actor_scale3d())}
        origin,extent=a.get_actor_bounds(False)
        row.update(bounds_origin=vec(origin),bounds_extent=vec(extent))
        mesh=a.get_component_by_class(unreal.StaticMeshComponent)
        if mesh and mesh.static_mesh:row['mesh']=mesh.static_mesh.get_path_name()
        if row['class']=='BP_TutorialIntro_C':
            row['bindings']={k:str(a.get_editor_property(k)) for k in ['Cat','StartCamera','WakeCamera','GamePlayCamera']}
        if isinstance(a,unreal.CatrunNoBellZone):row['zone_extent']=vec(a.get_component_by_class(unreal.BoxComponent).get_unscaled_box_extent())
        rows.append(row)
    result['maps'][stage]=rows
result['apis']={'levels':dir(levels), 'utils':dir(unreal.EditorLoadingAndSavingUtils), 'asset_tools':dir(unreal.AssetToolsHelpers.get_asset_tools())}
result['settings']={c:str(unreal.get_default_object(unreal.load_class(None,'/Script/Catrun.'+c))) for c in ['CatrunLevelFlowSettings','CatrunSoundSettings']}
(out/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('PREFLIGHT',json.dumps({k:[r for r in v if any(s in r['label'].lower() for s in ['hole','armor','nobell','intro','exit'])] for k,v in result['maps'].items()},ensure_ascii=False))
print(result['apis'])



