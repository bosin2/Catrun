import bpy,sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent));import build_sit_sleep as B
a=B.a;sc=B.sc;a.animation_data.action=bpy.data.actions['AN_BlackCat_Sleep'];sc.frame_set(121);a.animation_data.action=None;B.sleep_tail(4)
cam=bpy.data.objects.new('SleepPreview',bpy.data.cameras.new('SleepPreview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.30
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world=bpy.data.worlds.new('ReviewWorld');sc.world.color=(.24,.24,.24)
for label,loc in [('side',(.5,0,.12)),('threequarter',(.32,-.45,.25)),('above',(.2,0,.5))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,.015,.070))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(B.O/'Previews'/f'sleep_fixed_{label}.png');bpy.ops.render.render(write_still=True)
