import bpy,json,pathlib,math
from mathutils import Vector
OUT=pathlib.Path(r'C:/Users/whghk/Catrun/SourceArt/Cinematics/ElevatorCat/Production01_20261125')
arm=bpy.data.objects['ARM_BlackCat_Final']; mesh=bpy.data.objects['SK_BlackCat_Final'];sc=bpy.context.scene
d={}
for an in ['Idle','Sleep','JumpDown','Landing','StandUp']:
 arm.animation_data.action=bpy.data.actions['AN_BlackCat_'+an];sc.frame_set(1);bpy.context.view_layer.update()
 d[an]={p.name:{'loc':list(p.location),'rot':list(p.rotation_quaternion),'scale':list(p.scale),'head':list(p.head)} for p in arm.pose.bones}
(OUT/'QA/base_poses.json').write_text(json.dumps(d,indent=2))
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.40
cam.location=(.35,-.55,.28);cam.rotation_euler=(Vector((0,0,.10))-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.engine='BLENDER_EEVEE';sc.eevee.taa_render_samples=16;sc.render.resolution_x=640;sc.render.resolution_y=640;sc.render.resolution_percentage=100
sc.world=bpy.data.worlds.new('QA_World');sc.world.color=(.2,.2,.2)
for n,loc,power,size in [('Key',(.3,-.4,.6),35,.5),('Rim',(-.3,.2,.4),45,.3),('Fill',(-.4,-.4,.2),15,.4)]:
 l=bpy.data.objects.new(n,bpy.data.lights.new(n,'AREA'));sc.collection.objects.link(l);l.location=loc;l.data.energy=power;l.data.shape='DISK';l.data.size=size;l.rotation_euler=(Vector((0,0,.1))-l.location).to_track_quat('-Z','Y').to_euler()
for an in ['Idle','Sleep']:
 arm.animation_data.action=bpy.data.actions['AN_BlackCat_'+an];sc.frame_set(1);sc.render.filepath=str(OUT/'QA'/('source_'+an+'.png'));bpy.ops.render.render(write_still=True)
src=r'C:/Users/whghk/Desktop/CastleKit/Stage2To3_Elevator/Production01_20261125/Assemblies/ASM_E23_Elevator.blend'
with bpy.data.libraries.load(src,link=False) as (a,b):b.objects=a.objects
for o in b.objects:
 if o:sc.collection.objects.link(o)
bpy.context.view_layer.update()
dd=[]
for o in b.objects:
 if o and any(x in o.name for x in ['Grip','Control','Floor']):
  dd.append({'name':o.name,'type':o.type,'parent':o.parent.name if o.parent else None,'location':list(o.matrix_world.translation),'dimensions':list(o.dimensions),'bounds': [list(o.matrix_world@Vector(c)) for c in o.bound_box] if o.type=='MESH' else None})
(OUT/'QA/elevator_inspection.json').write_text(json.dumps(dd,indent=2));print('ELEVATOR',dd)
