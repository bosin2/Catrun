"""Read-only inspection of existing tutorial cinematic links and actor settings."""
import json
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.object import ObjectTools as OBJ

out = Path(unreal.Paths.project_saved_dir()) / 'Restoration'
out.mkdir(parents=True, exist_ok=True)
result = {'graphs': {}, 'maps': {}}
for path in ['/Game/Blueprints/BP_TutorialIntro',
             '/Game/Cinematics/Transitions/Blueprints/BP_StairDescentDirector',
             '/Game/Systems/LevelFlow/BP_LevelExit', '/Game/Systems/LevelFlow/BP_LevelArrival']:
    bp = unreal.EditorAssetLibrary.load_asset(path)
    rows = []
    for graph in BP.list_graphs(bp):
        for node in BP.get_node_infos(BP.find_nodes(graph)):
            rows.append({'graph': graph.get_name(), 'node': node.node.get_name(), 'type': node.type_id,
                         'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in node.input_pins],
                         'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in node.output_pins]})
    result['graphs'][path] = rows
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for name in ['Tutorial', 'SoundTest_Tutorial', 'SoundTest_Stage1']:
    assert levels.load_level('/Game/Maps/' + name)
    rows = []
    for actor in actors.get_all_level_actors():
        cls = actor.get_class().get_name()
        if not any(s in cls for s in ['LevelExit', 'LevelArrival', 'StairDescent', 'TutorialIntro', 'Candle', 'LivingArmor', 'CatrunDoor', 'SoundGrid']):
            continue
        row = {'label': actor.get_actor_label(), 'class': cls, 'position': str(actor.get_actor_location()), 'properties': {}}
        for prop in ['WaitForCinematic', 'TransitionStarted', 'ExitActor', 'LevelExit', 'Sequence', 'LevelSequence',
                     'SequencePlayer', 'PlayerRef', 'bStartOpen', 'bPenaltiesEnabled', 'PatrolPoints', 'Settings']:
            try: row['properties'][prop] = str(actor.get_editor_property(prop))
            except Exception: pass
        rows.append(row)
    result['maps'][name] = rows
(out / 'inspection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('RESTORATION_INSPECTION_OK')
