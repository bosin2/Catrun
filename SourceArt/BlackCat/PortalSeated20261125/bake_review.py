import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).parent
render_from=int(sys.argv[sys.argv.index('--render-from')+1]) if '--render-from' in sys.argv else 0
src=(HERE/'create_revision.py').read_text(encoding='utf8').split('cam=preview_setup()')[0]
exec(compile(src,str(HERE/'create_revision.py'),'exec'))
allbones=list(a.pose.bones);newactions=[];motion={};sc.render.fps=30
for name,kind,end in [('AN_Portal_SeatedListenTouch','touch',91),('AN_Portal_HipsBackWiggle','prepare',53),('AN_Portal_SeatedTakeoff','launch',13),('AN_Portal_WalkReview','walk',121),('AN_Portal_AirReach','flight',19)]:
 act=bpy.data.actions.new(name);act.use_fake_user=True;prev={};data=[]
 for f in range(1,end+1):
  evaluate(kind,f);a.animation_data.action=act
  for p in allbones:
   q=p.rotation_quaternion.copy()
   if p.name in prev and q.dot(prev[p.name])<0:q.negate();p.rotation_quaternion=q
   prev[p.name]=q.copy()
   for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
  data.append({n:[list(row) for row in a.pose.bones[n].matrix] for n in original_names})
 for fc in fcurves(act):
  for k in fc.keyframe_points:k.interpolation='LINEAR'
 newactions.append(act);motion[name]=data
(O/'QA'/'pose_samples.json').write_text(json.dumps(motion),encoding='utf8')
# A separate mesh/skeleton revision is necessary for support-ring channels.
# It is not safe to import these animations onto the old 78-bone UE mesh alone.
a.animation_data.action=newactions[0];sc.frame_start=1;sc.frame_end=91;sc.frame_set(32);update()
bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_SeatedPortal_Review.blend'))
qa={};contact=[]
for act in newactions[:3]:
 a.animation_data.action=act;end=int(act.frame_range[1]);frames=[]
 for f in range(1,end+1):
  sc.frame_set(f);update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();item={'f':f,'body_min_z':min(v.co.z for v in me.vertices),'feet':{}}
  for k,ids in skin['vertex_groups'].items():
   vs=[me.vertices[i].co.copy() for i in ids];item['feet'][k]={'min_z':min(v.z for v in vs),'min_y':min(v.y for v in vs)}
  if act==newactions[0] and 57<=f<=64:contact.append(item['feet']['F_L']['min_y']-PORTAL_Y)
  frames.append(item);ev.to_mesh_clear()
 qa[act.name]=frames
(O/'QA'/'contact_and_ground.json').write_text(json.dumps({'portal_plane_y':PORTAL_Y,'contact_distance_m':contact,'frames':qa},indent=2),encoding='utf8')
cam=preview_setup();cam.location=(.43,-.32,.18);cam.rotation_euler=(Vector((0,-.055,.15))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.58
# The reference ripple proves where the paw intersects the vertical target.
blue=bpy.data.materials['PortalBlueReference'];bpy.ops.mesh.primitive_torus_add(major_segments=24,minor_segments=5,major_radius=.024,minor_radius=.0008,location=(.042,PORTAL_Y+.0005,.068),rotation=(math.pi/2,0,0));ripple=bpy.context.object;ripple.name='REFERENCE_ContactRipple';ripple.data.materials.append(blue)
sc.render.resolution_x=800;sc.render.resolution_y=640
folder=O/'Previews'/'frames';folder.mkdir(exist_ok=True);i=0
full=bpy.data.actions.new('AN_REVIEW_FullPortalSequence');full.use_fake_user=True;prev_full={}
for name,lo,hi in [('AN_Portal_WalkReview',1,120),('AN_Portal_SeatedListenTouch',1,90),('AN_Portal_HipsBackWiggle',1,52),('AN_Portal_SeatedTakeoff',1,12),('AN_Portal_AirReach',1,19)]:
 a.animation_data.action=bpy.data.actions[name]
 for f in range(lo,hi+1):
  a.animation_data.action=bpy.data.actions[name];sc.frame_set(f);update();a.location=(0,0,0)
  if name=='AN_Portal_WalkReview':a.location.y=(120-f)*.001
  elif name=='AN_Portal_SeatedTakeoff':
   t=max(0,(f-9)/4);a.location.y=-.045*t*t;a.location.z=.020*t*t
  elif name=='AN_Portal_AirReach':
   t=(f-1)/18;a.location.y=-.045-.31*t;a.location.z=.02+.11*math.sin(math.pi*.65*t)
  # Rear three-quarter reveals the two equal hip sways and keeps takeoff in
  # the same shot. Camera only follows after the hind paws have left.
  if name in ['AN_Portal_HipsBackWiggle','AN_Portal_SeatedTakeoff','AN_Portal_AirReach']:
   cam.location=(.40,.36,.20);target=Vector((0,-.045,.13))
   if name=='AN_Portal_AirReach':target+=a.location*.55
  else:cam.location=(.43,-.32,.18);target=Vector((0,-.055,.15))
  cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.keyframe_insert('location',frame=i+1);cam.keyframe_insert('rotation_euler',frame=i+1)
  visible=name=='AN_Portal_SeatedListenTouch' and 57<=f<=66;ripple.hide_render=not visible;ripple.scale=(1+(f-57)*.08,)*3 if visible else (1,1,1)
  a.animation_data.action=full
  for p in allbones:
   q=p.rotation_quaternion.copy()
   if p.name in prev_full and q.dot(prev_full[p.name])<0:q.negate();p.rotation_quaternion=q
   prev_full[p.name]=q.copy()
   for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=i+1,group=p.name)
  a.keyframe_insert('location',frame=i+1);ripple.keyframe_insert('hide_render',frame=i+1);ripple.keyframe_insert('scale',frame=i+1)
  for fc in fcurves(full):
   if len(fc.keyframe_points):fc.keyframe_points[-1].interpolation='LINEAR'
  sc.frame_set(i+1)
  if i>=render_from:
   sc.render.filepath=str(folder/f'{i:04}.png');bpy.ops.render.render(write_still=True)
  i+=1
sc.frame_start=1;sc.frame_end=i;a.animation_data.action=full;sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SC_BlackCat_PortalReview.blend'))
print('REVIEW_BAKED',i,'frames','contact',contact,flush=True)
