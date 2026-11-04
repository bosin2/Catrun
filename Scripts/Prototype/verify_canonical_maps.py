"""Reloaded disk-map, passage capsule, references, graph and input inspection."""
import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/CanonicalMaps'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
def vec(v):return [round(v.x,3),round(v.y,3),round(v.z,3)]
def trace(w,a,b,r=20,h=24,ignore=[]):
    hit=unreal.SystemLibrary.capsule_trace_single_by_profile(w,unreal.Vector(*a),unreal.Vector(*b),r,h,'Pawn',False,ignore,unreal.DrawDebugTrace.NONE,False)
    return str(hit) if hit else None
result={'maps':{},'graphs':{},'inputs':{}}
for stage in ['Tutorial','Stage1','Stage2']:
    assert levels.load_level('/Game/Maps/'+stage)
    w=editor.get_editor_world();actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)
    rows=[]
    for a in actors:
        rot=a.get_actor_rotation()
        row={'label':a.get_actor_label(),'name':a.get_name(),'class':a.get_class().get_name(),'location':vec(a.get_actor_location()),'rotation':[rot.pitch,rot.yaw,rot.roll],'scale':vec(a.get_actor_scale3d())}
        mesh=a.get_component_by_class(unreal.StaticMeshComponent)
        if mesh and mesh.static_mesh:row['mesh']=mesh.static_mesh.get_path_name()
        if row['class']=='BP_TutorialIntro_C':row['bindings']={p:a.get_editor_property(p).get_path_name() for p in ['Cat','StartCamera','WakeCamera','GamePlayCamera']}
        if row['class']=='CatrunNoBellZone':row['extent']=vec(a.get_component_by_class(unreal.BoxComponent).get_scaled_box_extent())
        rows.append(row)
    result['maps'][stage]={'actors':rows,'count':len(rows)}
    if stage=='Tutorial':
        armor=next(a for a in actors if a.get_actor_label()=='Armor_Tutorial')
        result['tutorial_geometry']={
            'armor_clearance':trace(w,(-80,820,101),(-80,820,101.1),35,100,[armor]),
            'cat_hole_transit':trace(w,(-275,420,26),(-275,510,26)),
            'corridor_pass_armor':trace(w,(-170,730,26),(-170,885,26)),
            'armor_floor':str(unreal.SystemLibrary.line_trace_single(w,unreal.Vector(-80,820,105),unreal.Vector(-80,820,-15),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[armor],unreal.DrawDebugTrace.NONE,False))}
    # Registry dependencies catch stale map package references; actor hard refs are
    # separately verified for intro, and T3D exposes saved component/door bindings.
    result['maps'][stage]['dependencies']=list(map(str,unreal.AssetRegistryHelpers.get_asset_registry().get_dependencies('/Game/Maps/'+stage,unreal.AssetRegistryDependencyOptions(True,True,False,False,False))))
    task=unreal.AssetExportTask();task.object=w;task.filename=str(out/(stage+'.t3d'))
    task.automated=True;task.prompt=False;task.replace_identical=True
    assert unreal.Exporter.run_asset_export_task(task),stage
    task=None;w=None;actors=None;a=None
for path in ['/Game/Blueprints/BP_TutorialIntro','/Game/Systems/LevelFlow/BP_LevelExit','/Game/UI/WBP_MainMenu']:
    bp=unreal.load_asset(path)
    if not bp:continue
    compile_blueprint(bp,True)
    assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE,(path,str(bp.get_editor_property('status')))
    nodes=[]
    for graph in BP.list_graphs(bp):
        for n in BP.get_node_infos(BP.find_nodes(graph)):
            nodes.append({'graph':graph.get_name(),'node':n.node.get_name(),'type':n.type_id,'inputs':[{'name':p.name,'value':str(p.value),'links':str(p.connected_pins)} for p in n.input_pins]})
    result['graphs'][path]={'status':'BS_UP_TO_DATE','nodes':nodes}
for path in ['/Game/Input/Contexts/IMC_Default','/Game/Input/Contexts/IMC_CatInteraction']:
    asset=unreal.load_asset(path)
    result['inputs'][path]=[{'action':m.action.get_path_name(),'key':m.key.export_text(),'modifiers':[x.get_class().get_name() for x in m.modifiers]} for m in asset.get_editor_property('default_key_mappings').get_editor_property('mappings')]
(out/'disk-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('MAPS_VERIFY',json.dumps({k:{'count':v['count'],'map_dependencies':[d for d in v['dependencies'] if '/Maps/' in d]} for k,v in result['maps'].items()}))
print('GEOMETRY',result['tutorial_geometry']);print('INPUTS',result['inputs'])
assert levels.load_level('/Game/Maps/MainMenu')
