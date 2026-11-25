"""Native constraint-based surface-ring bones. No handlers, add-ons, or runtime Python."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
O=Path(__file__).resolve().parents[1]/'JointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
uniform=m.data.attributes.get('uniform_ring_id') is not None
if uniform:O=Path(__file__).resolve().parents[1]/'UniformJointRepair'
a.animation_data.action=None;a['controls_enabled']=0.
for p in a.pose.bones:p.matrix_basis.identity()
for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
a.update_tag();bpy.context.view_layer.update()
col=bpy.data.collections.new('Mechanism - Surface Guides');sc.collection.children.link(col);col.hide_render=True
def empty(name,co=(0,0,0)):
 o=bpy.data.objects.new(name,None);col.objects.link(o);o.location=co;o.empty_display_size=.003;o.hide_render=True;o.hide_set(True);return o
def blend_point(name,targets):
 o=empty(name);acc=0.
 for target,w in targets:
  if w<1e-8:continue
  acc+=w;c=o.constraints.new('COPY_LOCATION');c.target=target;c.target_space='WORLD';c.owner_space='WORLD';c.influence=w/acc
 return o
regions=m.data.attributes['V3_leg_region'];records={};allrings=[]
for reg,key in enumerate(['F_L','F_R','H_L','H_R'],1):
 ids={v for p in m.data.polygons if regions.data[p.index].value==reg for v in p.vertices}
 byz={}
 for i in ids:
  z=round(m.data.vertices[i].co.z,6)
  if z>=.0309:continue
  byz.setdefault(z,[]).append(i)
 rows=[];original=[]
 cx=.026*(1 if key.endswith('L') else -1);cy=-.036 if key.startswith('F') else .038;upper=('upperarm_' if key.startswith('F') else 'thigh_')+key[-1]
 if uniform:
  codes=m.data.attributes['uniform_ring_id'];groups={}
  for i in ids:
   code=codes.data[i].value
   if code:groups.setdefault(code,[]).append(i)
  entries=[(.075,[])]+[(sum(m.data.vertices[i].co.z for i in vs)/len(vs),vs) for code,vs in sorted(groups.items())]
 else:entries=[(z,[]) for z in [.065,.055,.045,.035]]+sorted(byz.items(),reverse=True)
 for k,(z,vs) in enumerate(entries):
  # Exclude the cap center from the average so every cross-section keeps its center.
  cx=.026*(1 if key.endswith('L') else -1);rim=[i for i in vs if abs(m.data.vertices[i].co.x-cx)>.001 or len(vs)==12]
  if uniform:rim=[i for i in vs if len(vs)!=9 or (m.data.vertices[i].co-Vector((cx,cy-.002,z))).length>.002]
  center=sum((m.data.vertices[i].co for i in rim),Vector())/len(rim) if rim else Vector((cx,cy,z))
  w={m.vertex_groups[g.group].name:g.weight for g in m.data.vertices[vs[0]].groups if g.weight>1e-6 and m.vertex_groups[g.group].name in a.data.bones} if vs else {('chest' if key.startswith('F') else 'pelvis') if uniform else upper:1.}
  targets=[]
  for n,weight in w.items():
   obj=empty(f'LAND_{key}_{k:02d}_{n}',center);c=obj.constraints.new('CHILD_OF');c.target=a;c.subtarget=n;c.inverse_matrix=(a.matrix_world@a.pose.bones[n].matrix).inverted();targets.append((obj,weight))
  original.append(blend_point(f'BASE_{key}_{k:02d}',targets));rows.append({'indices':vs,'center':center,'name':f'skin_{key}_{k:02d}','z':z,'fixed':uniform and k<=1})
 current=original
 # Broad smoothing prevents the inner surface rings from overtaking at the hinge.
 for layer in range(4):
  nxt=[]
  for k in range(len(rows)):
   kernel=[(-1,1),(0,2),(1,1)] if uniform else [(-2,1),(-1,2),(0,3),(1,2),(2,1)]
   targets=[(current[min(len(rows)-1,max(0,k+off))],w) for off,w in kernel]
   nxt.append(blend_point(f'SMOOTH_{layer}_{key}_{k:02d}',targets))
  current=nxt
 bpy.context.view_layer.update()
 for k,row in enumerate(rows):
  row['target']=current[k];row['center_smooth']=current[k].matrix_world.translation.copy()
  prev=current[max(0,k-1)];nxt=current[min(len(rows)-1,k+1)]
  pointer=empty('AIM_'+row['name'])
  for axis,letter in enumerate(['X','Y','Z']):
   d=pointer.driver_add('location',axis).driver;d.type='SCRIPTED';d.expression='a+b-c' if k in [0,len(rows)-1] else 'a+(b-c)*0.5'
   for vn,target in [('a',current[k]),('b',nxt),('c',prev)]:
    v=d.variables.new();v.name=vn;v.type='TRANSFORMS';v.targets[0].id=target;v.targets[0].transform_type='LOC_'+letter;v.targets[0].transform_space='WORLD_SPACE'
  row['pointer']=pointer;row['reference']=('upperarm_' if key.startswith('F') else 'thigh_')+key[-1]
  allrings.append(row)
 records[key]=rows
bpy.context.view_layer.update();bpy.context.view_layer.objects.active=a;bpy.ops.object.mode_set(mode='EDIT');eb=a.data.edit_bones
for row in allrings:
 center=row['center_smooth'];direction=(row['pointer'].matrix_world.translation-center).normalized();x=Vector((1,0,0));x=(x-direction*x.dot(direction)).normalized();z=x.cross(direction).normalized()
 mat=Matrix(((x.x,direction.x,z.x,center.x),(x.y,direction.y,z.y,center.y),(x.z,direction.z,z.z,center.z),(0,0,0,1)))
 b=eb.new(row['name']);b.length=.004;b.matrix=mat;b.parent=eb['root'];b.use_deform=True
bpy.ops.object.mode_set(mode='OBJECT')
for row in allrings:
 p=a.pose.bones[row['name']]
 c=p.constraints.new('COPY_LOCATION');c.target=row['target'];c.owner_space='WORLD';c.target_space='WORLD'
 c=p.constraints.new('COPY_ROTATION');c.target=a;c.subtarget=row['reference'];c.owner_space='WORLD';c.target_space='WORLD'
 c=p.constraints.new('DAMPED_TRACK');c.target=row['pointer'];c.track_axis='TRACK_Y'
 g=m.vertex_groups.new(name=row['name'])
 if row['fixed']:continue
 for i in row['indices']:
  for old in [x.group for x in m.data.vertices[i].groups]:m.vertex_groups[old].remove([i])
 if row['indices']:g.add(row['indices'],1.,'REPLACE')
 a.data.collections['Mechanism'].assign(a.data.bones[row['name']])
# Extend the deformation path into the shoulder/thigh, instead of squeezing the
# whole bend into a few millimeters below the body.
for reg,(key,rows) in enumerate(records.items() if not uniform else [],1):
 upper=('upperarm_' if key.startswith('F') else 'thigh_')+key[-1];gi=m.vertex_groups[upper].index
 boundary={i for p in m.data.polygons if regions.data[p.index].value==reg for i in p.vertices if m.data.vertices[i].co.z>=.0309}
 for v in m.data.vertices:
  if v.index in boundary:
   for old in [x.group for x in v.groups]:m.vertex_groups[old].remove([v.index])
   m.vertex_groups[rows[4]['name']].add([v.index],1.,'REPLACE');continue
  weight=next((g.weight for g in v.groups if g.group==gi),0)
  if weight<1e-6 or v.co.z<.031:continue
  z=v.co.z;k=next((j for j in range(len(rows)-1) if rows[j]['z']>=z>=rows[j+1]['z']),0)
  den=rows[k]['z']-rows[k+1]['z'];t=max(0,min(1,(rows[k]['z']-z)/den))
  m.vertex_groups[upper].remove([v.index])
  for rr,ww in [(rows[k],weight*(1-t)),(rows[k+1],weight*t)]:
   if ww>1e-6:m.vertex_groups[rr['name']].add([v.index],ww,'REPLACE')
a.update_tag();bpy.context.view_layer.update()
# Align bind orientation exactly to the evaluated neutral constraint orientation.
neutral={row['name']:a.pose.bones[row['name']].matrix.copy() for row in allrings}
bpy.ops.object.mode_set(mode='EDIT')
for n,mat in neutral.items():a.data.edit_bones[n].matrix=mat
bpy.ops.object.mode_set(mode='OBJECT');a.update_tag();bpy.context.view_layer.update()
a['surface_guide_note']=f'{len(allrings)} native skin-ring bones preserve cross-section shape; FBX export must bake constraints. No custom Python runtime.'
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/('SK_BlackCat_UniformJointRepair.blend' if uniform else 'SK_BlackCat_JointRepair_V3.blend')))
(O/'QA/surface_guides.json').write_text(json.dumps({key:[{'name':r['name'],'vertices':r['indices'],'rest_center':list(r['center']),'bind_center':list(r['center_smooth'])} for r in rows] for key,rows in records.items()},indent=2));print('SURFACE_GUIDES_ADDED',len(allrings))
