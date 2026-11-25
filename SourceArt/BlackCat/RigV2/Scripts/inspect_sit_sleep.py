import bpy,json,sys
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1]/'SitSleep';O.mkdir(exist_ok=True);(O/'Before').mkdir(exist_ok=True);sc=bpy.context.scene
a=next(o for o in sc.objects if o.type=='ARMATURE');meshes=[o for o in sc.objects if o.type=='MESH' and o.vertex_groups]
report={'file':bpy.data.filepath,'actions':[(x.name,list(x.frame_range)) for x in bpy.data.actions],'bones':[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in a.data.bones if not b.name.startswith(('CTRL','support','skin','lid'))]}
(O/('inspect_'+('original' if 'Final.blend' in bpy.data.filepath else 'latest')+'.json')).write_text(json.dumps(report,indent=2))
print('ACTIONS',report['actions'],flush=True)
cam=bpy.data.objects.new('QA_SitSleepCamera',bpy.data.cameras.new('QA_SitSleepCamera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.30
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True;sc.display.shading.background_type='WORLD'
if not sc.world:sc.world=bpy.data.worlds.new('QA_World')
sc.world.color=(.25,.25,.25)
for action in bpy.data.actions:
 if not any(k in action.name.lower() for k in ['sleep','sit']):continue
 a.animation_data.action=action
 if 'controls_enabled' in a:a['controls_enabled']=0.
 for f in [int(action.frame_range[0]),int(sum(action.frame_range)/2)]:
  sc.frame_set(f);a.update_tag();bpy.context.view_layer.update()
  for label,loc in [('front',(0,-.5,.15)),('side',(.5,-.05,.14)),('above',(.24,-.3,.34))]:
   target=Vector((0,0,.075));cam.location=loc;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Before'/f'{Path(bpy.data.filepath).stem}_{action.name}_{f}_{label}.png');bpy.ops.render.render(write_still=True)
print('INSPECTED')
