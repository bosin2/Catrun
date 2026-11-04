import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
result={'subsystem_api':{n:str(getattr(unreal,n).__doc__) for n in dir(unreal) if 'local_player' in n},'graphs':{}}
for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game',True):
    if str(data.asset_name) not in ['BP_Cat','BP_CatActions']:continue
    bp=data.get_asset();rows=[]
    for g in BP.list_graphs(bp):
        for n in BP.get_node_infos(BP.find_nodes(g)):
            if any(s in n.type_id for s in ['Bell','MappingContext','Interact','InputAction','MapKey']):rows.append({'graph':g.get_name(),'name':n.node.get_name(),'type':n.type_id,'inputs':[{'name':p.name,'value':str(p.value)} for p in n.input_pins]})
    result['graphs'][bp.get_path_name()]=rows
(Path(unreal.Paths.project_saved_dir())/'Prototype20261104/CanonicalMaps/input-graph-inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
