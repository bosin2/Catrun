import bpy,json,hashlib
from pathlib import Path
O=Path(__file__).parent
def digest(x):return hashlib.sha256(json.dumps(x,separators=(',',':')).encode()).hexdigest()
def snapshot():
 sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH')
 data={'vertices':digest([list(v.co) for v in m.data.vertices]),'faces':digest([[list(p.vertices),p.material_index,p.use_smooth] for p in m.data.polygons]),'weights':digest([[ (m.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in m.data.vertices]),'bind':digest([[b.name,b.parent.name if b.parent else None,[list(r) for r in b.matrix_local],b.use_connect] for b in a.data.bones]),'object_transforms':digest([[o.name,[list(r) for r in o.matrix_world]] for o in [a,m]]),'actions':{}}
 for act in bpy.data.actions:
  curves=[]
  for layer in act.layers:
   for strip in layer.strips:
    for bag in strip.channelbags:
     for fc in bag.fcurves:curves.append([fc.data_path,fc.array_index,[[list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation] for k in fc.keyframe_points]])
  data['actions'][act.name]=digest(curves)
 return data
new=snapshot();bpy.ops.wm.open_mainfile(filepath='C:/Users/whghk/Desktop/CastleKit/BlackCat/PortalCinematic/SK_BlackCat_PortalCinematic.blend');old=snapshot();out={'original_asset_unchanged':{k:new[k]==v for k,v in old.items() if k!='actions'},'original_actions_unchanged':{k:new['actions'].get(k)==v for k,v in old['actions'].items()},'source_hashes':old,'delivery_hashes':new};(O/'QA'/'preservation.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if not k.endswith('hashes')}),flush=True)
