"""Wire existing menu/stair Blueprints and place exits at existing doors. Backups go to Saved/Flow.
Run with UnrealEditor-Cmd -run=pythonscript -script=<this file>. Idempotent.
"""
import json
import shutil
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

root = Path(unreal.Paths.project_dir())
output = root / "Saved" / "Flow"
backup = output / "Backups"
backup.mkdir(parents=True, exist_ok=True)
assets = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report = {"blueprints": [], "exits": []}

def backup_file(relative):
    target = backup / relative
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)

def connect_flow(path, graph_name, function):
    backup_file('Content/' + path.removeprefix('/Game/') + '.uasset')
    bp = assets.load_asset(path)
    graph = unreal.load_object(None, path + '.' + path.rsplit('/', 1)[-1] + ':' + graph_name)
    assert bp and graph, path
    infos = BP.get_node_infos(BP.find_nodes(graph))
    existing = [n for n in infos if n.type_id.endswith('|' + function)]
    if existing:
        assert len(existing) == 1, path
    else:
        old = [n for n in infos if 'OpenLevel' in n.type_id]
        assert len(old) == 1, [(n.type_id) for n in infos]
        old = old[0]
        editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
        choices = [t for t in editor.list_available_nodes([]) if ''.join(t.split()).endswith('|' + function)]
        assert len(choices) == 1, (function, choices)
        new = BP.create_node(graph, choices[0], old.position, unreal.CatrunLevelFlowLibrary.static_class())
        info = BP.get_node_infos([new])[0]
        old_exec = next(p for p in old.input_pins if p.name == 'execute')
        new_exec = next(p for p in info.input_pins if p.name == 'execute')
        # Preserve the existing event/sequence chain; replace only the final travel node.
        sources = list(old_exec.connected_pins)
        assert sources, path
        for source in sources:
            BP.break_pins(source, old_exec.pin_id)
            BP.connect_pins(source, new_exec.pin_id)
        BP.delete_node(old.node)
    BP.compile_blueprint(bp)
    assert assets.save_loaded_asset(bp), path
    report['blueprints'].append({'asset': path, 'graph': graph_name, 'function': function})

connect_flow('/Game/UI/WBP_MainMenu', 'EventGraph', 'StartNewGame')
connect_flow('/Game/Systems/LevelFlow/BP_LevelExit', 'CompleteTransition', 'CompleteCurrentStage')

# Stage2 completes after the cat enters the corridor beyond Gate_00.
for map_name, label, location, extent in [
    ('SoundTest_Stage1', 'Flow_ExitToStage2', (101, 65, 65), (65, 30, 80)),
    ('SoundTest_Stage2', 'Flow_Stage2Complete', (715, -80, 65), (65, 30, 80)),
]:
    backup_file('Content/Maps/' + map_name + '.umap')
    assert levels.load_level('/Game/Maps/' + map_name)
    exits = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.CatrunStageExit)]
    assert len(exits) <= 1, 'Duplicate exit in ' + map_name
    actor = exits[0] if exits else actors.spawn_actor_from_class(unreal.CatrunStageExit, unreal.Vector(*location))
    actor.set_actor_label(label)
    actor.set_folder_path('Gameplay/LevelFlow')
    actor.set_actor_location(unreal.Vector(*location), False, True)
    actor.get_editor_property('Trigger').set_box_extent(unreal.Vector(*extent))
    if label == 'Flow_Stage2Complete':
        actor.set_editor_property('bRequireCenterInside', True)
    assert levels.save_current_level()
    report['exits'].append({'map': map_name, 'label': label, 'location': location, 'extent': extent})

(output / 'setup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('FLOW_SETUP_OK ' + json.dumps(report, ensure_ascii=False))
