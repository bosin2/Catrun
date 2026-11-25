import bpy,sys,json,pathlib,math
from mathutils import Vector
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final']
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
full='full' in args
only=next((x.split('=',1)[1].split(',') for x in args if x.startswith('only=')),None)
for o in sc.objects:
 if o.type=='MESH' and o!=mesh:
  # Cutaway preserves floor, ring and chain; source elevator is never written.
  o.hide_render=not any(t in o.name for t in ['Platform','ControlRing','ControlChain']) or o.name.startswith('UCX')
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.lens=50
sc.render.engine='BLENDER_EEVEE';sc.eevee.taa_render_samples=8;sc.render.resolution_x=512;sc.render.resolution_y=512;sc.render.resolution_percentage=100
sc.world=bpy.data.worlds.new('QA_World');sc.world.color=(.13,.15,.18)
sc.view_settings.view_transform='AgX'
for n,loc,power,size in [('Key',(1,-1,1.6),100,1.5),('Rim',(-.7,.5,1.2),100,1),('Fill',(-1,-1,.5),60,1)]:
 o=bpy.data.objects.new(n,bpy.data.lights.new(n,'AREA'));sc.collection.objects.link(o);o.location=loc;o.data.energy=power;o.data.size=size;o.rotation_euler=(Vector((0,0,.3))-o.location).to_track_quat('-Z','Y').to_euler()
# A plain reference floor only when the actual platform naming isn't captured.
if not any(o.type=='MESH' and not o.hide_render and o!=mesh and 'Platform' in o.name for o in sc.objects):
 me=bpy.data.meshes.new('QA_Floor');me.from_pydata([(-.55,-.5,0),(.55,-.5,0),(.55,.5,0),(-.55,.5,0)],[],[(0,1,2,3)]);o=bpy.data.objects.new('QA_Floor',me);sc.collection.objects.link(o)
 m=bpy.data.materials.new('QA_Floor');m.diffuse_color=(.15,.17,.20,1);m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=m.diffuse_color;o.data.materials.append(m)
manifest=json.loads((OUT/'manifest.json').read_text());pull=bpy.data.objects['ROOT_ControlPull'];pull_action=pull.animation_data.action;pull_base=pull.location.copy()
views={'front':(0,-1.5,.4),'side':(1.5,0,.35),'oblique':(.95,-1.3,.75)}
def camera(view,target,size):
 cam.location=Vector(target)+Vector(views[view]);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=size
def setclip(name,f):
 arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_'+name]
 master_f=f+({'JumpGrab':0,'HangPull':24,'ReleaseLand':54}.get(name,0))
 if name in ['MASTER_JumpPullLand','JumpGrab','HangPull','ReleaseLand']:
  pull.animation_data.action=pull_action;sc.frame_set(master_f)
  # Re-evaluate character at clip time while sampling reference action explicitly.
  loc=pull.location.copy();pull.animation_data.action=None;sc.frame_set(f);pull.location=loc
 else:pull.animation_data.action=None;pull.location=pull_base;sc.frame_set(f)
 bpy.context.view_layer.update()
if not full:
 tests={'MASTER_JumpPullLand':[1,7,13,20,24,29,39,48,55,62,70,73,78,102],'StartleTail':[1,12,23,61],'PeekDown':[1,49,103,133,174,276],'RideBalance':[1,23,46,69],'LoafIdle':[1,61,121],'LoafStartleRise':[1,38,41,48,59,82]}
 if 'final-stills' in args:tests={'MASTER_JumpPullLand':[24,48,73],'StartleTail':[12],'PeekDown':[133],'LoafIdle':[61],'LoafStartleRise':[39,48]}
 for name,frames in tests.items():
  for view in ['oblique','side']:
   for f in frames:
    setclip(name,f);center=arm.pose.bones['pelvis'].head.copy();center.z+=.04
    camera(view,center,.36 if name!='MASTER_JumpPullLand' or f<20 or f>70 else .42)
    sc.render.filepath=str(OUT/'QA'/('Stills_Final' if 'final-stills' in args else 'Stills')/f'{name}_{view}_{f:03d}.png');bpy.ops.render.render(write_still=True)
else:
 for clip in manifest['clips']:
  if only and clip['id'] not in only:continue
  name=clip['action'].replace('AN_BlackCat_Elevator_','');num=clip['frames'][1]
  for view in views:
   for f in range(1,num+1,2):
    setclip(name,f)
    if name in ['JumpGrab','HangPull','ReleaseLand']:target=(0,-.07,.37);size=.86
    elif name=='PeekDown':target=(0,-.21,.10);size=.72
    else:target=(0,-.01,.105);size=.34
    camera(view,target,size);sc.render.filepath=str(OUT/'Previews'/'Frames'/clip['id']/view/f'{(f-1)//2:04d}.png');bpy.ops.render.render(write_still=True)
 print('FULL_RENDER_DONE')
