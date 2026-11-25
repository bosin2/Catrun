"""Idempotent authoring of the approved E23 corridor, storage room and receiving dock.
Only tagged E23 actors plus the superseded Stage2 exit closure are changed.
Run after import_assets.py and a build exposing CatrunElevatorTransition.
"""
import json,math,random,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/ElevatorTransition'
SRC=Path('C:/Users/whghk/Desktop/CastleKit/Stage2To3_Elevator/Production01_20261125')
DEST='/Game/Environment/ElevatorTransition';TAG='CatrunElevatorTransition20261125'
EA=u.EditorAssetLibrary;ML=u.MaterialEditingLibrary;AT=u.AssetToolsHelpers.get_asset_tools()
AC=u.get_editor_subsystem(u.EditorActorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem);ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
MAN=json.loads((SRC/'manifest_elevator.json').read_text(encoding='utf8'))
ANIM=json.loads((ROOT/'SourceArt/Cinematics/ElevatorCat/Production01_20261125/manifest.json').read_text(encoding='utf8'))['clips']
R={'success':False,'maps':{},'superseded':[]};created=[]

def prop(o,k,v):o.set_editor_property(k,v)
def V(p):return u.Vector(*p)
def spawn(cls,name,p=(0,0,0),yaw=0):
    a=AC.spawn_actor_from_class(cls,V(p),u.Rotator(yaw=yaw));a.set_actor_label('E23_'+name);a.tags=[TAG]
    a.set_folder_path('E23/'+name.split('_')[0]);created.append(a);return a
def mesh(name,asset,p=(0,0,0),yaw=0,scale=(1,1,1),collision=True,local_light=True):
    a=spawn(u.StaticMeshActor,name,p,yaw);c=a.static_mesh_component
    c.set_mobility(u.ComponentMobility.MOVABLE)
    m=EA.load_asset(asset if asset.startswith('/') else DEST+'/Meshes/'+asset);assert m,asset
    c.set_static_mesh(m);a.set_actor_scale3d(V(scale));c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    if local_light:prop(c,'lighting_channels',u.LightingChannels(channel0=False,channel1=True,channel2=False))
    prop(c,'cast_hidden_shadow',True)
    return a
def centered(name,asset,center,yaw=0,scale=(1,1,1),collision=True):
    a=mesh(name,asset,(0,0,0),yaw,scale,collision);c,e=a.get_actor_bounds(False)
    a.set_actor_location(V(center)-c,False,True);return a
def flatmat(name,color,unlit=True):
    path=DEST+'/Presentation/'+name
    if EA.does_asset_exist(path):return EA.load_asset(path)
    m=AT.create_asset(name,DEST+'/Presentation',u.Material,u.MaterialFactoryNew())
    if unlit:prop(m,'shading_model',u.MaterialShadingModel.MSM_UNLIT)
    n=ML.create_material_expression(m,u.MaterialExpressionConstant3Vector);n.constant=u.LinearColor(*color,1)
    ML.connect_material_property(n,'',u.MaterialProperty.MP_EMISSIVE_COLOR if unlit else u.MaterialProperty.MP_BASE_COLOR)
    ML.recompile_material(m);EA.save_loaded_asset(m);return m
def cube(name,center,dimensions,material,collision=True):
    a=centered(name,'/Engine/BasicShapes/Cube',center,scale=tuple(x/100 for x in dimensions),collision=collision)
    a.static_mesh_component.set_material(0,material);return a
def floor(name,x,y,w=200,d=200,z=0):
    a=centered(name,'SM_E23_StoneFloor200',(x+w/2,y-d/2,z-2.5),scale=(w/200,d/200,1));a.tags=[TAG,'SoundFloor'];return a
def wall(name,c,yaw=0):
    a=centered(name,'SM_E23_StoneWall200',c,yaw);a.tags=[TAG,'SoundWall'];return a
def trigger(name,center,extent):
    a=spawn(u.TriggerBox,name,center);c=a.get_component_by_class(u.BoxComponent);c.set_box_extent(V(extent));return a
def camera(name,position,target,fov=65):
    a=spawn(u.CameraActor,name,position);a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(V(position),V(target)),True)
    a.camera_component.set_field_of_view(fov);a.camera_component.set_editor_property('constrain_aspect_ratio',False);return a
def light(name,p,intensity,radius,spot=False):
    a=spawn(u.SpotLight if spot else u.PointLight,name,p);c=a.light_component;c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_intensity(intensity);c.set_light_color(u.LinearColor(1,.90,.77,1));prop(c,'attenuation_radius',radius)
    prop(c,'lighting_channels',u.LightingChannels(channel0=False,channel1=True,channel2=False))
    if spot:
        a.set_actor_rotation(u.Rotator(pitch=-90),True);c.set_inner_cone_angle(22);c.set_outer_cone_angle(37)
    return a
def dustmat():
    path=DEST+'/Presentation/M_E23_DriftingDust'
    m=flatmat('M_E23_DriftingDust',(.65,.39,.16))
    ML.delete_all_material_expressions(m)
    color=ML.create_material_expression(m,u.MaterialExpressionConstant3Vector);color.constant=u.LinearColor(.65,.39,.16,1)
    ML.connect_material_property(color,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
    # World-position phase gives each grain a different slow, bounded drift.
    def node(cls):return ML.create_material_expression(m,cls)
    time=node(u.MaterialExpressionTime);pos=node(u.MaterialExpressionObjectPositionWS)
    mask=node(u.MaterialExpressionComponentMask)
    for k,v in [('R',True),('G',False),('B',False),('A',False)]:prop(mask,k,v)
    ML.connect_material_expressions(pos,'',mask,'Input')
    phase=node(u.MaterialExpressionMultiply);prop(phase,'ConstB',.019);ML.connect_material_expressions(mask,'',phase,'A')
    slow=node(u.MaterialExpressionMultiply);prop(slow,'ConstB',.08);ML.connect_material_expressions(time,'',slow,'A')
    add=node(u.MaterialExpressionAdd);ML.connect_material_expressions(phase,'',add,'A');ML.connect_material_expressions(slow,'',add,'B')
    sine=node(u.MaterialExpressionSine);ML.connect_material_expressions(add,'',sine,'Input')
    axis=node(u.MaterialExpressionConstant3Vector);axis.constant=u.LinearColor(9,4,16,1)
    drift=node(u.MaterialExpressionMultiply);ML.connect_material_expressions(sine,'',drift,'A');ML.connect_material_expressions(axis,'',drift,'B')
    ML.connect_material_property(drift,'',u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    ML.recompile_material(m);EA.save_loaded_asset(m);return m
def assemble(origin,yaw=0):
    result={};moving=[];fixed=[];rot=u.Rotator(yaw=yaw)
    def transform(p):return V(origin)+u.MathLibrary.rotate_angle_axis(V(p),yaw,V((0,0,1)))
    for row in MAN:
        name=row['name'];p=row['pivot'];p=(100*p[0],-100*p[1],100*p[2])
        a=mesh('Lift_'+name.removeprefix('SM_E23_'),name,transform(p).to_tuple(),yaw)
        result[name]=a
        if row['mode'].startswith('cabin'):moving.append(a)
        else:fixed.append(a)
    # Three full height guide sections on both sides, plus the left foot/cap.
    for side in [-1,1]:
        for n in range(3):
            if side==1 and n==0:continue
            p=transform((130*side,0,-70+200*n))
            a=mesh(f'Guide_{side}_{n}','SM_E23_GuideRepeat',p.to_tuple(),yaw+(180 if side<0 else 0));fixed.append(a)
        if side<0:
            for label,z in [('GuideFoot',-70),('GuideCap',530)]:
                a=mesh('Guide_Left_'+label,'SM_E23_'+label,transform((-130,0,z)).to_tuple(),yaw+180);fixed.append(a)
    lamp=light('Lift_LanternLight',transform((65,45,250)).to_tuple(),35,470)
    prop(lamp.light_component,'cast_shadows',False);moving.append(lamp)
    # Lamp bracket is fixed to cabin, swinging body/insert/light pivot separately.
    result['lamp_light']=lamp;result['moving']=moving;result['fixed']=fixed
    return result
def wire(origin,yaw,parts,zones,occluders,warehouse_camera,hide_ascent,arrival=False):
    cls=getattr(u,'CatrunElevatorTransition',None)
    assert cls,'Compile CatrunElevatorTransition before map authoring'
    director=spawn(cls,'Director',origin)
    catmark=spawn(u.TargetPoint,'Mark_Cat',(origin[0],origin[1],origin[2]+26.2),yaw+90)
    pivot=spawn(u.TargetPoint,'Mark_CabinPivot',origin,yaw)
    if not arrival:
        front=camera('Shot_Ring',(origin[0]+160,origin[1]+290,origin[2]+120),(origin[0],origin[1]+30,origin[2]+65),58)
        peek=camera('Shot_Below',(origin[0]+20,origin[1]+240,origin[2]-32),(origin[0],origin[1]+65,origin[2]+260),66)
        inside=camera('Shot_Ascent',(origin[0]+320,origin[1]+500,origin[2]+260),(origin[0],origin[1]+5,origin[2]+150),64)
    else:
        front=camera('Shot_Arrival',(origin[0]-110,origin[1]-145,120),(origin[0],origin[1],50),64)
        peek=front;inside=front
    for key,val in {'arrival_side':arrival,'corridor_volume':zones.get('corridor'),'entry_volume':zones.get('entry'),
        'cabin_volume':zones['cabin'],'warehouse_volume':zones.get('warehouse'),'warehouse_camera':warehouse_camera,
        'cat_mark':catmark,'cabin_pivot':pivot,'front_camera':front,'peek_camera':peek,'cabin_camera':inside,
        'cabin_actors':parts['moving'],'control_pull_actors':[parts['SM_E23_ControlChain'],parts['SM_E23_ControlRing']],
        'chain_actor':parts['SM_E23_ControlRing'],'lantern_actor':parts['SM_E23_LanternBody'],
        'lantern_actors':[parts['SM_E23_LanternBody'],parts['SM_E23_LanternEmission'],parts['lamp_light']],
        'corridor_occluders':occluders,'cabin_occluders':[parts['SM_E23_Ceiling']],
        'hide_during_ascent':hide_ascent,'use_local_elevator_lighting':True,
        'departure_clips':[EA.load_asset('/Game/Cinematics/ElevatorTransition/Animations/'+x['action']) for x in ANIM[:7]],
        'arrival_clips':[EA.load_asset('/Game/Cinematics/ElevatorTransition/Animations/'+x['action']) for x in ANIM[7:]]}.items():prop(director,key,val)
    for key,id in [('pull_sound','chain_ring_pull'),('start_sound','lift_departure'),('dock_latch_sound','dock_latch')]:
        p='/Game/Audio/CatAudioDirector/CAD_20261125_053416_46364406/SW_'+id
        if EA.does_asset_exist(p):prop(director,key,EA.load_asset(p))
    if arrival:prop(director,'arrival_release_mark',spawn(u.TargetPoint,'Mark_Return',(150,-110,26.2),-90))
    return director

def stage2():
    origin=(715,-1590,0);actors={a.get_actor_label():a for a in AC.get_all_level_actors()};corridor=[]
    for name,a in actors.items():
        if name=='Flow_Stage2Complete' or name=='S2_ExitCorridor_DarkEnd' or name.startswith('S2_ExitCorridor_BlackMist'):
            a.set_actor_enable_collision(False);a.set_actor_hidden_in_game(True);a.set_actor_tick_enabled(False)
            a.tags=list(a.tags)+(['E23_Superseded'] if 'E23_Superseded' not in map(str,a.tags) else [])
            # Editor also shows the opened route; do not destroy old references.
            if isinstance(a,u.StaticMeshActor):a.static_mesh_component.set_visibility(False)
            R['superseded'].append(name)
        elif name.startswith('S2_ExitCorridor_') and any(x in name for x in ['WallEast','Ceiling','EastOuterShade']):
            corridor.append(a)
            c=a.get_component_by_class(u.PrimitiveComponent)
            if c:prop(c,'cast_hidden_shadow',True)
        if name.startswith('S2_ExitCorridor_Floor'):
            prop(a.static_mesh_component,'lighting_channels',u.LightingChannels(channel0=False,channel1=True,channel2=False))
    floor('Corridor_Floor3',615,-415)
    wall('Corridor_West3',(600,-515,150),90)
    corridor += [wall('Corridor_East3',(830,-515,150),90)]
    corridor += [cube('Corridor_Roof3',(715,-515,300),(260,200,20),BLACK)]
    # Black outside surfaces keep the cutaway legible, while floor and pawn remain opaque.
    for x in [410,1020]:cube('Corridor_OuterDark_'+str(x),(x,-315,-8),(380,600,5),BLACK,False)
    for i in range(3):light('Corridor_ReadLight'+str(i),(715,-140-195*i,210),75,240)
    start=len(created)
    for ix in range(5):
        for iy in range(6):
            if ix==2 and iy>=4:continue
            floor(f'Warehouse_Floor_{ix}_{iy}',215+200*ix,-615-200*iy)
    floor('Warehouse_ThresholdApproach',615,-1415,200,72)
    cube('Warehouse_Pit',(715,-1590,-78),(250,250,10),BLACK)
    for level in range(2):
        z=150+300*level
        for i in range(6):
            wall(f'Warehouse_WallWest_{level}_{i}',(200,-715-200*i,z),90)
            wall(f'Warehouse_WallEast_{level}_{i}',(1230,-715-200*i,z),90)
        for i in range(5):
            wall(f'Warehouse_WallBack_{level}_{i}',(315+200*i,-1830,z))
            if i!=2:wall(f'Warehouse_WallEntry_{level}_{i}',(315+200*i,-600,z))
    # Entrance lintel keeps the room enclosed above its 300 cm doorway.
    wall('Warehouse_EntryLintel',(715,-600,450))
    roof=cube('Warehouse_ShadowRoof',(715,-1215,625),(1060,1260,30),BLACK)
    roof.set_actor_hidden_in_game(True)
    # All room architecture remains opaque during the walking view.
    boxposes=[(330,-760,0,13,False),(425,-930,0,-9,True),(330,-1120,0,7,False),(380,-1260,0,-5,True),
              (1090,-780,0,-11,False),(1000,-940,0,8,True),(1110,-1100,0,12,False),(1040,-1275,0,-15,True),
              (385,-1660,0,-8,False),(1030,-1670,0,5,False),(395,-1660,120,8,True),(1045,-1675,120,-12,True)]
    for i,(x,y,z,yaw,small) in enumerate(boxposes):
        a=mesh('Warehouse_Crate'+str(i),'SM_E23_CrateSmall' if small else 'SM_E23_CrateLarge',(x,y,z),yaw)
    # The pointed recess frames the tall timber mechanism without boxing its open front.
    for n,p in [('PortalJambLeft',(-180,-135,0)),('PortalJambRight',(180,-135,0)),('PortalPointedHead',(0,-135,370))]:
        mesh('Warehouse_'+n,'SM_E23_'+n,(origin[0]+p[0],origin[1]+p[1],p[2]))
    beam=light('Warehouse_OverheadBeam',(715,-1470,570),400,1100,True)
    fog=spawn(u.ExponentialHeightFog,'Warehouse_VolumetricMedium',(715,-1470,0))
    fc=fog.get_component_by_class(u.ExponentialHeightFogComponent)
    prop(fc,'fog_density',0.0);prop(fc,'bEnableVolumetricFog',True);prop(fc,'volumetric_fog_distance',3500.0)
    localfog=spawn(u.LocalFogVolume,'Warehouse_LocalDustHaze',(715,-1470,280))
    localfog.set_actor_scale3d(V((.36,.36,.65)))
    lc=localfog.get_component_by_class(u.LocalFogVolumeComponent)
    prop(lc,'radial_fog_extinction',.15);prop(lc,'height_fog_extinction',0.0)
    prop(lc,'fog_albedo',u.LinearColor(.65,.55,.4,1))
    # Dim bounce comes from the same shaft footprint, no decorative extra fixture.
    bounce=light('Warehouse_BeamBounce',(715,-1450,105),8,850)
    light('Warehouse_PathBounce',(715,-920,190),12,650).light_component.set_light_color(u.LinearColor(.78,.82,.88,1))
    rng=random.Random(23);dm=dustmat()
    for i in range(55):
        a=mesh('Warehouse_Dust'+str(i),'/Engine/BasicShapes/Sphere',(rng.uniform(565,865),rng.uniform(-1620,-1280),rng.uniform(40,535)),scale=(.004,.004,.004),collision=False)
        a.static_mesh_component.set_material(0,dm);prop(a.static_mesh_component,'cast_shadow',False)
    room=list(created[start:])
    # Permanent black surfaces around the shaft are outside the walkable space.
    cube('Shaft_BlackBack',(715,-2020,700),(2000,20,2000),BLACK,False)
    cube('Shaft_BlackWest',(-400,-1500,700),(20,2000,2000),BLACK,False)
    parts=assemble(origin)
    zones={'corridor':trigger('Zone_Corridor',(715,-320,90),(100,305,120)),
           'entry':trigger('Zone_Protection',(715,-1220,100),(500,605,160)),
           'warehouse':trigger('Zone_Warehouse',(715,-1220,100),(500,605,160)),
           'cabin':trigger('Zone_Cabin',(715,-1580,90),(91,83,115))}
    cam=camera('View_Warehouse',(715,-680,1100),(715,-1090,60),86)
    wire(origin,0,parts,zones,corridor,cam,room+parts['fixed'])

def stage3():
    origin=(150,170,0)
    # Open only the existing start-end closure; its old actors remain recoverable.
    old={a.get_actor_label():a for a in AC.get_all_level_actors()}
    for name,a in old.items():
        if name in ('S3_Wall_0001','S3_Wall_0002') or name.startswith(('S3_Gothic_Wall1_','S3_Gothic_Wall2_')):
            a.set_actor_enable_collision(False);a.set_actor_hidden_in_game(True)
            c=a.get_component_by_class(u.StaticMeshComponent)
            if c:c.set_visibility(False)
            if 'E23_Superseded' not in map(str,a.tags):a.tags=list(a.tags)+['E23_Superseded']
            R['superseded'].append(name)
    for i,x in enumerate([25,275]):
        a=centered('Dock_ExistingDoorJamb'+str(i),'/Game/Environment/Stage3/FinalGuard/Meshes/SM_S3_Wall_50',(x,-15,150))
        c=old['S3_Wall_0001'].static_mesh_component
        for slot in range(c.get_num_materials()):a.static_mesh_component.set_material(slot,c.get_material(slot))
    # Existing start is unchanged. New dock joins its north edge through a short threshold.
    floor('Dock_Approach',(50),70,200,70)
    floor('Dock_Left',-50,320,100,320);floor('Dock_Right',250,320,100,320)
    for i in range(2):
        wall('Dock_West'+str(i),(-65,70+200*i,150),90)
        wall('Dock_East'+str(i),(365,70+200*i,150),90)
        wall('Dock_Back'+str(i),(50+200*i,340,150))
    cube('Dock_Pit',(150,170,-78),(240,220,10),BLACK)
    parts=assemble(origin,180)
    zones={'cabin':trigger('Zone_Cabin',(150,170,90),(90,85,115))}
    wire(origin,180,parts,zones,[],None,[],True)

try:
    assert not ED.get_game_world(),'Stop PIE first'
    assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Unsaved map edits'
    BLACK=flatmat('M_E23_AbsoluteBlack',(0,0,0))
    for name,fn in [('Stage2',stage2),('Stage3',stage3)]:
        assert LE.load_level('/Game/Maps/'+name)
        for a in AC.get_all_level_actors():
            if TAG in map(str,a.tags):AC.destroy_actor(a)
        created=[];fn()
        R['maps'][name]={'actors':len(created),'labels':[a.get_actor_label() for a in created]}
        assert LE.save_current_level()
        created=[]
    R['success']=True
except Exception:
    R['error']=traceback.format_exc();print(R['error']);raise
finally:
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'author_report.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf8')
