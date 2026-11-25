"""Flatten the exhibition notch line to the reference's continuous lower edge."""
import json,sys,importlib
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
sys.path.insert(0,str(ROOT/'Scripts/Stage3'));import layout,build_map
importlib.reload(layout)
ACT=u.get_editor_subsystem(u.EditorActorSubsystem);EA=u.EditorAssetLibrary
lookup={a.get_actor_label():a for a in ACT.get_all_level_actors()}
target=lookup['S3_Wall_0014'];assert abs(target.get_actor_bounds(False)[0].y-1535)<.1
for label,a in lookup.items():
    if label=='S3_Wall_0014' or label.startswith('S3_Gothic_Wall14_'):
        a.set_actor_location(a.get_actor_location()+u.Vector(0,50,0),False,True)
        c=a.get_component_by_class(u.StaticMeshComponent)
        # The complete physical wall group translates rigidly with its CPD box.
        values=c.get_editor_property('custom_primitive_data').get_editor_property('data')
        if len(values)>=20:c.set_default_custom_primitive_data_vector4(16,u.Vector4(values[16],values[17]+50,values[18],values[19]))
assert ACT.destroy_actor(lookup['S3_Wall_0063'])
source=build_map.mesh('SM_S3_Floor_Octagon')
a=build_map.at_min('Floor_ReferenceBridge',build_map.cropped(source,150,50),(-550,1550,-5),folder='Floors',tags=('SoundFloor',))
reference=next(v.static_mesh_component for k,v in lookup.items() if k.startswith('S3_Floor_') and v.static_mesh_component.static_mesh==source)
for i in range(a.static_mesh_component.get_num_materials()):a.static_mesh_component.set_material(i,reference.get_material(i))
grid=lookup['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
data=json.loads((OUT/'applied.json').read_text(encoding='utf8'))
def vec(p):return[p.x,p.y,p.z]
data['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
data['connectors']=layout.CONNECTORS;data['bridge_edge_repair_cm']=50
data['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(OUT/'applied.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print('BRIDGE_REFERENCE_EDGE_SAVED')
