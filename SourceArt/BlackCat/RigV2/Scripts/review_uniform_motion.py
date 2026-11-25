import bpy,json,math,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
code=Path(__file__).with_name('scan_uniform_surface.py').read_text(encoding='utf-8-sig')
exec(compile(code.split("report={'neutral'")[0],__file__,'exec'))
cam=bpy.data.objects.new('MotionReview',bpy.data.cameras.new('MotionReview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.19
cam.location=(.3,-.4,.135);cam.rotation_euler=(Vector((0,0,.055))-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=640;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
sc.display.shading.light='STUDIO';sc.display.shading.color_type='MATERIAL';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True
sc.display.shading.background_type='WORLD'
if not sc.world:sc.world=bpy.data.worlds.new('QA_World')
sc.world.color=(.18,.18,.18)
report={}
reset();co,_,_=evaluated();materials=np.array([p.material_index for p in m.data.polygons]);mask=(materials[poly]==0)&(co[tris].max(axis=1)[:,2]<.085)
if m.data.attributes.get('uniform_body_surface'):
 authored=np.array([v.value for v in m.data.attributes['uniform_body_surface'].data]);mask &= authored[poly]>0
lower=np.where(mask)[0]
report['neutral_lower_body']=surface(co,lower)
for kind in ['Body','PawReach','Curl']:
 reset();a.animation_data.action=bpy.data.actions['V2_TEST_'+kind];out=O/'Previews'/'Motion'/kind;out.mkdir(parents=True,exist_ok=True);rows=[]
 for f in range(1,92):
  sc.frame_set(f);a.update_tag();bpy.context.view_layer.update();co,_,_=evaluated()
  row={'frame':f,'limbs':{k:surface(co,ids) for k,ids in selected.items()},'lower_body':surface(co,lower)};rows.append(row)
  if '--no-render' not in sys.argv:
   sc.render.filepath=str(out/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
 report[kind]=rows
 print('MOTION',kind,'max limb intersections',max(x['intersection_pairs'] for row in rows for x in row['limbs'].values()),'max lower body',max(row['lower_body']['intersection_pairs'] for row in rows),flush=True)
(O/'QA/motion_surface.json').write_text(json.dumps(report,indent=2))
