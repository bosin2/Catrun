import bpy
from mathutils import Vector
a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene;col=bpy.data.collections['Mechanism - Surface Guides'];rid=m.data.attributes['uniform_ring_id'];a.animation_data.action=None;a['controls_enabled']=0.
for p in a.pose.bones:p.matrix_basis.identity()
a.update_tag();bpy.context.view_layer.update();records=[]
for code,key in enumerate(['F_L','F_R','H_L','H_R'],1):
 targets=[]
 for suffix,ring,bone in [('Root',1,'chest' if code<3 else 'pelvis'),('Low',2,'skin_'+key+'_02')]:
  vs=[v for v in m.data.vertices if rid.data[v.index].value==code*100+ring];center=sum((v.co for v in vs),Vector())/len(vs)
  ob=bpy.data.objects.new('FACET_'+key+'_'+suffix,None);col.objects.link(ob);ob.location=center;ob.hide_render=True;ob.hide_set(True);c=ob.constraints.new('CHILD_OF');c.target=a;c.subtarget=bone;c.inverse_matrix=(a.matrix_world@a.pose.bones[bone].matrix).inverted();targets.append(ob)
 ob=bpy.data.objects.new('FACET_'+key+'_Center',None);col.objects.link(ob);ob.hide_render=True;ob.hide_set(True)
 for i,target in enumerate(targets):c=ob.constraints.new('COPY_LOCATION');c.target=target;c.influence=1/(i+1)
 records.append((code,key,ob,targets[1]))
bpy.context.view_layer.update();bpy.context.view_layer.objects.active=a;bpy.ops.object.mode_set(mode='EDIT')
for code,key,center,end in records:
 b=a.data.edit_bones.new('skin_upperFacet_'+key);b.head=center.matrix_world.translation;b.tail=end.matrix_world.translation;b.parent=a.data.edit_bones['root'];b.use_deform=True
bpy.ops.object.mode_set(mode='OBJECT')
for code,key,center,end in records:
 name='skin_upperFacet_'+key;p=a.pose.bones[name];c=p.constraints.new('COPY_LOCATION');c.target=center;c.owner_space='WORLD';c.target_space='WORLD';c=p.constraints.new('COPY_ROTATION');c.target=a;c.subtarget='skin_'+key+'_02';c.owner_space='WORLD';c.target_space='WORLD';c=p.constraints.new('DAMPED_TRACK');c.target=end;c.track_axis='TRACK_Y';a.data.collections['Mechanism'].assign(a.data.bones[name])
a.update_tag();bpy.context.view_layer.update();mats={p.name:p.matrix.copy() for p in a.pose.bones if p.name.startswith('skin_upperFacet_')}
bpy.ops.object.mode_set(mode='EDIT')
for n,mat in mats.items():a.data.edit_bones[n].matrix=mat
bpy.ops.object.mode_set(mode='OBJECT')
for code,key,center,end in records:
 g=m.vertex_groups.new(name='skin_upperFacet_'+key);ids=[v.index for v in m.data.vertices if rid.data[v.index].value==code*100+7]
 for i in ids:
  for old in [x.group for x in m.data.vertices[i].groups]:m.vertex_groups[old].remove([i])
 g.add(ids,1.,'REPLACE')
a['surface_guide_note']='32 native surface guide bones; export requires constraint baking.'
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;sc.frame_set(1);a.update_tag();bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
