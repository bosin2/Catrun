"""Resume the recorded unsaved layout after separating wall/floor material lookup."""
import sys,json,importlib
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'));sys.path.insert(0,str(ROOT/'Scripts/Stage3'))
import layout,floor_recess,occlusion
for m in (layout,floor_recess,occlusion):importlib.reload(m)
EA=u.EditorAssetLibrary;ACT=u.get_editor_subsystem(u.EditorActorSubsystem);ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3' and not ED.get_game_world()
R=json.loads((OUT/'attempt_error.json').read_text(encoding='utf8'));R.pop('error',None)
baseline=json.loads((OUT/'QA/before/snapshot.json').read_text(encoding='utf8'))
bindings={}
for a in baseline['actors'].values():
    if not a['label'].startswith('S3_Floor_'):continue
    c=a['components']['StaticMeshComponent0'];mesh=EA.load_asset(c['mesh'])
    for i,slot in enumerate(mesh.get_editor_property('static_materials')):
        material=EA.load_asset(c['materials'][i]);src=EA.get_metadata_tag(material,'Stage3DockRecessSource')
        if src:material=EA.load_asset(src)
        assert material.get_base_material().get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE
        bindings[slot.get_editor_property('material_interface').get_path_name()]=material
lookup={a.get_actor_label():a for a in ACT.get_all_level_actors()}
assert lookup['S3_Plate1'].get_actor_location().x==-700
for label,a in lookup.items():
    if not label.startswith('S3_Floor_'):continue
    c=a.static_mesh_component
    for i,slot in enumerate(c.static_mesh.get_editor_property('static_materials')):
        c.set_material(i,bindings[slot.get_editor_property('material_interface').get_path_name()])
R['floor_recess']=floor_recess.apply();R['cutaway']=occlusion.apply()
lookup['S3_KeyLight'].get_component_by_class(u.DirectionalLightComponent).set_editor_property('forward_shading_priority',1)
lookup['S3_FillLight'].get_component_by_class(u.DirectionalLightComponent).set_editor_property('forward_shading_priority',0)
grid=lookup['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
R['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
def vec(p):return[p.x,p.y,p.z]
R['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
R['portals']={name:{'position':pos,'orientation':orient,'kind':kind} for orient,fixed,start,end,ops in layout.INTERNAL for center,kind,name in ops for pos in [[center,fixed,0] if orient=='h' else [fixed,center,0]]}
u.SystemLibrary.execute_console_command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
R['success']=True;R['map_saved']=True
(OUT/'applied.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf8')
print('LAYOUT_CORRECTION_SAVED',len(R['moved']))
