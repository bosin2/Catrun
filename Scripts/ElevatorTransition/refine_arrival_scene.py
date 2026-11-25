"""Revision 2: softer practical light, visible drifting dust, persistent arrival dock.
Run after the native build and author_arrival_look.py; edit only E23 presentation.
"""
import json, random, shutil, time
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/ElevatorTransition'
DEST='/Game/Environment/ElevatorTransition/Presentation'
TAG='CatrunElevatorTransition20261125'
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
AC=u.get_editor_subsystem(u.EditorActorSubsystem)
EA=u.EditorAssetLibrary
ML=u.MaterialEditingLibrary
AT=u.AssetToolsHelpers.get_asset_tools()
SOFT=u.LinearColor(1.0,.90,.77,1)
REPORT={'maps':{},'success':False}

def dust_material():
    path=DEST+'/M_E23_DustSoft'
    if EA.does_asset_exist(path):return EA.load_asset(path)
    m=AT.create_asset('M_E23_DustSoft',DEST,u.Material,u.MaterialFactoryNew())
    m.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
    def node(cls):return ML.create_material_expression(m,cls)
    def link(a,b,p):ML.connect_material_expressions(a,'',b,p)
    color=node(u.MaterialExpressionConstant3Vector);color.constant=u.LinearColor(.65,.58,.46,1)
    ML.connect_material_property(color,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
    fresnel=node(u.MaterialExpressionFresnel)
    soft=node(u.MaterialExpressionOneMinus);link(fresnel,soft,'Input')
    opacity=node(u.MaterialExpressionMultiply);opacity.set_editor_property('ConstB',.48);link(soft,opacity,'A')
    ML.connect_material_property(opacity,'',u.MaterialProperty.MP_OPACITY)
    pos=node(u.MaterialExpressionObjectPositionWS)
    mask=node(u.MaterialExpressionComponentMask)
    for k,v in [('R',True),('G',False),('B',False),('A',False)]:mask.set_editor_property(k,v)
    link(pos,mask,'Input')
    phase=node(u.MaterialExpressionMultiply);phase.set_editor_property('ConstB',.031);link(mask,phase,'A')
    clock=node(u.MaterialExpressionTime)
    speed=node(u.MaterialExpressionMultiply);speed.set_editor_property('ConstB',.10);link(clock,speed,'A')
    add=node(u.MaterialExpressionAdd);link(phase,add,'A');link(speed,add,'B')
    sine=node(u.MaterialExpressionSine);link(add,sine,'Input')
    axis=node(u.MaterialExpressionConstant3Vector);axis.constant=u.LinearColor(11,6,18,1)
    drift=node(u.MaterialExpressionMultiply);link(sine,drift,'A');link(axis,drift,'B')
    ML.connect_material_property(drift,'',u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    ML.recompile_material(m);EA.save_loaded_asset(m)
    return m

def grain(lookup,name,position,radius,mat):
    a=lookup.get(name)
    if not a:
        a=AC.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*position));a.set_actor_label(name)
        a.tags=[TAG];a.set_folder_path('E23/Dust')
    c=a.static_mesh_component;c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(EA.load_asset('/Engine/BasicShapes/Sphere'))
    c.set_collision_profile_name('NoCollision');c.set_editor_property('cast_shadow',False)
    c.set_editor_property('bounds_scale',50.0)
    c.set_material(0,mat)
    a.set_actor_location(u.Vector(*position),False,True);a.set_actor_scale3d(u.Vector(radius,radius,radius))
    return a

def camera(lookup,name,position,target,fov):
    a=lookup.get(name)
    if not a:
        a=AC.spawn_actor_from_class(u.CameraActor,u.Vector(*position));a.set_actor_label(name);a.tags=[TAG]
        a.set_folder_path('E23/Shot')
    a.set_actor_location(u.Vector(*position),False,True)
    a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(a.get_actor_location(),u.Vector(*target)),True)
    a.camera_component.set_field_of_view(fov)
    a.camera_component.set_editor_property('constrain_aspect_ratio',False)
    return a

assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Preserve unsaved edits first'
backup=OUT/'Backups'/('ArrivalRefine_'+time.strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True,exist_ok=True)
for name in ['Stage2','Stage3']:shutil.copy2(ROOT/'Content/Maps'/(name+'.umap'),backup/(name+'.umap'))
mat=dust_material()
for mapname in ['Stage2','Stage3']:
    assert LE.load_level('/Game/Maps/'+mapname)
    lookup={a.get_actor_label():a for a in AC.get_all_level_actors()}
    d=lookup['E23_Director']
    # Less orange, lower exposure contribution: one soft warm practical source.
    light=lookup['E23_Lift_LanternLight'].light_component
    light.set_intensity(35);light.set_light_color(SOFT)
    light.set_editor_property('cast_shadows',False)
    roomdust=[];cabindust=[];rng=random.Random(2302 if mapname=='Stage2' else 2303)
    if mapname=='Stage2':
        for name,intensity in [('E23_Warehouse_OverheadBeam',400),('E23_Warehouse_BeamBounce',8),('E23_Warehouse_PathBounce',12)]:
            light=lookup[name].light_component;light.set_intensity(intensity)
            light.set_light_color(SOFT if not name.endswith('PathBounce') else u.LinearColor(.78,.82,.88,1))
        lookup['E23_Warehouse_OverheadBeam'].light_component.set_editor_property('volumetric_scattering_intensity',2.2)
        haze=lookup['E23_Warehouse_LocalDustHaze'].get_component_by_class(u.LocalFogVolumeComponent)
        haze.set_editor_property('radial_fog_extinction',.22)
        haze.set_editor_property('fog_albedo',u.LinearColor(.69,.66,.60,1))
        for i in range(160):
            # Mix a few readable foreground motes with the fine dust; avoid a
            # uniformly large snow-like field in the distant warehouse shot.
            large=i<48
            position=(rng.uniform(535,895),rng.uniform(-1450,-1250) if large else rng.uniform(-1670,-1250),rng.uniform(45,535))
            size=rng.uniform(.014,.022) if large else rng.uniform(.006,.012)
            roomdust.append(grain(lookup,'E23_Warehouse_Dust'+str(i),position,size,mat))
        hidden=list(d.hide_during_ascent)
        d.hide_during_ascent=hidden+[a for a in roomdust if a not in hidden]
        # The whole tall frame remains readable within the cinematic bars.
        camera(lookup,'E23_Shot_Ascent',(1115,-970,300),(715,-1585,168),70)
    origin=(715,-1590) if mapname=='Stage2' else (150,170)
    for i in range(32):
        large=i<12
        front=1 if mapname=='Stage2' else -1
        y=origin[1]+(front*rng.uniform(40,85) if large else rng.uniform(-70,70))
        size=rng.uniform(.012,.018) if large else rng.uniform(.004,.009)
        cabindust.append(grain(lookup,'E23_CabinDust'+str(i),(origin[0]+rng.uniform(-80,80),y,rng.uniform(30,290)),size,mat))
    moving=list(d.cabin_actors);d.cabin_actors=moving+[a for a in cabindust if a not in moving]
    if mapname=='Stage3':
        lookup['E23_Lift_LanternLight'].light_component.set_editor_property('lighting_channels',u.LightingChannels(channel0=True,channel1=True,channel2=False))
        # Gameplay looks from +X/+Y: the roof alone leaves the cat behind the
        # tall rear/left boards and the corner frame. Only presentation hides;
        # blocking stays on and the platform/far wall remain visibly solid.
        # Crafted arrival shots restore all of these before playback.
        d.cabin_occluders=[lookup['E23_Lift_'+name] for name in ['Ceiling','WallBack','WallLeft','CabinFrame']]
        d.arrival_release_mark.set_actor_location(u.Vector(150,-110,26.2),False,True)
        d.arrival_exit_walk_clip=EA.load_asset('/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_CautiousWalk')
        d.arrival_look_around_clip=EA.load_asset('/Game/Cinematics/ElevatorTransition/Animations/AN_BlackCat_Elevator_ArrivalLookAround')
        assert d.arrival_exit_walk_clip and d.arrival_look_around_clip
        d.arrival_walk_speed=26;d.arrival_walk_clip_play_rate=2
        d.arrival_look_clip_start_seconds=0;d.arrival_camera_blend_seconds=1.1
        d.arrival_exit_camera=camera(lookup,'E23_Shot_StepOff',(240,-90,170),(150,100,45),74)
        response=d.get_component_by_class(u.CatrunElevatorWeightComponent)
        assert response
        response.set_editor_property('moving_actors',list(d.cabin_actors))
        response.set_editor_property('support_actors',[lookup['E23_Lift_Platform']])
        response.set_editor_property('occupancy_volume',d.cabin_volume)
        # Preserve existing title style; native gate holds it until the real blend ends.
        if not any('CatrunStageEntryPresentation' in map(str,a.tags) for a in lookup.values()):
            cls=EA.load_blueprint_class('/Game/UI/Continue/BP_StageEntryPresentation')
            assert cls,'Existing stage title presenter missing'
            a=AC.spawn_actor_from_class(cls,u.Vector(0,0,0));a.set_actor_label('E23_StageEntryPresentation')
            a.tags=[TAG,'CatrunStageEntryPresentation'];a.set_folder_path('E23/Presentation')
    assert LE.save_current_level()
    REPORT['maps'][mapname]={'lantern_intensity':35,'light_linear_color':[1,.90,.77],'warehouse_dust':len(roomdust),'cabin_dust':len(cabindust),'large_warehouse_dust':48 if mapname=='Stage2' else 0,'large_cabin_dust':12}
    del lookup,roomdust,cabindust,moving,d
REPORT.update(success=True,backup=str(backup))
(OUT/'arrival_refine_scene_report.json').write_text(json.dumps(REPORT,indent=2),encoding='utf8')
