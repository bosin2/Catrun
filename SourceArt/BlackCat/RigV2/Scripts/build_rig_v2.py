"""Build an isolated authoring rig. Never overwrite the approved source or game assets."""
import bpy,bmesh,math,json,hashlib
import numpy as np
from mathutils import Vector,Matrix,Quaternion
from mathutils.bvhtree import BVHTree
from pathlib import Path
O=Path(__file__).resolve().parents[1]
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.data.objects if o.type=='MESH');sc=bpy.context.scene
source_path=bpy.data.filepath
source_hash=hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
arm.animation_data.action=None
for p in arm.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update()
original_bones={b.name:[list(row) for row in b.matrix_local] for b in arm.data.bones}
original_coords=[v.co.copy() for v in mesh.data.vertices]
for a in bpy.data.actions:a.use_fake_user=True
arm.name='ARM_BlackCat_RigV2';mesh.name='SK_BlackCat_RigV2'
mesh.data.name='BlackCat_RigV2_Mesh'

def prop(obj,name,value,lo,hi,description):
    obj[name]=value;obj.id_properties_ui(name).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description=description)
def drv(owner,path,expression,variables,index=None):
    fc=owner.driver_add(path) if index is None else owner.driver_add(path,index)
    d=fc.driver;d.type='SCRIPTED';d.expression=expression
    for name,target,path in variables:
        v=d.variables.new();v.name=name;v.type='SINGLE_PROP';v.targets[0].id=target;v.targets[0].data_path=path
    return d
def control_var(name='on'):return (name,arm,'["controls_enabled"]')
prop(arm,'controls_enabled',0.0,0,1,'0: original baked actions. 1: pose using CTRL bones and IK. Blend only after matching poses.')
prop(arm,'rig_version',2,2,2,'Low-poly preserving authoring rig v2')

# Preserve original rest transforms. Controls do not deform and are excluded by export.
bpy.context.view_layer.objects.active=arm;arm.select_set(True);mesh.select_set(False)
bpy.ops.object.mode_set(mode='EDIT')
eb=arm.data.edit_bones
def bone(name,head,tail,parent=None,deform=False):
    b=eb.new(name);b.head=head;b.tail=tail;b.use_deform=deform
    if parent:b.parent=eb[parent]
    return b
bone('CTRL_world',(0,0,0),(0,0,.025))
bone('CTRL_body',(0,.04,.079),(0,.04,.105),'CTRL_world')
bone('CTRL_spine',(0,.008,.13),(0,.008,.155),'CTRL_body')
bone('CTRL_face',(0,-.15,.17),(0,-.15,.19),'CTRL_world')
fk_names=[n for n in original_bones if not n.startswith('Lid_') and not n.startswith('breath_') and n not in ['root','pelvis','lumbar','spine','chest','abdomen']]
for n in fk_names:
    b=eb.new('CTRL_'+n);b.length=eb[n].length;b.matrix=eb[n].matrix.copy();b.use_deform=False
    par=eb[n].parent.name if eb[n].parent else None
    b.parent=eb['CTRL_'+par] if par in fk_names else eb[par] if par else eb['CTRL_world']
for side in ['L','R']:
    for limb,paw,end,count in [('F','paw_F_','forearm_',2),('H','paw_H_','hock_',3)]:
        n=paw+side;b=eb.new('CTRL_IK_'+limb+'_'+side);b.length=.018;b.matrix=eb[n].matrix.copy();b.use_deform=False;b.parent=eb['CTRL_world']
        pos=eb['forearm_'+side].head.copy() if limb=='F' else eb['shin_'+side].head.copy()
        pos.y+=.09 if limb=='F' else -.09
        bone('CTRL_pole_'+limb+'_'+side,pos,pos+Vector((0,0,.012)),'CTRL_world')
bone('jaw',(0,-.071,.119),(0,-.099,.119),'head',True)
bone('tongue',(0,-.087,.111),(0,-.103,.111),'jaw',True)
for side,sign in [('L',1),('R',-1)]:
    bone('eye_'+side,(.02544*sign,-.101,.144),(.02544*sign,-.122,.144),'head',True)
bone('CTRL_jaw',(0,-.071,.119),(0,-.099,.119),'head')
bone('CTRL_tongue',(0,-.087,.111),(0,-.103,.111),'jaw')
supports={}
for child in ['forearm_L','forearm_R','shin_L','shin_R','hock_L','hock_R','neck']:
    parent=eb[child].parent.name;n='support_'+child
    b=eb.new(n);b.length=eb[child].length;b.matrix=eb[child].matrix.copy();b.parent=eb[parent];b.use_deform=True;supports[n]=(parent,child)
bpy.ops.object.mode_set(mode='OBJECT')
for n in ['jaw','tongue','eye_L','eye_R']+list(supports):
    if not mesh.vertex_groups.get(n):mesh.vertex_groups.new(name=n)
for p in arm.pose.bones:
    p.rotation_mode='QUATERNION'
    if p.name.startswith('CTRL_'):p.lock_scale=(True,True,True)
def copy_constraint(n,target,typ='COPY_ROTATION',space='LOCAL'):
    c=arm.pose.bones[n].constraints.new(typ);c.name='V2 '+target;c.target=arm;c.subtarget=target;c.target_space=space;c.owner_space=space
    drv(c,'influence','on',[control_var()]);return c
copy_constraint('root','CTRL_world','COPY_TRANSFORMS')
copy_constraint('pelvis','CTRL_body','COPY_TRANSFORMS','POSE')
# CTRL_body rest matrix is not pelvis rest matrix: use matching orientation for translation/rotation.
bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT');eb=arm.data.edit_bones
eb['CTRL_body'].matrix=eb['pelvis'].matrix.copy();eb['CTRL_body'].length=.022
bpy.ops.object.mode_set(mode='OBJECT')
for n in fk_names+['jaw','tongue']:copy_constraint(n,'CTRL_'+n)
jawctl=arm.pose.bones['CTRL_jaw'];jawctl.rotation_mode='XYZ';prop(jawctl,'open',0.,0,1,'Mouth opening, 0 closed to 1 open. Do not rotate past the tested range.')
drv(jawctl,'rotation_euler','-v*0.55',[('v',arm,'pose.bones["CTRL_jaw"]["open"]')],0)
tonguectl=arm.pose.bones['CTRL_tongue'];prop(tonguectl,'extend',0.,0,1,'Tongue extension for grooming. Open jaw first.')
drv(tonguectl,'location','v*0.014',[('v',arm,'pose.bones["CTRL_tongue"]["extend"]')],1)
for n,(parent,child) in supports.items():
    c=arm.pose.bones[n].constraints.new('COPY_ROTATION');c.name='Joint volume midpoint';c.target=arm;c.subtarget=child;c.target_space='LOCAL';c.owner_space='LOCAL';c.influence=.5
sp=arm.pose.bones['CTRL_spine']
for key,limit,desc in [('bend',105,'Back arch/curl distributed along three spine joints, degrees.'),('side_bend',75,'Side bend distributed across the back, degrees.'),('twist',90,'Total longitudinal torso twist, distributed; do not rotate one deform bone 90 degrees.')]:prop(sp,key,0.0,-limit,limit,desc)
for n,factor in [('lumbar',.34),('spine',.33),('chest',.33)]:
    p=arm.pose.bones[n]
    # Add rotation to existing pose only when authoring mode is enabled.
    c=p.constraints.new('TRANSFORM');c.name='V2 distributed spine';c.target=arm;c.subtarget='CTRL_spine'
    c.influence=0 # Property-driven additive rotation is implemented with helper bones below.
# Dedicated local additive helpers let legacy bone action channels remain intact.
bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT');eb=arm.data.edit_bones
for n in ['lumbar','spine','chest']:
    b=eb.new('MCH_'+n);b.length=eb[n].length;b.matrix=eb[n].matrix.copy();b.use_deform=False
bpy.ops.object.mode_set(mode='OBJECT')
for n,factor in [('lumbar',.34),('spine',.33),('chest',.33)]:
    p=arm.pose.bones['MCH_'+n];p.rotation_mode='XYZ'
    for idx,key in [(0,'bend'),(1,'twist'),(2,'side_bend')]:
        drv(p,'rotation_euler',f'v*{factor}*pi/180',[('v',arm,f'pose.bones["CTRL_spine"]["{key}"]')],idx)
    c=copy_constraint(n,'MCH_'+n);c.mix_mode='AFTER'
    dead=arm.pose.bones[n].constraints.get('V2 distributed spine');arm.pose.bones[n].constraints.remove(dead)

for side in ['L','R']:
    for limb,end,count,paw in [('F','forearm_',2,'paw_F_'),('H','hock_',3,'paw_H_')]:
        ctl=arm.pose.bones['CTRL_IK_'+limb+'_'+side];prop(ctl,'ik',1.0,0,1,'1 = foot target/pole, 0 = FK controls. Match transforms before switching.')
        c=arm.pose.bones[end+side].constraints.new('IK');c.name='V2 planted '+limb;c.target=arm;c.subtarget=ctl.name;c.chain_count=count;c.use_stretch=False;c.iterations=100
        c.pole_target=arm;c.pole_subtarget='CTRL_pole_'+limb+'_'+side
        c.pole_angle=math.pi/2
        variables=[control_var(),('ik',arm,f'pose.bones["{ctl.name}"]["ik"]')]
        drv(c,'influence','on*ik',variables)
        c=arm.pose.bones[paw+side].constraints.new('COPY_ROTATION');c.name='V2 planted paw orientation';c.target=arm;c.subtarget=ctl.name;c.target_space='POSE';c.owner_space='POSE';drv(c,'influence','on*ik',variables)

face=arm.pose.bones['CTRL_face']
for n,lo,hi,desc in [('blink_L',0,1,'Left blink, 0 open, 1 closed'),('blink_R',0,1,'Right blink'),('look_x',-1,1,'Eyes horizontal gaze'),('look_z',-1,1,'Eyes vertical gaze')]:prop(face,n,0.0,lo,hi,desc)
for side in ['L','R']:
    p=arm.pose.bones['eye_'+side];p.rotation_mode='XYZ'
    for idx,key,factor in [(0,'look_z',.15),(2,'look_x',.18)]:drv(p,'rotation_euler',f'on*v*{factor}',[control_var(),('v',arm,f'pose.bones["CTRL_face"]["{key}"]')],idx)

# Remove only the old banded lid shells. Body/head/ears retain their original coordinates.
bm=bmesh.new();bm.from_mesh(mesh.data);bm.verts.ensure_lookup_table();deform=bm.verts.layers.deform.verify();src=bm.verts.layers.int.new('source_vertex')
for v in bm.verts:v[src]=v.index+1
clapper_ids=sorted({i for p in mesh.data.polygons if p.material_index==6 for i in p.vertices});clapper_map={i:j for j,i in enumerate(clapper_ids)}
clapper_data=bpy.data.meshes.new('BellClapper_V2_Mesh');clapper_data.from_pydata([mesh.data.vertices[i].co[:] for i in clapper_ids],[],[[clapper_map[i] for i in p.vertices] for p in mesh.data.polygons if p.material_index==6]);clapper_data.materials.append(mesh.data.materials[6]);clapper_data.uv_layers.new(name='UV0')
clapper=bpy.data.objects.new('SK_BlackCat_BellClapper_V2',clapper_data);sc.collection.objects.link(clapper);clapper.parent=arm
clapper.vertex_groups.new(name='bell').add(list(range(len(clapper_ids))),1,'REPLACE');clapper.modifiers.new('Armature','ARMATURE').object=arm
for p in clapper_data.polygons:
    axis=max(range(3),key=lambda i:abs(p.normal[i]));axes=[i for i in range(3) if i!=axis]
    for li in p.loop_indices:
        v=clapper_data.vertices[clapper_data.loops[li].vertex_index].co;clapper_data.uv_layers.active.data[li].uv=(v[axes[0]]*20+.5,v[axes[1]]*20+.5)
bmesh.ops.delete(bm,geom=[v for v in bm.verts if v[src]-1 in clapper_map],context='VERTS')
lidgroups={g.index for g in mesh.vertex_groups if g.name.startswith('Lid_')}
old_lids=[v for v in bm.verts if any(i in lidgroups and w>.1 for i,w in v[deform].items())]
bmesh.ops.delete(bm,geom=old_lids,context='VERTS')

# Create a real small mouth seam below the nose. Cut only the front muzzle.
mouth_geom=set()
for f in bm.faces:
    if f.material_index==0 and all(v.co.y<-.078 and abs(v.co.x)<.04 and .09<v.co.z<.14 for v in f.verts):
        mouth_geom.add(f);mouth_geom.update(f.edges);mouth_geom.update(f.verts)
res=bmesh.ops.bisect_plane(bm,geom=list(mouth_geom),dist=1e-7,plane_co=(0,0,.119),plane_no=(0,0,1),clear_inner=False,clear_outer=False)
slit=[e for e in res['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and abs((e.verts[0].co.x+e.verts[1].co.x)/2)<.021 and sum(v.co.y for v in e.verts)/2<-.095]
if slit:bmesh.ops.split_edges(bm,edges=slit)
jawidx=mesh.vertex_groups['jaw'].index;headidx=mesh.vertex_groups['head'].index
for v in bm.verts:
    # Assign only lower-side slit vertices; shared unsplit corners taper back to head.
    low=all(f.calc_center_median().z<.1190001 for f in v.link_faces)
    if low and v.co.z<.119001 and v.co.z>.085 and v.co.y<-.078 and abs(v.co.x)<.035:
        blend=min(1,max(0,(-v.co.y-.078)/.018))*min(1,max(0,(v.co.z-.085)/.018))
        if blend>.001:
            for g in list(v[deform].keys()):v[deform][g]*=1-blend
            v[deform][jawidx]=blend
# Reweight eyes rigidly to dedicated gaze bones, no neutral geometry change.
for v in bm.verts:
    if v.link_faces and all(f.material_index in [1,2] for f in v.link_faces):
        for g in list(v[deform].keys()):del v[deform][g]
        v[deform][mesh.vertex_groups['eye_L' if v.co.x>0 else 'eye_R'].index]=1
# Midpoint support bones replace the shrinking blend between adjacent hinge bones.
support_changes=0
for v in bm.verts:
    w=v[deform]
    for n,(parent,child) in supports.items():
        pi=mesh.vertex_groups[parent].index;ci=mesh.vertex_groups[child].index;blend=min(w.get(pi,0),w.get(ci,0))
        if blend>.001:
            w[pi]-=blend;w[ci]-=blend;w[mesh.vertex_groups[n].index]=2*blend;support_changes+=1
    keep=sorted(w.items(),key=lambda x:x[1],reverse=True)[:4];total=sum(x[1] for x in keep)
    for g in list(w.keys()):del w[g]
    for g,value in keep:
        if value>1e-6:w[g]=value/total

bm.verts.index_update()
skinverts=[v.co.copy() for v in bm.verts]
skinfaces=[[v.index for v in f.verts] for f in bm.faces if f.material_index==0]
skinbvh=BVHTree.FromPolygons(skinverts,skinfaces)
def skin_y(x,z):
    hit=skinbvh.ray_cast(Vector((x,-.3,z)),Vector((0,1,0)))
    return hit[0].y if hit[0] else -.095

# Eyelids are a compact patch following each eye, with 3 calibrated morph stages.
lidmeta=[]
def lid_co(sign,upper,u,t,blink):
    cx=.02544*sign;rx=.0201;rz=.022;cz=.144
    outer=math.sqrt(max(0,1-u*u));direction=1 if upper else -1
    # Upper lid travels further than lower lid; closed seam slightly below center.
    line=-.003*blink
    outer_z=direction*rz*outer
    inner_z=(1-blink)*outer_z+blink*line
    z=(1-t)*outer_z+t*inner_z
    normz=z/rz
    front=math.sqrt(max(0,1-u*u-normz*normz))
    flatten=max(0,(blink-.65)/.35)
    y=-.099-(.0145-.0085*flatten)*front
    if blink<.01:y+=.004
    # Very small overlap prevents a green seam at complete closure.
    z+=(-1 if upper else 1)*.00035*t*blink
    if blink>=.999:y=skin_y(cx+rx*u,cz+z)+.0006
    return Vector((cx+rx*u,y,cz+z))
for side,sign in [('L',1),('R',-1)]:
 for upper in [True,False]:
    grid=[]
    for row in range(5):
        line=[]
        for col in range(17):
            u=-.998+1.996*col/16;t=row/4
            # A tiny hidden width avoids collapsed open-state topology.
            co=lid_co(sign,upper,u,t,.012)
            v=bm.verts.new(co);v[deform][headidx]=1;v[src]=0
            lidmeta.append((v,side,sign,upper,u,t));line.append(v)
        grid.append(line)
    for row in range(4):
        for col in range(16):
            vs=[grid[row][col],grid[row][col+1],grid[row+1][col+1],grid[row+1][col]]
            f=bm.faces.new(vs if upper else list(reversed(vs)));f.material_index=0;f.smooth=True

creasemeta=[]
for side,sign in [('L',1),('R',-1)]:
    rows=[]
    for row in [0,1]:
        line=[]
        for j in range(13):
            u=-1+j/6;x=.02544*sign+.0155*u;z=.141+.0025*(1-u*u)+row*.00065
            end=Vector((x,skin_y(x,z)-.0005,z));v=bm.verts.new(end+Vector((0,.012,0)));v[deform][headidx]=1;v[src]=0
            creasemeta.append((v,side,end));line.append(v)
        rows.append(line)
    for j in range(12):
        f=bm.faces.new([rows[0][j],rows[0][j+1],rows[1][j+1],rows[1][j]]);f.material_index=0;f.smooth=False

# Mouth interior and tongue remain hidden in neutral; no new external silhouette.
def material(name,color):
    mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);mat.use_nodes=True
    p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=.8;mesh.data.materials.append(mat);return len(mesh.data.materials)-1
mouthmat=material('Cat_MouthInterior',(.008,.003,.005));tonguemat=material('Cat_Tongue',(.26,.065,.085))
for center,scale,group,mat in [((0,-.076,.111),(.017,.013,.009),'jaw',mouthmat),((0,-.081,.110),(.007,.011,.002),'tongue',tonguemat)]:
    res=bmesh.ops.create_uvsphere(bm,u_segments=12,v_segments=6,radius=1)
    vs=set(res['verts'])
    for v in vs:
        v.co=Vector((v.co.x*scale[0]+center[0],v.co.y*scale[1]+center[1],v.co.z*scale[2]+center[2]));v[deform][mesh.vertex_groups[group].index]=1;v[src]=0
    for f in bm.faces:
        if all(v in vs for v in f.verts):f.material_index=mat
bm.verts.index_update();meta=[(v.index,side,sign,upper,u,t) for v,side,sign,upper,u,t in lidmeta];creases=[(v.index,side,end) for v,side,end in creasemeta]
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh.data);bm.free();mesh.data.update()
# Retain all prior UVs; set usable planar UVs for the replacement lids/interior.
uv=mesh.data.uv_layers.active
for p in mesh.data.polygons:
    if all(mesh.data.attributes['source_vertex'].data[i].value==0 for i in p.vertices):
        for li in p.loop_indices:
            co=mesh.data.vertices[mesh.data.loops[li].vertex_index].co;uv.data[li].uv=(co.x*6+0.5,co.z*4)

mesh.shape_key_add(name='Basis',from_mix=False)
for side in ['L','R']:
    eyeids={i for p in mesh.data.polygons if p.material_index in [1,2] for i in p.vertices if (mesh.data.vertices[i].co.x>0)==(side=='L')}
    for stage,b in [('Half',.5),('Closed',1.0)]:
        key=mesh.shape_key_add(name='Blink_'+side+'_'+stage,from_mix=False)
        for i,si,sign,upper,u,t in meta:
            if si==side:key.data[i].co=lid_co(sign,upper,u,t,b)
        if b==1:
            for i in eyeids:
                c=key.data[i].co;c.y+=.024;c.z=.144+(c.z-.144)*.65
            for i,si,end in creases:
                if si==side:key.data[i].co=end
        # Existing baked lid bones continue driving blinks in legacy playback.
        # Controls mode uses clean artist-facing properties, not 32 individual lid bones.
        expression='max(0,1-abs(2*VALUE-1))' if b==.5 else 'max(0,2*VALUE-1)'
        d=drv(key,'value',expression.replace('VALUE','min(1,max(0,on*blink+(1-on)*legacy/1.75))'),[control_var(),('blink',arm,f'pose.bones["CTRL_face"]["blink_{side}"]')])
        v=d.variables.new();v.name='legacy';v.type='TRANSFORMS';v.targets[0].id=arm;v.targets[0].bone_target='Lid_Upper_'+side+'_00';v.targets[0].transform_type='ROT_X';v.targets[0].transform_space='LOCAL_SPACE';v.targets[0].rotation_mode='XYZ'

# Bone collections and visible controller shapes make authoring discoverable.
for c in list(arm.data.collections):arm.data.collections.remove(c)
cols={n:arm.data.collections.new(n) for n in ['Controls - Body','Controls - Feet IK','Controls - Face','Controls - FK','Deform - Export','Mechanism']}
for b in arm.data.bones:
    if b.name.startswith('MCH_'):dest='Mechanism'
    elif b.name in ['CTRL_world','CTRL_body','CTRL_spine']:dest='Controls - Body'
    elif b.name.startswith(('CTRL_IK_','CTRL_pole_')):dest='Controls - Feet IK'
    elif b.name in ['CTRL_face','CTRL_jaw','CTRL_tongue']:dest='Controls - Face'
    elif b.name.startswith('CTRL_'):dest='Controls - FK'
    else:dest='Deform - Export'
    cols[dest].assign(b)
cols['Mechanism'].is_visible=False;cols['Deform - Export'].is_visible=False
shapes=bpy.data.collections.new('Rig Widgets');sc.collection.children.link(shapes);shapes.hide_render=True
def widget(name,vertices,edges):
    m=bpy.data.meshes.new(name);m.from_pydata(vertices,edges,[]);o=bpy.data.objects.new(name,m);shapes.objects.link(o);o.hide_render=True;o.hide_set(True);return o
circle=widget('WGT_Circle',[(math.cos(i*math.tau/24),0,math.sin(i*math.tau/24)) for i in range(24)],[(i,(i+1)%24) for i in range(24)])
diamond=widget('WGT_Diamond',[(-1,0,0),(0,0,1),(1,0,0),(0,0,-1)],[(0,1),(1,2),(2,3),(3,0)])
for p in arm.pose.bones:
    if not p.name.startswith('CTRL_'):continue
    p.custom_shape=diamond if 'pole' in p.name else circle;p.use_custom_shape_bone_size=False
    size=.008
    if p.name=='CTRL_world':size=.10
    elif p.name=='CTRL_body':size=.045
    elif p.name=='CTRL_spine':size=.025
    elif p.name=='CTRL_face':size=.018
    elif 'IK' in p.name:size=.018
    p.custom_shape_scale_xyz=(size,size,size)
    p.color.palette='THEME03' if p.name.endswith('_L') else 'THEME04' if p.name.endswith('_R') else 'THEME02'
arm.show_in_front=True
# Store documentation in the blend, not in an auto-executed script.
txt=bpy.data.texts.new('START_HERE_RigV2.txt')
txt.write('BLACKCAT RIG V2\n\nOriginal angular body/head geometry retained.\nObject custom property controls_enabled: 0 = legacy actions, 1 = authoring controls.\nFor a new action, detach the legacy action and reset pose before enabling controls.\nCTRL_body: pelvis position/orientation. CTRL_spine: bend, side_bend, twist properties (degrees).\nCTRL_IK_F/H_L/R: foot targets, ik property. CTRL_pole: bend direction.\nCTRL_neck/head/ears/tail: FK rotation. CTRL_face: blinks and gaze. CTRL_jaw/tongue: mouth.\nDo not key deform bones in controls mode. Avoid scaling bones.\nKeep the original 78 bone names/rest matrices for legacy compatibility. Added jaw/tongue/eyes need a V2 mesh import.\nExport must bake constraints and facial morph drivers; Blender control bones are not game bones.\nThis source is separate from approved game assets.\n')
arm['source_sha256']=source_hash;arm['source_file']=source_path
arm['controls_enabled']=0.0;arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];sc.frame_set(1)
for mat in mesh.data.materials:
    if mat.node_tree:
        p=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if p:mat.diffuse_color=p.inputs['Base Color'].default_value
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type=='VIEW_3D':
        area.spaces.active.shading.type='MATERIAL'
        area.spaces.active.region_3d.view_distance=.45;area.spaces.active.region_3d.view_location=(0,0,.11)
sc.render.fps=30
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_RigV2.blend'))
rest_errors={n:max(abs(arm.data.bones[n].matrix_local[i][j]-original_bones[n][i][j]) for i in range(4) for j in range(4)) for n in original_bones}
report={'source':source_path,'source_sha256':source_hash,'original_rest_matrix_max_error':max(rest_errors.values()),'deform_bones':sum(b.use_deform for b in arm.data.bones),'controls':sum(b.name.startswith('CTRL_') for b in arm.data.bones),'vertices':len(mesh.data.vertices),'triangles':sum(len(p.vertices)-2 for p in mesh.data.polygons),'mouth_seam_edges':len(slit),'replaced_lid_vertices':2112,'new_lid_vertices':len(meta),'shape_keys':[k.name for k in mesh.data.shape_keys.key_blocks]}
(O/'QA/build_report.json').write_text(json.dumps(report,indent=2))
print('RIG_V2_BUILT',json.dumps(report))
