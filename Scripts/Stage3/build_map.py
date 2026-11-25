"""Author Stage3 from recovered room dimensions without altering earlier levels."""
import sys, json, math, traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3'))
import layout as L
OUT=ROOT/'Saved/Stage3Integration20261125'
DEST='/Game/Environment/Stage3/FinalGuard'
EA=u.EditorAssetLibrary; ML=u.MaterialEditingLibrary
ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem)
REPORT={'rooms':L.ROOMS,'connectors':L.CONNECTORS,'actors':{},'portals':{},'closures':{}}
IM=json.loads((OUT/'import_report.json').read_text())
assert IM.get('success')
SERIAL=0

def load(path):
    a=u.load_object(None,path if '.' in path.rsplit('/',1)[-1] else path+'.'+path.rsplit('/',1)[-1]); assert a,path; return a
def mesh(name): return load(IM['meshes'][name]['path'])
def xyz(v): return [v.x,v.y,v.z]
def persist(): (OUT/'map_report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf8')
def spawn(cls,label,loc=(0,0,0),yaw=0,folder='Gameplay'):
    a=ACT.spawn_actor_from_class(cls,u.Vector(*loc),u.Rotator(yaw=yaw));assert a,label
    a.set_actor_location(u.Vector(*loc),False,True)
    a.set_actor_label('S3_'+label);a.set_folder_path('Stage3/'+folder);a.tags=[u.Name('CatrunStage3_20261125')]
    return a
def bp(path,label,loc=(0,0,0),yaw=0):return spawn(EA.load_blueprint_class(path),label,loc,yaw)
def static(label,m,loc=(0,0,0),yaw=0,folder='Architecture',tags=(),movable=False,collision=True,occlusion=False):
    m=mesh(m) if isinstance(m,str) else m
    a=spawn(u.StaticMeshActor,label,loc,yaw,folder)
    c=a.static_mesh_component
    if movable:c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(m); c.set_collision_profile_name('BlockAllDynamic' if movable else 'BlockAll')
    if not collision:c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    a.tags=list(a.tags)+[u.Name(t) for t in tags]
    if occlusion:
        for i in range(c.get_num_materials()):c.set_material(i,fade(c.get_material(i)))
    REPORT['actors'][label]={'mesh':m.get_path_name(),'location':list(loc),'yaw':yaw,'tags':list(tags)}
    return a
def fade(original):
    path=DEST+'/Materials/'+original.get_name()+'_Occlusion'
    if EA.does_asset_exist(path):
        existing=load(path)
        if EA.get_metadata_tag(existing,'Stage3OcclusionReady')=='1':return existing
        assert path.startswith(DEST+'/Materials/') and path.endswith('_Occlusion')
        assert EA.delete_asset(path)
    m=EA.duplicate_asset(original.get_path_name(),path)
    m.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED)
    m.set_editor_property('opacity_mask_clip_value',.333)
    fn=ML.create_material_expression(m,u.MaterialExpressionMaterialFunctionCall,-400,800)
    assert fn.set_material_function(load('/Game/Systems/Camera/Occlusion/Materials/MF_WallOcclusion'))
    lerp=ML.create_material_expression(m,u.MaterialExpressionLinearInterpolate,-100,800)
    lerp.set_editor_property('ConstA',1.);lerp.set_editor_property('ConstB',.04)
    assert ML.connect_material_expressions(fn,'Result',lerp,'Alpha')
    dither=ML.create_material_expression(m,u.MaterialExpressionMaterialFunctionCall,100,800)
    assert dither.set_material_function(load('/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA'))
    assert ML.connect_material_expressions(lerp,'',dither,'Alpha Threshold')
    assert ML.connect_material_property(dither,'Result',u.MaterialProperty.MP_OPACITY_MASK)
    ML.recompile_material(m);EA.set_metadata_tag(m,'Stage3OcclusionReady','1');EA.save_loaded_asset(m);return m
def at_min(label,m,minimum,yaw=0,**kw):
    a=static(label,m,(0,0,0),yaw,**kw)
    center,extent=a.get_actor_bounds(False)
    a.set_actor_location(u.Vector(*minimum)-(center-extent),False,True)
    REPORT['actors'][label]['location']=xyz(a.get_actor_location())
    return a

def device_readability(original):
    """Low housings need a head-sized fade area, not a tall-wall plane test."""
    source=original.get_base_material() if isinstance(original,u.MaterialInstanceConstant) else original
    base_name=source.get_name().replace('_DeviceReadability','').replace('_Occlusion','')
    path=DEST+'/Materials/'+base_name+'_DeviceReadability'
    if EA.does_asset_exist(path):
        existing=load(path)
        if EA.get_metadata_tag(existing,'Stage3DeviceReadabilityReady')=='1':return existing
        assert path.startswith(DEST+'/Materials/') and path.endswith('_DeviceReadability')
        assert EA.delete_asset(path)
    parent=fade(load(DEST+'/Materials/'+base_name))
    m=EA.duplicate_asset(parent.get_path_name(),path)
    cat=ML.create_material_expression(m,u.MaterialExpressionCollectionParameter,-700,1100)
    cat.set_editor_property('collection',load('/Game/Characters/BlackCat/Materials/MPC_CatOcclusion'))
    cat.set_editor_property('parameter_name','CatPosition')
    center=ML.create_material_expression(m,u.MaterialExpressionActorPositionWS,-700,1300)
    proximity=ML.create_material_expression(m,u.MaterialExpressionCustom,-400,1100)
    proximity.set_editor_property('code','return saturate(Cat.a)*(1.0-smoothstep(105.0,155.0,length(Cat.xy-Center.xy)));')
    proximity.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1)
    inputs=[]
    for name in ['Cat','Center']:
        entry=u.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
    proximity.set_editor_property('inputs',inputs)
    assert ML.connect_material_expressions(cat,'',proximity,'Cat')
    assert ML.connect_material_expressions(center,'',proximity,'Center')
    lerps=[e for e in ML.get_material_expressions(m) if isinstance(e,u.MaterialExpressionLinearInterpolate)]
    target=next(e for e in lerps if any(isinstance(n,u.MaterialExpressionMaterialFunctionCall) and n.get_editor_property('material_function').get_name()=='MF_WallOcclusion' for n in ML.get_inputs_for_material_expression(m,e) if n))
    assert ML.connect_material_expressions(proximity,'',target,'Alpha')
    ML.recompile_material(m);EA.set_metadata_tag(m,'Stage3DeviceReadabilityReady','1');EA.save_loaded_asset(m)
    return m
def cropped(source,width,depth):
    """Cut closure pieces in mesh space; source UVs and pattern pitch are retained."""
    b=source.get_bounding_box();size=b.max-b.min
    if abs(size.x-width)<.05 and abs(size.y-depth)<.05:return source
    name=f'{source.get_name()}_Cut_{int(width)}x{int(depth)}';path=DEST+'/Closures/'+name
    if EA.does_asset_exist(path):return load(path)
    d=u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(source,u.new_object(u.DynamicMesh),u.GeometryScriptCopyMeshFromAssetOptions(),u.GeometryScriptMeshReadLOD())[0]
    for loc,rot,keep in [(u.Vector(b.min.x+width,0,0),u.Rotator(pitch=-90),False),(u.Vector(0,b.min.y+depth,0),u.Rotator(roll=90),False)]:
        d=u.GeometryScript_MeshBooleans.apply_mesh_plane_cut(d,u.Transform(location=loc,rotation=rot),u.GeometryScriptMeshPlaneCutOptions(fill_holes=True,fill_spans=True,flip_cut_side=keep,hole_fill_material_id=0,uv_world_dimension=100))
    result=EA.duplicate_asset(source.get_path_name(),path)
    u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(d,result,u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,enable_recompute_tangents=True),u.GeometryScriptMeshWriteLOD())
    b=result.get_bounding_box();s=b.max-b.min
    body=result.get_editor_property('body_setup');geo=body.get_editor_property('agg_geom');box=u.KBoxElem()
    box.set_editor_property('center',(b.min+b.max)*.5);box.set_editor_property('rotation',u.Rotator())
    for key,value in zip(['x','y','z'],xyz(s)):box.set_editor_property(key,value)
    geo.set_editor_property('box_elems',[box])
    for key in ['convex_elems','sphere_elems','sphyl_elems']:geo.set_editor_property(key,[])
    body.set_editor_property('agg_geom',geo);body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
    assert abs(s.x-width)<.1 and abs(s.y-depth)<.1,(name,xyz(s))
    EA.save_loaded_asset(result);REPORT['closures'][name]={'size':xyz(s),'source':source.get_path_name()};return result
def wall_run(orient,fixed,start,end,side=1,openings=()):
    global SERIAL
    cursor=start
    for center,kind,label in sorted(openings)+[(end+100,None,None)]:
        stop=min(end,center-100)
        while cursor<stop-.1:
            length=min(200,stop-cursor);SERIAL+=1
            source=mesh('SM_S3_Wall_BlindArch_200' if SERIAL%7==0 and length==200 else 'SM_S3_Wall_200')
            m=cropped(source,length,30)
            offset=0 if side>0 else -30 if side<0 else -15
            minimum=(cursor,fixed+offset,0) if orient=='h' else (fixed+offset,cursor,0)
            at_min(f'Wall_{SERIAL:04}',m,minimum,0 if orient=='h' else 90,tags=('SoundWall',),occlusion=True)
            cursor+=length
        if kind:
            assert center-100>=start and center+100<=end,(label,start,end,center)
            source={'cat':'SM_S3_CatHoleWall','door':'SM_S3_ArmorDoor_Frame','gate':'SM_S3_PuzzleGate_Frame'}[kind]
            minimum=(center-100,fixed-15,0) if orient=='h' else (fixed-15,center-100,0)
            frame=at_min(label+'_Frame',source,minimum,(180 if kind=='gate' else 0) if orient=='h' else 90,tags=('SoundWall',),occlusion=True)
            pos=(center,fixed,0) if orient=='h' else (fixed,center,0)
            REPORT['portals'][label]={'position':pos,'orientation':orient,'kind':kind}
            if kind=='cat':
                static(label+'_Trim','SM_S3_CatHoleTrim',(pos[0],pos[1]-15.2,0),0,collision=False)
                zone=spawn(u.CatrunNoBellZone,label+'_NoBell',(pos[0],pos[1],35))
                zone.get_editor_property('Box').set_box_extent(u.Vector(45,55,45))
                zone.tags=list(zone.tags)+[u.Name('CatHole')]
            elif kind=='gate':
                gate=static(label+'_Bars','SM_S3_PuzzleGate_Bars',pos,180,folder='Puzzles',movable=True)
                GATES[label]=gate
            else:
                door=spawn(u.CatrunDoor,'D0',(pos[0],pos[1]-75,0),90)
                c=door.get_editor_property('DoorMesh');c.set_static_mesh(mesh('SM_S3_ArmorDoor_Leaf'))
                c.set_relative_location(u.Vector(3.8,0,0),False,False)
                box=door.get_editor_property('GateBox');box.set_relative_location(u.Vector(75,0,110),False,False);box.set_box_extent(u.Vector(75,20,110))
                door.set_editor_property('ArmorPassageHalfWidth',37.5)
            cursor=center+100

GATES={}
def characters():
    # Reuse exact Stage2 skeletons/animations; only duplicate the approved material variants.
    armor_source='/Game/Characters/Stage2/A/LivingArmor'
    candle_source='/Game/Characters/Stage2/A/CandleMonster'
    from import_assets import texture,SRC
    charcoal=texture(SRC/'Characters/SK_S3_GuardArmor_MaterialVariant/Textures/T_ArmorStage3_Charcoal_BaseColor.png','T_ArmorStage3_Charcoal_BaseColor')
    original=load(armor_source+'/Materials/M_ArmorStage2_Navy')
    path=DEST+'/Characters/M_ArmorStage3_Charcoal'
    material=load(path) if EA.does_asset_exist(path) else EA.duplicate_asset(original.get_path_name(),path)
    node=ML.get_material_property_input_node(material,u.MaterialProperty.MP_BASE_COLOR)
    assert isinstance(node,(u.MaterialExpressionTextureSample,u.MaterialExpressionTextureSampleParameter2D)),str(node)
    node.set_editor_property('texture',charcoal);ML.recompile_material(material);EA.save_loaded_asset(material)
    candle_mats={}
    for name,color in [('WarmWax',(.549395,.538242,.552939)),('WaxPool',(.356234,.345944,.362357))]:
        src=load(candle_source+'/Materials/M_CandleStage2_'+name);p=DEST+'/Characters/M_CandleStage3_'+name
        m=load(p) if EA.does_asset_exist(p) else EA.duplicate_asset(src.get_path_name(),p)
        n=ML.get_material_property_input_node(m,u.MaterialProperty.MP_BASE_COLOR)
        assert isinstance(n,(u.MaterialExpressionConstant3Vector,u.MaterialExpressionVectorParameter)),str(n)
        n.set_editor_property('default_value' if isinstance(n,u.MaterialExpressionVectorParameter) else 'constant',u.LinearColor(*color,1));ML.recompile_material(m);EA.save_loaded_asset(m);candle_mats[name]=m
    for label,pos,yaw,route in L.ARMORS:
        a=bp('/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor','Armor_'+label,pos,yaw)
        c=a.get_component_by_class(u.SkeletalMeshComponent);c.set_skeletal_mesh_asset(load(armor_source+'/Meshes/SK_LivingArmor_Stage2_A'))
        c.set_editor_property('override_materials',[]);c.set_material(3,material)
        points=[spawn(u.CatrunPatrolPoint,label+f'_Route{i}',p) for i,p in enumerate(route)]
        a.set_editor_property('PatrolPoints',points);a.set_editor_property('bPatrolLoop',len(points)>2)
    for label,pos,yaw,route in L.CANDLES:
        pos=(pos[0],pos[1],0)
        a=bp('/Game/Characters/CandleMonster/Blueprints/BP_Candle','Candle_'+label,pos,yaw)
        a.get_editor_property('BlockingCapsule').set_relative_location(u.Vector(0,0,62.25),False,False)
        c=a.get_editor_property('Body');c.set_skeletal_mesh_asset(load(candle_source+'/Meshes/SK_CandleMonster_Stage2_A'));c.set_editor_property('override_materials',[])
        c.set_material(0,candle_mats['WarmWax']);c.set_material(2,candle_mats['WaxPool'])
        points=[spawn(u.TargetPoint,label+f'_Route{i}',(p[0],p[1],0)) for i,p in enumerate(route)]
        a.set_editor_property('PatrolPoints',points);a.set_editor_property('bPatrolEnabled',bool(points));a.set_editor_property('bPatrolLoop',len(points)>2)

def main():
    gate_x0,gate_y0,gate_x1,gate_y1=L.ROOMS['GateHall']
    gate_x=(gate_x0+gate_x1)/2
    final_gate_y=gate_y1-50
    exhibit_x0,exhibit_y0,_,exhibit_y1=L.ROOMS['Exhibition']
    d2=[(center,fixed) for orient,fixed,start,end,openings in L.INTERNAL
        for center,kind,label in openings if label=='D2' and orient=='h']
    assert len(d2)==1
    d2_x,d2_y=d2[0]
    path='/Game/Maps/Stage3'
    marker=OUT/'map_ownership.json'
    if EA.does_asset_exist(path):
        assert marker.exists() and json.loads(marker.read_text())['map']==path,'Refusing to overwrite an unowned Stage3 map'
        assert LEVEL.load_level(path)
        for a in list(ACT.get_all_level_actors()):
            if 'CatrunStage3_20261125' in map(str,a.tags) or a.get_actor_label()=='S3_Minimap':assert ACT.destroy_actor(a)
    else:
        marker.write_text(json.dumps({'map':path,'run':'20261125'}),encoding='utf8')
        assert LEVEL.new_level(path)
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode',EA.load_blueprint_class('/Game/Blueprints/GameModes/GM_Cat'))
    for i,(x,y,w,h) in enumerate(L.floor_rectangles()):
        typ='SM_S3_Floor_GatePlain' if y>=gate_y0 else 'SM_S3_Floor_Octagon'
        m=cropped(mesh(typ),w,h)
        at_min(f'Floor_{i:04}',m,(x,y,-5),folder='Floors',tags=('SoundFloor',))
    # A short external landing supports the cat as the final exit overlap completes.
    for i in range(3):at_min(f'ExitLanding{i}','SM_S3_Floor_GatePlain',(gate_x-300+i*200,gate_y1,-5),folder='Floors',tags=('SoundFloor',))
    for orient,fixed,start,end,side in L.boundary_segments():
        if orient=='h' and fixed==gate_y1:
            wall_run(orient,fixed,start,gate_x-400,side);wall_run(orient,fixed,gate_x+400,end,side)
        else:wall_run(orient,fixed,start,end,side)
    for orient,fixed,start,end,openings in L.INTERNAL:wall_run(orient,fixed,start,end,0,openings)
    for label,name,pos,yaw in L.PROPS:
        if name not in IM['meshes']:
            if label=='DisplayJoint':continue
            raise RuntimeError('Missing prop '+name)
        static(label,name,pos,yaw,folder='Furnishing',tags=('SoundObstacle',),occlusion=True)
    links=[]
    for i,(pos,platepos,gate) in enumerate(L.STATUES,1):
        statue=static(f'Statue{i}','SM_S3_GuardianStatue',pos,folder='Puzzles',movable=True)
        static(f'Plate{i}_Frame','SM_S3_StatuePlate_Frame',(platepos[0],platepos[1],.15),folder='Puzzles',collision=False)
        plate=static(f'Plate{i}','SM_S3_StatuePlate_Plate',(platepos[0],platepos[1],.15),folder='Puzzles',movable=True,collision=False)
        link=u.CatrunStatuePuzzleLink();link.set_editor_property('PuzzleId',f'S3_P{i}');link.set_editor_property('Statue',statue);link.set_editor_property('Plate',plate);link.set_editor_property('Gate',GATES[gate]);link.set_editor_property('ContactHalfExtent',u.Vector2D(60,60));link.set_editor_property('SocketAxis',u.Vector(0,1,0));link.set_editor_property('bExternalGateUnlocked',i==1);links.append(link)
    puzzle=spawn(u.CatrunStatuePuzzle,'StatuePuzzles');puzzle.set_editor_property('Links',links)
    director=spawn(u.CatrunStage3Objectives,'Objectives');director.set_editor_property('Puzzle',puzzle)
    animation_report=OUT/'Animation/animation_report.json'
    if not animation_report.exists():animation_report=ROOT/'Docs/Reviews/Stage3Evidence/animation_report.json'
    animation=json.loads(animation_report.read_text(encoding='utf8'))
    director.set_editor_property('ReleaseAnimation',load(IM['animation']['path']))
    director.set_editor_property('MouthOffsets',[u.Vector(*s['mouth_actor_cm']) for s in animation['samples']])
    devices=[]
    for i,pos in enumerate(L.DEVICES):
        h=static(f'Release{i+1}_Housing','SM_S3_ReleaseHousing',pos,180,folder='Objectives',tags=('SoundObstacle',),occlusion=True)
        r=static(f'Release{i+1}_Ring','SM_S3_ReleaseRing',(pos[0]+10,pos[1]-43,27.5),180,folder='Objectives',movable=True,collision=False)
        p=static(f'Release{i+1}_Pin','SM_S3_ReleasePin',(pos[0],pos[1]-9,71.7),180,folder='Objectives',movable=True,collision=False)
        static(f'Release{i+1}_Pulley','SM_S3_ChainPulley',(pos[0]-8,pos[1]+2.5,79),180,folder='Objectives',collision=False)
        chain=[]
        eye=u.Vector(pos[0]+10,pos[1]-10,68.5);top=u.Vector(pos[0]+10,pos[1]-43,34.9);axis=(eye-top).normal()
        for j in range(6):
            point=(top+axis*2.6)*(1-j/5)+(eye-axis*5.5)*(j/5)
            a=static(f'Release{i+1}_Chain{j}','SM_S3_ChainLink',xyz(point),folder='Objectives',movable=True,collision=False)
            rotation=u.MathLibrary.make_rot_from_z(axis)
            a.set_actor_rotation(rotation,True);chain.append(a)
        numeral='SM_S3_ReleaseIndicator'+('' if i==0 else '_'+str(i+1))
        static(f'Release{i+1}_Indicator',numeral,(pos[0],pos[1]+7.6,39),180,folder='Objectives',collision=False)
        # Published PuzzleGate_ThreeLocks assembly: +90 degrees Blender Y is
        # -90 Unreal pitch, with 16 cm horizontal withdrawal and moving keepers.
        z=62+i*70
        housing=static(f'Lock{i+1}_Housing','SM_S3_GateLockHousing',(d2_x-71,d2_y-21,z),folder='Objectives',collision=False)
        housing.set_actor_rotation(u.Rotator(pitch=-90,yaw=180),True)
        bolt=static(f'Lock{i+1}_Bolt','SM_S3_GateLockBolt',(d2_x-59.9,d2_y-21,z),folder='Objectives',movable=True,collision=False)
        bolt.set_actor_rotation(u.Rotator(pitch=-90,yaw=180),True)
        keeper=static(f'Lock{i+1}_Keeper','SM_S3_D2_BarKeeper',(d2_x-64.4,d2_y-21,z),180,folder='Objectives',movable=True,collision=False)
        keeper.attach_to_actor(GATES['D2'],u.Name('None'),u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,False)
        d=u.CatrunReleaseDevice();d.set_editor_property('Housing',h);d.set_editor_property('Ring',r);d.set_editor_property('Pin',p);d.set_editor_property('LockBolt',bolt);d.set_editor_property('ChainLinks',chain);devices.append(d)
    director.set_editor_property('Devices',devices)
    for x in [gate_x-470,gate_x+470]:
        for j,y in enumerate([gate_y0+250,gate_y0+550,gate_y0+825]):
            for part,z in [('Base',0),('ShaftLower',40),('ShaftUpper',300),('Capital',840)]:
                static(f'GrandPillar_{x}_{j}_{part}','SM_S3_GrandPillar_'+part,(x,y,z),folder='GateHall',tags=('SoundObstacle',),occlusion=True)
    for part,z in [('LowerFrame',0),('UpperFrame',300)]:static('FinalGate_'+part,'SM_S3_FinalGate_'+part,(gate_x,final_gate_y,z),180,folder='GateHall',tags=('SoundWall',),occlusion=True)
    REPORT['portals']['FinalGate']={'position':(gate_x,final_gate_y,0),'orientation':'h','kind':'gate','clear_width':600}
    for part,prop in [('Leaf_L','FinalLeafLeft'),('Leaf_R','FinalLeafRight')]:
        imported_part='Leaf_R' if part=='Leaf_L' else 'Leaf_L'
        a=static('FinalGate_'+part,'SM_S3_FinalGate_'+imported_part,(gate_x,final_gate_y,0),180,folder='GateHall',movable=True,occlusion=True);director.set_editor_property(prop,a)
    # Carpet sits above, never coincides with the stone surface. It has no unapproved acoustic multiplier.
    runners=[k for k in IM['meshes'] if 'Runner' in k]
    for j,y in enumerate(range(gate_y0+100,gate_y0+900,200)):
        name=next((k for k in runners if ('End' in k)==(j in [0,3])),runners[0])
        at_min(f'Runner{j}',name,(gate_x-125,y,.15),90,folder='GateHall',collision=False)
    for j,(x,y) in enumerate([(exhibit_x0+70,exhibit_y0+150),(exhibit_x0+70,exhibit_y0+800),(-330,1100),(1140,1640),(870,2500),(gate_x0+70,gate_y0+350),(gate_x1-70,gate_y0+350),(gate_x0+70,gate_y1-150),(gate_x1-70,gate_y1-150)]):
        grand=y>=gate_y0
        static(f'Lantern{j}','SM_S3_GrandWallLantern' if grand else 'SM_S3_WallSconce',(x,y,160),folder='Lighting',collision=False)
        light=spawn(u.PointLight,f'LocalLight{j}',(x,y-45,205),folder='Lighting')
        c=light.point_light_component;c.set_mobility(u.ComponentMobility.MOVABLE);c.set_intensity(500 if grand else 220);c.set_light_color(u.LinearColor(1,.91,.76,1));c.set_attenuation_radius(550);c.set_cast_shadows(False)
    for j,(x,y,z) in enumerate([(gate_x-600,gate_y1-30,650),(gate_x+600,gate_y1-30,650),(exhibit_x0+100,exhibit_y1-50,280),(900,2530,280)]):
        static(f'Banner{j}','SM_S3_GrandBanner' if z>300 else 'SM_S3_GuardBanner',(x,y,z),folder='Decor',collision=False,occlusion=True)
    key=spawn(u.DirectionalLight,'KeyLight',(0,2000,1000),folder='Lighting');key.set_actor_rotation(u.Rotator(pitch=-55,yaw=-35),True);key.get_component_by_class(u.DirectionalLightComponent).set_mobility(u.ComponentMobility.MOVABLE);key.get_component_by_class(u.DirectionalLightComponent).set_intensity(2.2);key.get_component_by_class(u.DirectionalLightComponent).set_light_color(u.LinearColor(.92,.94,1,1))
    fill=spawn(u.DirectionalLight,'FillLight',(0,2000,1000),folder='Lighting');fill.set_actor_rotation(u.Rotator(pitch=-70,yaw=145),True);fill.get_component_by_class(u.DirectionalLightComponent).set_mobility(u.ComponentMobility.MOVABLE);fill.get_component_by_class(u.DirectionalLightComponent).set_intensity(.8);fill.get_component_by_class(u.DirectionalLightComponent).set_cast_shadows(False)
    pp=spawn(u.PostProcessVolume,'Exposure',folder='Lighting');pp.set_editor_property('unbound',True)
    settings=pp.get_editor_property('settings');settings.set_editor_property('override_auto_exposure_min_brightness',True);settings.set_editor_property('override_auto_exposure_max_brightness',True);settings.set_editor_property('auto_exposure_min_brightness',1.);settings.set_editor_property('auto_exposure_max_brightness',1.);pp.set_editor_property('settings',settings)
    spawn(u.PlayerStart,'PlayerStart',(150,110,30),90)
    cat=bp('/Game/Characters/BlackCat/Blueprints/BP_Cat','Player',(150,110,26.2),90)
    cat.set_editor_property('auto_possess_player',u.AutoReceiveInput.PLAYER0)
    cam=bp('/Game/Systems/Camera/BP_QuarterViewCamera','FollowCamera',(150,110,26),45)
    cam.get_component_by_class(u.CameraComponent).set_editor_property('ortho_width',900.)
    cam.tags=list(cam.tags)+[u.Name('CatrunGameplayCamera')]
    grid=spawn(u.SoundGridManager,'SoundGrid');grid.set_editor_property('Settings',load('/Game/Systems/Sound/DA_SoundSettings'))
    bp('/Game/Systems/Sound/Visual/Bluprints/BP_CatrunSoundController','SoundVisual')
    characters()
    ex=spawn(u.CatrunStageExit,'FinalExit',(gate_x,gate_y1+90,60));ex.get_editor_property('Trigger').set_box_extent(u.Vector(250,45,80));ex.set_editor_property('bRequireCenterInside',True)
    grid.build_grid();assert grid.has_grid()
    REPORT['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
    REPORT['bounds']=[{'label':a.get_actor_label(),'min':xyz(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':xyz(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':[str(t) for t in a.tags]} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
    assert LEVEL.save_current_level()
    REPORT['success']=True;REPORT['actor_count']=len(ACT.get_all_level_actors());persist();print('STAGE3_MAP_OK',REPORT['actor_count'])

if __name__=='__main__':
    try:main()
    except Exception:REPORT['error']=traceback.format_exc();persist();raise
