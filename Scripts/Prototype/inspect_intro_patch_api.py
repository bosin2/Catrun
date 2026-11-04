import unreal, json, inspect
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
path='/Game/Blueprints/BP_TutorialIntro'
graph=unreal.load_object(None,path+'.BP_TutorialIntro:EventGraph')
infos=BP.get_node_infos(BP.find_nodes(graph))
rows=[]
for n in infos:
    rows.append(dict(name=n.node.get_name(),type=n.type_id,position=str(n.position),inputs=[dict(name=p.name,pin=str(p.pin_id),links=[str(x) for x in p.connected_pins]) for p in n.input_pins],outputs=[dict(name=p.name,pin=str(p.pin_id),links=[str(x) for x in p.connected_pins]) for p in n.output_pins]))
(out/'intro-live-graph.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print('BP_FILE',inspect.getfile(BP))

editor=unreal.BlueprintGraphEditor.get_graph_editor(graph)
choices=editor.list_available_nodes([])
matches=[x for x in choices if any(y in x for y in ['SetBinding','MakeArray','ShouldSkipStageIntro','RestorePlayableStart','GetBinding','MakeMovieScene','SetAnimInstanceClass','MakeTransform','Branch','SetActorHiddenInGame','SetVisibility'])]
print('CHOICES',matches)
seq=unreal.load_asset('/Game/Cinematics/LS_Tutorial')
for b in seq.get_possessables():
    bid=seq.get_binding_id(b)
    print('BINDING',b.get_name(),b.get_id().to_string(),str(bid),bid.export_text())
print('FLOW',unreal.CatrunLevelFlowLibrary.restore_playable_start.__doc__)


