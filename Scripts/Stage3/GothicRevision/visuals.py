"""Visual-only puzzle skins and military stone exhibits; root writer only.

Old gameplay primitives remain intact. Separate attached actors deliberately
avoid expanding GetComponentsBoundingBox(true) on gameplay actors.
"""
import json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3GothicRevision20261125'
DEST='/Game/Environment/Stage3/GothicRevision_20261125'
OLD='/Game/Environment/Stage3/FinalGuard/Meshes/'
EA=u.EditorAssetLibrary
ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
PREFIX='S3_GothicVisual_'
REPORT={}

def v(p):return u.Vector(*p)
def xyz(p):return [p.x,p.y,p.z]
def actors():return {a.get_actor_label():a for a in ACT.get_all_level_actors()}
def load(path):
    o=EA.load_asset(path);assert o,path
    return o
def hide_old(a):
    c=a.static_mesh_component
    c.set_visibility(False,False)
    c.set_hidden_in_game(True,False)
    c.set_cast_shadow(False)
def attach(a,parent):
    a.attach_to_actor(parent,u.Name('None'),u.AttachmentRule.KEEP_WORLD,
        u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,False)
def static(label,mesh,loc=(0,0,0),rot=None,scale=(1,1,1),parent=None,material=None):
    a=ACT.spawn_actor_from_class(u.StaticMeshActor,v(loc),rot or u.Rotator())
    assert a,label
    a.set_actor_label(PREFIX+label);a.set_folder_path('Stage3/GothicRevision/Visuals')
    a.tags=[u.Name('Stage3GothicRevision20261125')]
    c=a.static_mesh_component;c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(load(mesh) if isinstance(mesh,str) else mesh)
    c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    c.set_collision_response_to_all_channels(u.CollisionResponseType.ECR_IGNORE)
    c.set_editor_property('can_ever_affect_navigation',False)
    a.set_actor_scale3d(v(scale))
    if material:
        for i in range(c.get_num_materials()):c.set_material(i,material)
    else:calibrate_slots(c)
    if parent:attach(a,parent)
    # Transform/editor reconstruction can restore a StaticMeshActor profile;
    # establish the final no-collision contract after attachment and scaling.
    c.set_collision_profile_name('NoCollision')
    c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    REPORT[label]={'mesh':c.static_mesh.get_path_name(),'location':xyz(a.get_actor_location()),
        'rotation':str(a.get_actor_rotation()),'parent':parent.get_actor_label() if parent else None,
        'collision':str(c.get_collision_enabled()),'materials':[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]}
    return a
def palette():
    return json.loads((ROOT/'Saved/Stage3MaterialCorrection20261125/Materials/application_report.json').read_text())['instances']
def material(role):
    options=[p for p,r in palette().items() if r['calibration'].endswith('__'+role)]
    assert options,role
    options.sort(key=lambda p:('Occlusion' not in p,'DeviceReadability' in p))
    return load(options[0])
def calibrate_slots(c):
    for i in range(c.get_num_materials()):
        m=c.get_material(i)
        if not m or m.get_path_name().startswith(DEST):continue
        name=m.get_name().replace('_Occlusion','')
        candidates=[p for p,r in palette().items() if r['source'].rsplit('.',1)[-1].replace('_Occlusion','')==name]
        if candidates:
            candidates.sort(key=lambda p:('Occlusion' not in p,'DeviceReadability' in p))
            c.set_material(i,load(candidates[0]))

def wedge_mesh():
    """New UE-only stone slab, original meshes and source textures unchanged."""
    path=DEST+'/Meshes/SM_S3_SlopedStoneDisplay'
    if EA.does_asset_exist(path):return load(path)
    source=load('/Engine/BasicShapes/Cube')
    d=u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(source,u.new_object(u.DynamicMesh),
        u.GeometryScriptCopyMeshFromAssetOptions(),u.GeometryScriptMeshReadLOD())[0]
    count=u.GeometryScript_MeshQueries.get_vertex_count(d)
    for i in range(count):
        p,valid=u.GeometryScript_MeshQueries.get_vertex_position(d,i)
        assert valid
        q=u.Vector(p.x*2.44,p.y*.94,10 if p.z<0 else 79+p.y*.94*.46)
        u.GeometryScript_MeshEdits.set_vertex_position(d,i,q)
    m=EA.duplicate_asset(source.get_path_name(),path);assert m
    outcome=u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(d,m,
        u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=True,enable_recompute_tangents=True),
        u.GeometryScriptMeshWriteLOD())
    assert 'FAILURE' not in str(outcome),str(outcome)
    m.set_material(0,material('Pillar'))
    EA.set_metadata_tag(m,'Stage3GothicOwner','20261125')
    assert EA.save_loaded_asset(m)
    return m

def exhibits():
    lookup=actors();wedge=wedge_mesh();stone=material('Pillar');iron=material('BlackIron')
    cube=load('/Engine/BasicShapes/Cube')
    for n in (1,2):
        old=lookup['S3_Display'+str(n)];hide_old(old)
        t=old.get_actor_transform()
        def place(label,m,local,rotation=None,scale=(1,1,1),mat=None):
            point=u.MathLibrary.transform_location(t,v(local))
            # Exhibit actors have authored yaw90; compose local orientation explicitly.
            rot=u.MathLibrary.compose_rotators(rotation or u.Rotator(),old.get_actor_rotation())
            return static('Display'+str(n)+'_'+label,m,xyz(point),rot,scale,old,mat)
        place('StoneWedge',wedge,(0,0,0))
        place('Base',OLD+'SM_S3_Pillar_Base',(0,0,0),scale=(2.56,1.02,.4),mat=stone)
        for x in (-112,112):
            # Slim metal edge straps wrap the stone without making a black face.
            place('Clamp'+str(x),cube,(x,0,80),u.Rotator(roll=24.7),(.045,1.02,.035),iron)
        arrangement=[('Shield',(-48,-30,66),u.Rotator(roll=-65),(.8,.8,.8)),
                     ('Sword',(25,-36,64),u.Rotator(roll=-65),(1,1,1)),
                     ('Axe',(78,-32,66),u.Rotator(roll=-65),(.72,.72,.72)),
                     ('Spear',(-103,31,96),u.Rotator(yaw=-90,roll=-90),(.9,.9,.9))]
        if n==2:arrangement=arrangement[:1]+arrangement[2:]+[('Sword',(-2,-36,64),u.Rotator(roll=-65),(.9,.9,.9))]
        for name,pos,rot,s in arrangement:place(name,OLD+'SM_S3_WeaponSet_'+name,pos,rot,s)
    hide_old(lookup['S3_DisplayJoint'])

def mechanisms():
    imported=json.loads((OUT/'import_report.json').read_text())
    assert imported['success']
    mesh=lambda name:imported['meshes'][name]['path']
    lookup=actors()
    source=Path('C:/Users/whghk/Desktop/CastleKit/Stage3/Mechanisms03_20261125')
    assembly=json.loads((source/'Dock/Assemblies/Dock_Approach.json').read_text())
    # The importer reports bounds in UE coordinates; Blender exports use more
    # than one axis convention. Choose the dock yaw from the actual rear extent.
    bounds=imported['meshes']['SM_S3_DockArch']['bounds']
    rear_sign=1 if abs(bounds[1][1])>abs(bounds[0][1]) else -1
    dock_yaw=180 if rear_sign>0 else 0
    for n in (1,2):
        old=lookup['S3_Statue'+str(n)];hide_old(old)
        static('Weight'+str(n),mesh('SM_S3_GateCounterweight'),xyz(old.get_actor_location()),old.get_actor_rotation(),parent=old)
        shoe=old.get_actor_location()+u.Vector(0,0,.15)
        static('WeightShoe'+str(n),mesh('SM_S3_CounterweightPressureShoe'),xyz(shoe),old.get_actor_rotation(),parent=old)
        plate=lookup['S3_Plate'+str(n)];frame=lookup['S3_Plate'+str(n)+'_Frame']
        hide_old(plate);hide_old(frame)
        static('PressureDeck'+str(n),mesh('SM_S3_DockPressureDeck'),xyz(plate.get_actor_location()),parent=plate)
        static('FloorFrame'+str(n),mesh('SM_S3_DockFloorFrame'),xyz(frame.get_actor_location()),parent=frame)
        base=plate.get_actor_location();base.z=0
        for name,row in assembly.items():
            if name in ('SM_S3_GateCounterweight','SM_S3_CounterweightPressureShoe','SM_S3_DockPressureDeck','SM_S3_DockFloorFrame'):continue
            # Imported rear axis determines both the mesh yaw and translation.
            # FBX Y reflection must also be applied to assembly offsets.
            x,y,z=row['translation_m']
            pos=base+u.Vector(-rear_sign*100*x,-100*y,100*z)
            static('Dock'+str(n)+'_'+name.removeprefix('SM_S3_'),mesh(name),xyz(pos),u.Rotator(yaw=dock_yaw))
    for n in (1,2,3):
        for part in ('Housing','Bolt','Keeper'):
            old=lookup['S3_Lock'+str(n)+'_'+part];hide_old(old)
            static('Lock'+str(n)+'_'+part,mesh('SM_S3_GateLock_'+part),xyz(old.get_actor_location()),old.get_actor_rotation(),parent=old)
    REPORT['dock_orientation']={'import_rear_sign_y':rear_sign,'yaw':dock_yaw,
        'assembly_mapping':'Blender x,y,z -> world -rear_sign*x,-y,z; actual UE local axis compensated'}

def apply(include_mechanisms=True):
    REPORT.clear()
    for a in list(ACT.get_all_level_actors()):
        if a.get_actor_label().startswith(PREFIX):assert ACT.destroy_actor(a)
    exhibits()
    if include_mechanisms:mechanisms()
    (OUT/'visuals_report.json').write_text(json.dumps(REPORT,indent=2),encoding='utf8')
    return REPORT
