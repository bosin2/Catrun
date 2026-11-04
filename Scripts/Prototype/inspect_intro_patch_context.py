import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
bp=unreal.load_asset('/Game/Blueprints/BP_TutorialIntro')
g=BP.get_graph(bp,'EventGraph')
nodes=BP.get_node_infos(BP.find_nodes(g))
print('VARIABLES',BP.list_variables(bp))
for n in nodes:
    if n.node.get_name() in ['K2Node_CallFunction_6','K2Node_CallFunction_8','K2Node_CallFunction_9','K2Node_CallFunction_17','K2Node_CreateWidget_0']:
        print('NODE',n.node.get_name(),[(p.name,BP.get_pin_value(p.pin_id)) for p in n.input_pins])
print('ARRAY',BP.find_node_types(g,'Array'))
print('DOC_SET',BP.set_pin_value.__doc__)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/SoundTest_Tutorial')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows=[]
for a in actors:
    if any(s in a.get_actor_label().lower() for s in ['cat','intro','camera','cine','zzz','sleep']):
        row=dict(name=a.get_name(),label=a.get_actor_label(),cls=a.get_class().get_name(),path=a.get_path_name(),location=str(a.get_actor_location()))
        row['components']=[dict(name=c.get_name(),cls=c.get_class().get_name()) for c in a.get_components_by_class(unreal.ActorComponent)]
        if a.get_class().get_name()=='BP_TutorialIntro_C':row['variables']={v:str(a.get_editor_property(v)) for v in BP.list_variables(bp)}
        rows.append(row)
(out/'intro-patch-context.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print('CONTEXT',rows)
