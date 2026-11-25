import bpy,json
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH');out={'objects':[(o.name,o.type,list(o.scale)) for o in sc.objects],'units':sc.unit_settings.scale_length,'bones':[{ 'name':b.name,'parent':b.parent.name if b.parent else None,'connect':b.use_connect,'rest':[list(r) for r in b.matrix_local]} for b in a.data.bones], 'poses':{}}
cam=bpy.data.objects.new('ReferencePreview',bpy.data.cameras.new('ReferencePreview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.34;cam.location=(.32,-.45,.18);cam.rotation_euler=(Vector((0,.01,.105))-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=640;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.world=bpy.data.worlds.new('ReviewWorld');sc.world.color=(.20,.20,.20)
(O/'QA').mkdir(exist_ok=True)
for action,frames in [('AN_BlackCat_Idle',[1]),('AN_BlackCat_PortalInspect',[121]),('AN_BlackCat_PortalJumpIn',[1,10,12,13,18,18.5,19])]:
 a.animation_data.action=bpy.data.actions[action]
 for f in frames:
  sc.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update();k=action+'_'+str(f)
  out['poses'][k]={p.name:{'matrix':[list(r) for r in p.matrix],'basis':[list(r) for r in p.matrix_basis],'head':list(p.head),'tail':list(p.tail)} for p in a.pose.bones}
  if f in [1,12,19]:sc.render.filepath=str(O/'QA'/(k+'.png'));bpy.ops.render.render(write_still=True)
(O/'source_reference.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print('REFERENCE_READY',a.name,m.name,len(a.data.bones),flush=True)
