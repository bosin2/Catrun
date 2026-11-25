import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH');(O/'Previews').mkdir(exist_ok=True)
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.32
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=640;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world=bpy.data.worlds.new('ReviewWorld');sc.world.color=(.24,.24,.24)
def view(loc):cam.location=loc;cam.rotation_euler=(Vector((0,.015,.110))-cam.location).to_track_quat('-Z','Y').to_euler()
qa={'clips':{}}
for name,frames in [('AN_BlackCat_PortalPawEar',[1,9,13,23,33,49]),('AN_BlackCat_PortalCrouchWiggle',[1,10,14,18,22,26,37]),('AN_BlackCat_PortalTakeoffBridge',[1,4,7,8,10])]:
 a.animation_data.action=bpy.data.actions[name];end=int(a.animation_data.action.frame_range[1]);positions=[]
 for f in range(1,end+1):
  sc.frame_set(f);bpy.context.view_layer.update();ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
  sample={'frame':f,'bones':{n:list(a.pose.bones[n].head) for n in ['root','pelvis','chest','paw_F_L','paw_F_R','paw_H_L','paw_H_R']},'soles':{}}
  for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']:
   ids=[v.index for v in m.data.vertices if sum(g.weight for g in v.groups if m.vertex_groups[g.group].name==n)>.8]
   pts=[me.vertices[i].co.copy() for i in ids];z=min(p.z for p in pts);bottom=[p for p in pts if p.z<z+.0003];sample['soles'][n]={'min_z_m':z,'bottom_center_m':list(sum(bottom,Vector())/len(bottom))}
  positions.append(sample);ev.to_mesh_clear()
  if f in frames:
   for label,loc in [('front',(.32,-.45,.15)),('rear',(.32,.45,.16))]:
    view(loc);sc.render.filepath=str(O/'QA'/f'{name}_{f}_{label}.png');bpy.ops.render.render(write_still=True)
 qa['clips'][name]=positions
(O/'QA'/'contact_samples.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
if '--stills-only' not in sys.argv:
 sc.render.resolution_x=480;sc.render.resolution_y=480
 for label,loc in [('front',(.32,-.45,.15)),('rear',(.32,.45,.16))]:
  folder=O/'Previews'/label;folder.mkdir(exist_ok=True);view(loc);i=0
  for name,start,end in [('AN_BlackCat_PortalPawEar',1,48),('AN_BlackCat_PortalCrouchWiggle',1,36),('AN_BlackCat_PortalTakeoffBridge',1,9),('AN_BlackCat_PortalJumpIn',19,37)]:
   a.animation_data.action=bpy.data.actions[name]
   for f in range(start,end+1):
    sc.frame_set(f);sc.render.filepath=str(folder/f'{i:04}.png');bpy.ops.render.render(write_still=True);i+=1
print('QA_RENDER_READY',flush=True)
