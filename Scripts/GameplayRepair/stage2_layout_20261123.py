"""Apply the November Stage2 layout to the loaded Stage2 or SoundTest_Stage2 level.

The caller owns level loading, saving and independent cold/runtime verification.
Use apply_loaded() in the editor, or audit_loaded() without modifying the level.
"""
import json
from pathlib import Path
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/LevelFlow'))
from setup_playability import remove_reset_buttons, update_practice_hint

TAG = 'CatrunStage2Layout20261123'
OUT = ROOT / 'Saved/StageRevision20261123'
MAPS = ('Stage2', 'SoundTest_Stage2')
AS = u.EditorAssetLibrary
SUB = u.get_editor_subsystem(u.EditorActorSubsystem)
STONE = '/Game/Environment/Shared/Castle/Architecture/Meshes/SM_StoneWall_Partition_L120_H300_T030'
LANDING = '/Game/Environment/Shared/Castle/Architecture/Stairs/Meshes/SM_StairLanding_Stone_260x200'
PORTAL = '/Game/Environment/Stage2/Architecture/PortalFrame'
P = 'S2_Layout_'
PATROL = ((2187.5, 2537.5, 100.), (2187.5, 2887.5, 100.))
ROOM_TWO_LOOK_RATE = .45
A_STATUE = (2075., 2775.)
A_PLATE = (2075., 2555.)
C_STATUE = (1575., 3600.)
CANDLES = {'Candle_01': (1105., 1505., 65.), 'Candle_02': (1660., 2155., -115.)}


def xyz(v):
    return [v.x, v.y, v.z]


def level():
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Requires an editor world outside play'
    world = ed.get_editor_world()
    name = world.get_name()
    assert name in MAPS and world.get_path_name() == f'/Game/Maps/{name}.{name}'
    items = list(SUB.get_all_level_actors())
    actors = {a.get_actor_label(): a for a in items}
    assert len(items) == len(actors), 'Duplicate actor labels'
    return world, actors


def bounds(actor):
    center, half = actor.get_actor_bounds(False)
    return xyz(center-half), xyz(center+half)


def pose(actor, position, yaw=None):
    actor.modify()
    if yaw is not None:
        actor.set_actor_rotation(u.Rotator(yaw=yaw), True)
    actor.set_actor_location(u.Vector(*position), False, True)


def move_xy(actor, x, y):
    pose(actor, (x, y, actor.get_actor_location().z))


def fit(actor, low, high):
    """Fit the existing mesh, respecting its actual pivot and cardinal placement."""
    lo, hi = u.Vector(*low), u.Vector(*high)
    assert (hi.x > lo.x and hi.y > lo.y and hi.z > lo.z), actor.get_actor_label()
    center, half = actor.get_actor_bounds(False)
    desired = (hi-lo)*.5
    ratios = [desired.x/half.x, desired.y/half.y, desired.z/half.z]
    rotation = actor.get_actor_rotation()
    assert abs(rotation.roll)<.01 and abs(rotation.pitch)<.01 and abs(rotation.yaw/90-round(rotation.yaw/90))<.001
    if round(rotation.yaw/90) % 2:
        ratios[0],ratios[1] = ratios[1],ratios[0]
    s = actor.get_actor_scale3d()
    actor.modify()
    actor.set_actor_scale3d(u.Vector(s.x*ratios[0],s.y*ratios[1],s.z*ratios[2]))
    center = actor.get_actor_bounds(False)[0]
    pose(actor, xyz(actor.get_actor_location()+(lo+hi)*.5-center))
    measured = bounds(actor)
    assert max(abs(a-b) for actual, expected in zip(measured,(low, high)) for a,b in zip(actual,expected))<.15, (actor.get_actor_label(),measured,low,high)


def fit_xy(actor, x0, y0, x1, y1):
    lo, hi = bounds(actor)
    fit(actor, (x0,y0,lo[2]),(x1,y1,hi[2]))


def owned(actors, suffix, cls):
    label = P+suffix
    actor = actors.get(label)
    if actor:
        assert isinstance(actor,cls) and TAG in map(str,actor.tags), label
    else:
        actor = SUB.spawn_actor_from_class(cls,u.Vector(),u.Rotator())
        assert actor, label
        actor.set_actor_label(label)
        actor.set_folder_path('Gameplay/Stage2Layout')
        actor.set_editor_property('tags',[u.Name(TAG)])
        actors[label]=actor
    return actor


def mesh_piece(actors, suffix, source, tags=(), profile='BlockAll', yaw=0.):
    actor = owned(actors,suffix,u.StaticMeshActor)
    component = actor.static_mesh_component
    mesh = AS.load_asset(source) if isinstance(source,str) else source.static_mesh_component.static_mesh
    assert mesh, source
    component.modify()
    component.set_static_mesh(mesh)
    if not isinstance(source,str):
        template = source.static_mesh_component
        for i in range(template.get_num_materials()):
            component.set_material(i,template.get_material(i))
    component.set_collision_profile_name(profile)
    component.set_editor_property('generate_overlap_events',False)
    actor.set_actor_enable_collision(profile!='NoCollision')
    actor.set_editor_property('tags',[u.Name(t) for t in (TAG,*tags)])
    pose(actor, (0.,0.,0.),yaw)
    actor.set_actor_scale3d(u.Vector(1.,1.,1.))
    return actor


def part(actors, name, source, low, high, tags=('SoundWall',), yaw=0.):
    actor = mesh_piece(actors,name,source,tags,yaw=yaw)
    fit(actor,low,high)
    return actor


def room_two(actors):
    # Move the west and south edges inward. Keep the gate and cat-hole on the
    # shared northern seam and retain a short floor-supported western hall throat.
    for i in range(15):
        row,col=divmod(i,5)
        x0=1900.+col*200.*(750./900.)
        x1=min(2650.,1900.+(col+1)*200.*(750./900.))
        y0=2460.+row*500./3.
        y1=2460.+(row+1)*500./3.
        fit_xy(actors[f'SM_Stage2_Floor_r2_{i+1:03d}'],x0,y0,x1,y1)
    base=actors['SM_Stage2_Foundation_10']
    fit_xy(base,1900.,2460.,2650.,2960.)
    floor=actors['SM_Stage2_Floor_r2_001']
    lo,hi=bounds(floor)
    part(actors,'Room2_ThroatFloor',floor,(1750.,2610.,lo[2]),(1900.,2830.,hi[2]),('SoundFloor',))
    lo,hi=bounds(base)
    part(actors,'Room2_ThroatFoundation',base,(1750.,2610.,lo[2]),(1900.,2830.,hi[2]),())
    outerwall=actors['SM_Stage2_Wall_092']
    for suffix, low, high, yaw in (
        ('Room2_WestNorth',(1885,2475,0),(1915,2610,300),90),
        ('Room2_WestSouth',(1885,2830,0),(1915,2945,300),90),
        ('Room2_ThroatNorth',(1765,2595,0),(1915,2625,300),0),
        ('Room2_ThroatSouth',(1765,2815,0),(1915,2845,300),0)):
        part(actors,suffix,outerwall,low,high,yaw=yaw)
    fit_xy(actors['SM_Stage2_WallRun_035'],1885.,2945.,2200.,2975.)
    fit_xy(actors['SM_Stage2_WallRun_036'],2200.,2945.,2665.,2975.)
    fit_xy(actors['SM_Stage2_WallRun_087'],2635.,2475.,2665.,2945.)
    # Move attached light children to measured world positions after their parent.
    for label,pos in (
        ('S2_Torch_Room2_01',(1970.,2944.5,200.)),
        ('Light_Stage2_Room2_01',(1970.,2904.5,240.)),
        ('S2_Torch_Room2_01_Flame',(1970.,2921.5,227.))):
        pose(actors[label],pos)
    move_xy(actors['S2_Prop_Statue_A'],*A_STATUE)
    for suffix in ('Frame','Plate'):
        move_xy(actors['S2_Prop_Plate_A_'+suffix],*A_PLATE)
    guard=actors['Armor_02']
    points=[]
    for i,pos in enumerate(PATROL):
        marker=owned(actors,'Armor02_Patrol_'+str(i+1),u.CatrunPatrolPoint)
        pose(marker,pos)
        marker.set_editor_property('PauseSeconds',.15)
        points.append(marker)
    pose(guard,(PATROL[0][0],(PATROL[0][1]+PATROL[1][1])*.5,PATROL[0][2]),-90.)
    guard.set_editor_property('PatrolPoints',points)
    guard.set_editor_property('bPatrolLoop',False)
    # The 3 s arrival search lasts 6.667 s here, up from 3.75 s at the BP's .8 rate.
    # This instance uses the animation-backed search for every sound it investigates.
    guard.set_editor_property('ArrivalLookPlayRate',ROOM_TWO_LOOK_RATE)


def maintain_basket_exit(actors):
    basket=actors['S2_Basket_Room2']
    body=actors['S2_Basket_Room2_Body']
    cloth=actors['S2_Basket_Room2_Cloth']
    cat=actors['BP_Cat_Player']
    cap=cat.get_component_by_class(u.CapsuleComponent)
    entry=cat.get_component_by_class(u.CatrunBasketInteractionComponent)
    front=basket.get_editor_property('OpenDirectionLocal')
    direction=basket.get_actor_forward_vector()*front.x+basket.get_actor_right_vector()*front.y
    origin=basket.get_actor_location()+u.Vector(0.,0.,cap.get_scaled_capsule_half_height()+2.)
    # The game allows the front and neighboring sectors. A clear centerline is
    # independently required for approaching the basket from its authored front.
    distance=max(100.,entry.get_editor_property('ExitDistance')) if entry else 100.
    def obstruction(start):
        hit=u.SystemLibrary.capsule_trace_single_by_profile(
            basket,start,start+direction*distance,cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height(),
            cap.get_collision_profile_name(),False,[cat,basket,body,cloth],u.DrawDebugTrace.NONE,False)
        return hit.to_dict()['hit_actor'] if hit else None
    blocker=obstruction(origin)
    if blocker in (actors['SM_Stage2_WallRun_035'],actors['SM_Stage2_WallRun_036']):
        for item in (basket,body,cloth):
            move_xy(item,2390.,2820.)
        shifted=basket.get_actor_location()+u.Vector(0.,0.,cap.get_scaled_capsule_half_height()+2.)
        assert obstruction(shifted) is None, 'Room2 basket approach still blocked'
    else:
        assert blocker is None, ('Room2 basket approach unexpectedly blocked',blocker)

def room_three(actors):
    grate=actors.get('S2_Gate_03_Bars')
    if grate:
        assert isinstance(grate,u.StaticMeshActor)
        assert SUB.destroy_actor(grate)
        del actors['S2_Gate_03_Bars']
    for suffix in ('092','093'):
        move_xy(actors['SM_Stage2_Wall_'+suffix],1975.,1665.)
    move_xy(actors['Candle_03'],2530.,1590.)


def room_four_sweep(actors):
    settings=actors['SoundGridManager'].get_editor_property('Settings')
    total=settings.get_editor_property('CandleTotalAngle')
    cone=settings.get_editor_property('CandleConeAngle')
    return .75*max(0.,(total-cone)*.5)


def room_four(actors):
    # Four dressed masonry sides on a stepped plinth enclose a solid central
    # obstacle. The two mounted rune settings face the long approach corridors.
    cx=1400.
    part(actors,'Room4_AltarFoot',LANDING,(1250,1700,0),(1550,1980,24))
    wall=actors['SM_Stage2_Wall_092']
    for suffix,lo,hi,yaw in (
        ('North',(1260,1710,24),(1540,1740,157),0),('South',(1260,1940,24),(1540,1970,157),180),
        ('West',(1260,1740,24),(1290,1940,157),90),('East',(1510,1740,24),(1540,1940,157),-90)):
        part(actors,'Room4_Altar'+suffix,wall,lo,hi,yaw=yaw)
    part(actors,'Room4_AltarCap',LANDING,(1254,1704,157),(1546,1976,175))
    for end,y,yaw,offset in (('North',1710.,180.,-16.),('South',1970.,0.,16.)):
        for suffix,offset_y in (('Frame',0.),('Core',offset)):
            template=actors['S2_Prop_Arcane_Room4_West_'+suffix]
            actor=mesh_piece(actors,'Room4_AltarRune'+end+'_'+suffix,template,profile='NoCollision',yaw=yaw)
            pose(actor,(cx,y+offset_y,100.),yaw)
    sweep=room_four_sweep(actors)
    for label,(x,y,yaw) in CANDLES.items():
        candle=actors[label]
        pose(candle,(x,y,candle.get_actor_location().z),yaw)
        candle.set_editor_property('SweepHalfAngleOverride',sweep)


def entrance(actors):
    move_xy(actors['S2_Prop_Statue_C'],*C_STATUE)
    frame=mesh_piece(actors,'EntrancePortalFrame',PORTAL+'/Meshes/SM_PortalFrame_Stone',('SoundWall',))
    frame.static_mesh_component.set_material(0,AS.load_asset(PORTAL+'/Materials/MI_PortalFrame_Stone'))
    pose(frame,(1375.,3980.75,0.))
    frame.set_actor_scale3d(u.Vector(.9375,.9375,.9375))
    part(actors,'EntrancePortalBacking',STONE,(1292.,3997.,0.),(1458.,4023.,244.),yaw=90.)


def audit_loaded():
    world,actors=level()
    owned_actors=[a for a in actors.values() if TAG in map(str,a.tags)]
    assert not any(isinstance(a,u.CatrunPuzzleReset) for a in actors.values())
    assert 'S2_Gate_03_Bars' not in actors and 'S2_Gate_03_Frame' in actors
    for face,face_y,sign in (('North',1710.,-1.),('South',1970.,1.)):
        frame=actors[P+'Room4_AltarRune'+face+'_Frame']
        core=actors[P+'Room4_AltarRune'+face+'_Core']
        fmin,fmax=bounds(frame)
        cmin,cmax=bounds(core)
        frame_depth=sorted((sign*(fmin[1]-face_y),sign*(fmax[1]-face_y)))
        core_depth=sorted((sign*(cmin[1]-face_y),sign*(cmax[1]-face_y)))
        assert abs(frame_depth[0])<.15 and frame_depth[1]>23., (face,frame_depth)
        assert 0.<core_depth[0]<core_depth[1]<=frame_depth[1]+.15, (face,core_depth,frame_depth)
        assert all(fmin[i]<=cmin[i]<=cmax[i]<=fmax[i] for i in (0,2)),(face,fmin,cmin,cmax,fmax)
    puzzle=actors['S2_StatuePuzzle']
    links={str(k.get_editor_property('PuzzleId')):k for k in puzzle.get_editor_property('Links')}
    for key,gate in zip('ABC',('02','05','11')):
        link=links[key]
        assert link.get_editor_property('Statue')==actors['S2_Prop_Statue_'+key]
        assert link.get_editor_property('Plate')==actors['S2_Prop_Plate_'+key+'_Plate']
        assert link.get_editor_property('Gate')==actors['S2_Gate_'+gate+'_Bars']
    guard=actors['Armor_02']
    assert [xyz(a.get_actor_location()) for a in guard.get_editor_property('PatrolPoints')]==[list(p) for p in PATROL]
    look_rate=guard.get_editor_property('ArrivalLookPlayRate')
    assert abs(look_rate-ROOM_TWO_LOOK_RATE)<.0001, ('Armor_02 ArrivalLookPlayRate',look_rate)
    for label in CANDLES:
        assert actors[label].get_editor_property('SweepHalfAngleOverride')==room_four_sweep(actors)
    assert actors['Candle_03'].get_editor_property('SweepHalfAngleOverride')<0.
    for key,target in (('S2_Prop_Statue_A',A_STATUE),('S2_Prop_Plate_A_Plate',A_PLATE),('S2_Prop_Plate_A_Frame',A_PLATE),('S2_Prop_Statue_C',C_STATUE)):
        assert tuple(xyz(actors[key].get_actor_location())[:2])==target
    return {'map':world.get_path_name(),'new':{a.get_actor_label():{'xyz':xyz(a.get_actor_location()),'bounds':bounds(a)} for a in owned_actors},
            'patrol':PATROL,'room2_armor_arrival_look_rate':look_rate,
            'C_route':[C_STATUE,(1195.,3600.),(1195.,3430.)],'A_route':[A_STATUE,A_PLATE]}


def apply_loaded():
    world,actors=level()
    # Fail before touching the world if an old editor binary is still loaded.
    actors['Candle_01'].get_editor_property('SweepHalfAngleOverride')
    for name in ('S2_Prop_Plate_A_Frame','S2_Prop_Plate_A_Plate','S2_Gate_07_Bars','S2_Gate_04_Frame'):
        assert name in actors,name
    room_two(actors)
    maintain_basket_exit(actors)
    room_three(actors)
    room_four(actors)
    entrance(actors)
    update_practice_hint(actors.values())
    removed=remove_reset_buttons(actors.values(),SUB)
    actors['SoundGridManager'].build_grid()
    OUT.mkdir(exist_ok=True,parents=True)
    name=world.get_name()
    (OUT/(name+'-task3-postgrid.json')).write_text(actors['SoundGridManager'].call_method('ExportBakedGridSnapshot'),encoding='utf8')
    result=audit_loaded()
    result['removed_buttons']=removed
    (OUT/(name+'-task3-apply.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    return result
