"""Read-only Blender inspection of the existing approved cat rig."""
import bpy,json
from pathlib import Path
OUT=Path('C:/Users/whghk/Catrun/Saved/Stage3Integration20261125/Animation');OUT.mkdir(parents=True,exist_ok=True)
r={'version':bpy.app.version_string,'file':bpy.data.filepath,'units':bpy.context.scene.unit_settings.scale_length,'fps':bpy.context.scene.render.fps,'objects':[],'actions':[]}
for o in bpy.data.objects:
    row={'name':o.name,'type':o.type,'scale':list(o.scale),'rotation':list(o.rotation_euler),'location':list(o.location),'dimensions':list(o.dimensions)}
    if o.type=='ARMATURE':
        row['bones']=[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local),'matrix':[list(x) for x in b.matrix_local]} for b in o.data.bones]
    r['objects'].append(row)
for a in bpy.data.actions:r['actions'].append({'name':a.name,'range':list(a.frame_range),'slots':[s.identifier for s in a.slots]})
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];bpy.context.scene.frame_set(1)
r['idle_pose']={b.name:{'location':list(b.location),'quaternion':list(b.rotation_quaternion),'scale':list(b.scale),'head':list(b.head),'tail':list(b.tail)} for b in arm.pose.bones}
ob=next(o for o in bpy.data.objects if o.type=='MESH');ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
r['material_bounds']={}
for i,slot in enumerate(ob.material_slots):
    ids={v for p in me.polygons if p.material_index==i for v in p.vertices};vs=[me.vertices[k].co for k in ids]
    if vs:r['material_bounds'][slot.name]=[[min(v[a] for v in vs) for a in range(3)],[max(v[a] for v in vs) for a in range(3)]]
ev.to_mesh_clear()
(OUT/'rig_inspection.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print('CAT_RIG_INSPECT_OK')
