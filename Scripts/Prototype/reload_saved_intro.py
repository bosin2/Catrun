import unreal,json,re,hashlib
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/Prototype20261104'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert levels.load_level('/Game/Maps/MainMenu')
bp=unreal.load_asset('/Game/Blueprints/BP_TutorialIntro')
result,error=unreal.EditorLoadingAndSavingUtils.reload_packages([bp.get_outermost()],unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
assert result and not str(error),str(error)
bp=unreal.load_asset('/Game/Blueprints/BP_TutorialIntro')
assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE,str(bp.get_editor_property('status'))
def link_data(p):return {'node':p.node.get_name(),'index':p.index_id,'direction':str(p.direction)}
nodes=[]
for n in BP.get_node_infos(BP.find_nodes(BP.get_graph(bp,'EventGraph'))):
    nodes.append({'name':n.node.get_name(),'type':n.type_id,'position':[n.position.x,n.position.y],'inputs':[{'name':p.name,'value':BP.get_pin_value(p.pin_id),'links':[link_data(q) for q in p.connected_pins]} for p in n.input_pins],'outputs':[{'name':p.name,'links':[link_data(q) for q in p.connected_pins]} for p in n.output_pins]})
(out/'intro-graph-after.json').write_text(json.dumps(nodes,indent=2),encoding='utf8')
report={'reload_from_disk':result,'reload_error':str(error),'blueprint_status':str(bp.get_editor_property('status')),'editor_world':editor.get_editor_world().get_path_name(),'pie_active':bool(editor.get_game_world()),'node_count':len(nodes),'bindings':[n for n in nodes if n['type'].endswith('|SetBinding')],'hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['Content/Blueprints/BP_TutorialIntro.uasset','Content/Maps/SoundTest_Tutorial.umap','Content/Cinematics/LS_Tutorial.uasset']}}
(out/'intro-final-save-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('SAVED_INTRO_RELOAD_VERIFIED',json.dumps({k:v for k,v in report.items() if k!='bindings'}))
