"""Single live-editor writer: preserve gameplay identities while repairing plan topology."""
import sys,json,importlib,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
sys.path.insert(0,str(ROOT/'Scripts/Stage3'))
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import layout,build_map,dressing,occlusion,floor_recess
L=importlib.reload(layout);B=importlib.reload(build_map)
for module in (dressing,occlusion,floor_recess):importlib.reload(module)
ACT=u.get_editor_subsystem(u.EditorActorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);EA=u.EditorAssetLibrary
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
assert not ED.get_game_world()
assert (OUT/'Stage3_before.umap').exists()
assert not (OUT/'applied.json').exists(),'Already applied; inspect before repeating'
actors=list(ACT.get_all_level_actors());lookup={a.get_actor_label():a for a in actors}
before={a.get_path_name():a.get_actor_location() for a in actors}
R={'success':False,'moved':[],'rooms':L.ROOMS,'connectors':L.CONNECTORS,'removed_architecture':[]}
def vec(p):return [p.x,p.y,p.z]
def unwrap(m):
    for key in ('Stage3ReadabilitySource','Stage3DockRecessSource'):
        src=EA.get_metadata_tag(m,key)
        if src:m=EA.load_asset(src)
    return m
# Keep calibrated per-slot shading rather than falling back to imported colors.
bindings={}
for a in actors:
    if not a.get_actor_label().startswith(('S3_Floor_','S3_Wall_')):continue
    c=a.get_component_by_class(u.StaticMeshComponent)
    for i,slot in enumerate(c.static_mesh.get_editor_property('static_materials')):
        source=slot.get_editor_property('material_interface')
        if source:bindings[(a.get_actor_label().startswith('S3_Floor_'),source.get_path_name())]=unwrap(c.get_material(i))
def calibrate(a):
    c=a.static_mesh_component
    for i,slot in enumerate(c.static_mesh.get_editor_property('static_materials')):
        source=slot.get_editor_property('material_interface')
        key=(a.get_actor_label().startswith('S3_Floor_'),source.get_path_name() if source else None)
        assert key in bindings,(a.get_actor_label(),str(source))
        c.set_material(i,bindings[key])
def delta(a):
    label=a.get_actor_label();p=before[a.get_path_name()]
    if label.startswith(('S3_Wall_','S3_Floor_')) or dressing.OWNER in map(str,a.tags):return u.Vector()
    if label.startswith(('S3_D2_','S3_Lock','S3_GothicVisual_Lock','S3_GothicConnections_D2Lock')):return u.Vector(-50,-50,0)
    if p.y>=2900 and label.startswith('S3_'):return u.Vector(-50,-50,0)
    if -1010<=p.x<-400 and 1300<=p.y<=2450:return u.Vector(-150,0,0)
    if label.startswith(('S3_Lantern','S3_LocalLight','S3_Banner')) and -360<=p.x<=-50 and 2350<=p.y<2900:return u.Vector(-50,-50,0)
    return u.Vector()
try:
    # Absolute target world transforms prevent attached-child double offsets.
    moves=[(a,before[a.get_path_name()]+delta(a),delta(a)) for a in actors]
    def depth(a):
        n=0;p=a.get_attach_parent_actor()
        while p:n+=1;p=p.get_attach_parent_actor()
        return n
    for a,target,d in sorted(moves,key=lambda row:depth(row[0])):
        if d.length()>0:
            a.set_actor_location(target,False,True)
            R['moved'].append({'actor':a.get_actor_label(),'before':vec(before[a.get_path_name()]),'after':vec(target)})
    presenter=lookup['S3_GothicPresentation_Dock1']
    for key in ('ForkOpen','ForkClosed','PinOpen','PinLowered','PinClosed','ChainTerminalOpen','ChainTerminalClosed'):
        presenter.set_editor_property(key,presenter.get_editor_property(key)+u.Vector(-150,0,0))
    # Existing native links remain object-identical, with their actors translated.
    assert lookup['S3_Plate1'].get_actor_location().x==-700
    assert lookup['S3_D2_Bars'].get_actor_location().y==2300
    for a in actors:
        if a.get_actor_label().startswith(('S3_Wall_','S3_Floor_')):
            assert 'CatrunStage3_20261125' in map(str,a.tags)
            R['removed_architecture'].append(a.get_actor_label());assert ACT.destroy_actor(a)
    B.SERIAL=0
    for i,(x,y,w,h) in enumerate(L.floor_rectangles()):
        source=B.mesh('SM_S3_Floor_GatePlain' if y>=2900 else 'SM_S3_Floor_Octagon')
        a=B.at_min(f'Floor_{i:04}',B.cropped(source,w,h),(x,y,-5),folder='Floors',tags=('SoundFloor',))
        calibrate(a)
    for orient,fixed,start,end,side in L.boundary_segments():
        if orient=='h' and fixed==4000:
            B.wall_run(orient,fixed,start,-650,side);B.wall_run(orient,fixed,150,end,side)
        else:B.wall_run(orient,fixed,start,end,side)
    for orient,fixed,start,end,openings in L.INTERNAL:
        cursor=start
        for center,kind,label in sorted(openings):
            if cursor<center-100:B.wall_run(orient,fixed,cursor,center-100,0)
            cursor=center+100
        if cursor<end:B.wall_run(orient,fixed,cursor,end,0)
    for a in ACT.get_all_level_actors():
        if a.get_actor_label().startswith('S3_Wall_'):calibrate(a)
    # Reference exhibition L route, using the existing two route identities.
    candle=lookup['S3_Candle_Exhibition'];points=list(candle.get_editor_property('PatrolPoints'))
    route=next(row[3] for row in L.CANDLES if row[0]=='Exhibition')
    while len(points)<len(route):
        a=ACT.spawn_actor_from_class(u.TargetPoint,u.Vector())
        a.set_actor_label('S3_Exhibition_ReferenceRoute'+str(len(points)));a.tags=[u.Name('Stage3LayoutCorrection20261125')];points.append(a)
    for point,pos in zip(points,route):point.set_actor_location(u.Vector(pos[0],pos[1],0),False,True)
    candle.set_editor_property('PatrolPoints',points);candle.set_editor_property('bPatrolLoop',True)
    R['dressing']=dressing.apply()
    for a in ACT.get_all_level_actors():
        if a.get_actor_label().startswith('S3_Gothic_GateAxis'):
            a.static_mesh_component.set_visibility(False);a.static_mesh_component.set_hidden_in_game(True)
    R['floor_recess']=floor_recess.apply()
    R['cutaway']=occlusion.apply()
    # Keep a unique primary directional light for forward/translucent rendering.
    lookup['S3_KeyLight'].get_component_by_class(u.DirectionalLightComponent).set_editor_property('forward_shading_priority',1)
    lookup['S3_FillLight'].get_component_by_class(u.DirectionalLightComponent).set_editor_property('forward_shading_priority',0)
    grid=lookup['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
    R['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
    R['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
    R['portals']={name:{'position':pos,'orientation':orient,'kind':kind} for orient,fixed,start,end,ops in L.INTERNAL for center,kind,name in ops for pos in [[center,fixed,0] if orient=='h' else [fixed,center,0]]}
    u.SystemLibrary.execute_console_command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
    assert LE.save_current_level()
    R['success']=True;R['map_saved']=True
    (OUT/'applied.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf8')
    print('LAYOUT_CORRECTION_SAVED',len(R['moved']))
except Exception:
    R['error']=traceback.format_exc();(OUT/'attempt_error.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf8');raise
