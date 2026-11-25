"""Read-only implementation probe for coordinated headless execution."""
import json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3GothicRevision20261125'
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
result={'actors':{},'api':{}}
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    label=a.get_actor_label()
    if any(k in label for k in ['Display','Plate','Statue','Release','Lock','FollowCamera','GrandPillar','Lantern']):
        p=a.get_actor_location();r=a.get_actor_rotation();b,e=a.get_actor_bounds(False)
        row={'location':[p.x,p.y,p.z],'rotation':[r.pitch,r.yaw,r.roll],
             'bounds':[[b.x-e.x,b.y-e.y,b.z-e.z],[b.x+e.x,b.y+e.y,b.z+e.z]],'components':[]}
        for c in a.get_components_by_class(u.SceneComponent):
            q={'name':c.get_name(),'class':c.get_class().get_name()}
            if isinstance(c,u.StaticMeshComponent):
                q.update(mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
                    materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())])
            row['components'].append(q)
        result['actors'][label]=row
for cls in ['GeometryScript_Primitives','GeometryScript_MeshBasicEditFunctions','GeometryScript_MeshBasicEdit','GeometryScript_MeshTransforms','GeometryScript_MeshNormals','GeometryScript_MeshUVFunctions','GeometryScript_MeshUVs']:
    obj=getattr(u,cls,None)
    if obj:
        result['api'][cls]={x:str(getattr(obj,x).__doc__) for x in dir(obj) if any(k in x for k in ['append_box','vertex_position','auto_generate','recompute_normals','set_mesh_uvs','transform_mesh'])}
(OUT/'probe.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_PROBE_OK')
