"""Scoped player resource graph authoring. Set CATRUN_PLAYER_RESOURCES_MODE to dry/audit/apply/cold."""

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import traceback

import unreal as u
from editor_toolset.toolsets.actor import ActorTools
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayExpansion20261124'
CONTRACT = OUT / 'cat-runtime-contract.json'
CAT = '/Game/Characters/BlackCat/Blueprints/BP_Cat'
ACTIONS = '/Game/Systems/Player/Interaction/BP_CatActions'
PROTECTED = (
    '/Game/Characters/BlackCat/Final/Animations/BS_CatMove_Final',
    '/Game/Systems/Sound/DA_SoundSettings',
    '/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings',
)
SPEED_GRAPH = 'UpdateMovementSpeed'
BELL_GRAPH = 'TryBell'
RUN_SPEED = 'CATCTRL_SelectRunSpeed'
RUN_INTENT = 'CATCTRL_ReadRunning'
BELL_COMPARE = 'K2Node_PromotableOperator_1'
BELL_LEGACY_LITERAL = 'K2Node_CallFunction_6'
COOLDOWN = 'BellCooldownSeconds'
SPRINT_QUERY = '/Script/Catrun.CatrunSprintComponent.ResolveSprintIntent'
CAT_EVENT_TOKENS = ('IsRunning', 'IsSneaking', 'UpdateMovementSpeed', 'MaxWalkSpeed', 'IA_Run', 'IA_Sneak')
AS = u.EditorAssetLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)


def asset_file(package):
    return ROOT / 'Content' / (package.removeprefix('/Game/') + '.uasset')


def digest(package):
    return hashlib.sha256(asset_file(package).read_bytes()).hexdigest()


def backup(package):
    source = asset_file(package)
    target = OUT / 'PlayerResourcesBefore' / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
    assert target.read_bytes() == source.read_bytes(), ('Backup conflicts with current original', str(target))
    return str(target)


def dirty():
    return {p.get_name() for p in [*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                  *u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}


def load(package):
    asset = AS.load_asset(package)
    assert asset and asset.generated_class(), package
    return asset


def default(asset):
    return u.get_default_object(asset.generated_class())


def graph(asset, name):
    found = BP.get_graph(asset, name)
    assert found, (asset.get_path_name(), name)
    return found


def infos(g):
    return {item.node.get_name(): item for item in BP.get_node_infos(BP.find_nodes(g))}


def pin_record(pin):
    return {'name': str(pin.name), 'value': str(pin.value),
            'links': [{'node': link.node.get_name(), 'index': link.index_id} for link in pin.connected_pins]}


def graph_record(g, tokens=()):
    return {
        name: {'node': name, 'type': str(row.type_id), 'inputs': [pin_record(p) for p in row.input_pins],
               'outputs': [pin_record(p) for p in row.output_pins if p.connected_pins]}
        for name, row in infos(g).items()
        if not tokens or any(token in f'{name} {row.type_id}' for token in tokens)
    }


def normalized_value(value):
    try:
        return tuple(Decimal(piece) for piece in value.split(','))
    except InvalidOperation:
        return value


def assert_graph(actual, baseline, *, own_pins=(), additions=()):
    expected_names = {row['node'] for row in baseline} | set(additions)
    assert set(actual) == expected_names, ('Unexpected graph nodes', sorted(expected_names ^ set(actual)))
    edits = set(own_pins)
    for expected in baseline:
        name = expected['node']
        current = actual[name]
        for direction in ('inputs', 'outputs'):
            # Node category strings may be localized across cold editor launch modes.
            old_pins = {p['name']: p for p in expected[direction] if (name, p['name']) not in edits}
            new_pins = {p['name']: p for p in current[direction] if (name, p['name']) not in edits}
            assert old_pins.keys() == new_pins.keys(), (name, direction, old_pins.keys(), new_pins.keys())
            for pin_name, old_pin in old_pins.items():
                new_pin = new_pins[pin_name]
                assert normalized_value(new_pin['value']) == normalized_value(old_pin['value']), (name, old_pin, new_pin)
                assert new_pin['links'] == old_pin['links'], (name, old_pin, new_pin)


def pin_row(records, node, name, direction='inputs'):
    rows = [pin for pin in records[node][direction] if pin['name'] == name]
    assert len(rows) == 1, (node, name, direction, rows)
    return rows[0]


def sources(records, node, name):
    return [connection['node'] for connection in pin_row(records, node, name)['links']]


def properties(obj, names):
    return {name: obj.get_editor_property(name) for name in names}


def only_type(records, type_name):
    found = [name for name, item in records.items() if type_name in item['type']]
    assert len(found) <= 1, (type_name, found)
    return found[0] if found else None


def inspect_assets(cat, actions, contract, require_applied=False):
    baseline_cat, baseline_actions = contract['cat'], contract['actions']
    cat_default, actions_default = default(cat), default(actions)
    movement = cat_default.get_editor_property('CharacterMovement')
    graphs = {
        'speed': graph_record(graph(cat, SPEED_GRAPH)),
        'input': graph_record(graph(cat, 'EventGraph'), CAT_EVENT_TOKENS),
        'bell': graph_record(graph(actions, BELL_GRAPH)),
        'dispatch': graph_record(graph(actions, 'EventGraph'), ('Bell',)),
    }
    speed, bell = graphs['speed'], graphs['bell']
    resolve = only_type(speed, 'ResolveSprintIntent')
    cooldown_get = only_type(bell, 'Get' + COOLDOWN)
    components = {
        'sprint': ActorTools.get_components(cat_default, u.CatrunSprintComponent.static_class()),
        'bell': ActorTools.get_components(cat_default, u.CatrunBellComponent.static_class()),
    }
    variables = {str(name) for name in BP.list_variables(actions)}
    assert properties(cat_default, baseline_cat['defaults']) == baseline_cat['defaults']
    assert properties(movement, baseline_cat['movement_defaults']) == baseline_cat['movement_defaults']
    action_defaults = properties(actions_default, baseline_actions['defaults'])
    action_defaults['BasketPhase'] = str(action_defaults['BasketPhase'])
    # Enum repr in the saved diagnostic can differ from the enum's str form.
    assert actions_default.get_editor_property('BasketPhase') == u.CatrunBasketPhase.OUTSIDE
    assert {k: v for k, v in action_defaults.items() if k != 'BasketPhase'} == {
        k: v for k, v in baseline_actions['defaults'].items() if k != 'BasketPhase'}
    assert_graph(graphs['input'], baseline_cat['input_callers'])
    assert_graph(graphs['dispatch'], baseline_actions['event_graph'])

    if resolve:
        assert all(len(found) == 1 for found in components.values()), components
        assert_graph(speed, baseline_cat['speed_graph'], additions=(resolve,), own_pins=(
            (RUN_INTENT, 'IsRunning'), (RUN_SPEED, 'A'), (RUN_SPEED, 'bPickA')))
        assert float(pin_row(speed, RUN_SPEED, 'A')['value']) == 134.
        assert not sources(speed, RUN_SPEED, 'A')
        assert sources(speed, RUN_SPEED, 'bPickA') == [resolve]
        assert sources(speed, resolve, 'bSprintHeld') == [RUN_INTENT]
    else:
        assert not require_applied and not any(components.values()), components
        assert_graph(speed, baseline_cat['speed_graph'])
        assert digest(CAT) == baseline_cat['disk_sha256'], 'BP_Cat differs from inspected original'

    if cooldown_get:
        assert variables == set(baseline_actions['variables']) | {COOLDOWN}, variables
        assert float(actions_default.get_editor_property(COOLDOWN)) == 5.
        assert_graph(bell, baseline_actions['try_bell'], additions=(cooldown_get,), own_pins=(
            (BELL_COMPARE, 'B'), (BELL_LEGACY_LITERAL, 'ReturnValue')))
        assert sources(bell, BELL_COMPARE, 'B') == [cooldown_get]
        assert not bell[BELL_LEGACY_LITERAL]['outputs']
    else:
        assert not require_applied and variables == set(baseline_actions['variables']), variables
        assert_graph(bell, baseline_actions['try_bell'])
        assert digest(ACTIONS) == baseline_actions['disk_sha256'], 'BP_CatActions differs from inspected original'

    writers = [(g.get_name(), item.node.get_name()) for g in BP.list_graphs(cat) for item in infos(g).values()
               if str(item.type_id).endswith('|SetMaxWalkSpeed')]
    assert writers == [(SPEED_GRAPH, 'CATCTRL_ApplyMaxWalkSpeed')], writers
    animation = cat_default.get_editor_property('Mesh').get_editor_property('AnimClass')
    component_report = {role: [component.get_name() for component in found] for role, found in components.items()}
    return {'cat_applied': bool(resolve), 'bell_applied': bool(cooldown_get), 'components': component_report,
            'animation_class': animation.get_path_name() if animation else None,
            'speed_writers': writers, 'graphs': graphs}


def pin(node, name, output=False):
    found = node.find_output_pin(name) if output else node.find_input_pin(name)
    assert found and found.is_valid(), (node.get_name(), name, output)
    return found


def author_cat(cat):
    cat.modify()
    assert ActorTools.add_component(cat, u.CatrunSprintComponent.static_class(), 'SprintComponent')
    assert ActorTools.add_component(cat, u.CatrunBellComponent.static_class(), 'BellComponent')
    g = graph(cat, SPEED_GRAPH)
    n = {name: row.node for name, row in infos(g).items()}
    intent = pin(n[RUN_INTENT], 'IsRunning', True)
    pick_run = pin(n[RUN_SPEED], 'bPickA')
    assert intent.break_single_pin_link(pick_run)
    query = u.BlueprintGraphEditor.get_graph_editor(g).add_call_function_node(SPRINT_QUERY)
    assert query, SPRINT_QUERY
    query.set_node_pos(u.IntPoint(60, 280))
    # Cat is native DefaultToSelf. The authored pin carries existing IA_Run intent only.
    assert intent.try_create_connection(pin(query, 'bSprintHeld'))
    assert pin(query, 'ReturnValue', True).try_create_connection(pick_run)
    assert pin(n[RUN_SPEED], 'A').set_pin_value('134.0')
    compile_blueprint(cat, True)


def author_actions(actions):
    actions.modify()
    BP.add_variable(actions, COOLDOWN, 'float')
    BP.set_variable_category(actions, COOLDOWN, 'Bell')
    BP.set_variable_instance_editable(actions, COOLDOWN, True)
    compile_blueprint(actions, True)
    g = graph(actions, BELL_GRAPH)
    n = {name: row.node for name, row in infos(g).items()}
    comparison = pin(n[BELL_COMPARE], 'B')
    old = pin(n[BELL_LEGACY_LITERAL], 'ReturnValue', True)
    assert old.break_single_pin_link(comparison)
    getter = u.BlueprintGraphEditor.get_graph_editor(g).add_get_member_variable_node(COOLDOWN, '')
    assert getter, COOLDOWN
    getter.set_node_pos(u.IntPoint(640, 440))
    assert pin(getter, COOLDOWN, True).try_create_connection(comparison)
    compile_blueprint(actions, True)
    cdo = default(actions)
    cdo.modify()
    cdo.set_editor_property(COOLDOWN, 5.)


def main():
    option = re.search(r'-catrunplayerresources=(\w+)', u.SystemLibrary.get_command_line(), re.I)
    mode = globals().get('CATRUN_PLAYER_RESOURCES_MODE') or (option[1] if option else None) or os.environ.get(
        'CATRUN_PLAYER_RESOURCES_MODE', 'dry')
    mode = mode.lower()
    assert mode in ('dry', 'audit', 'apply', 'cold'), mode
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'mode': mode, 'saved': [], 'backups': {}}
    try:
        assert not ED.get_game_world() and not dirty(), ('Use a clean editor with PIE stopped', dirty())
        contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        report['owned_before'] = {package: digest(package) for package in (CAT, ACTIONS)}
        report['protected_before'] = {package: digest(package) for package in PROTECTED}
        if mode == 'apply':
            world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
            assert world and ED.get_editor_world() == world and not world.get_path_name().startswith('/Game/')
            assert not dirty(), dirty()
        cat, actions = load(CAT), load(ACTIONS)
        before = inspect_assets(cat, actions, contract, require_applied=mode == 'cold')
        if mode == 'apply':
            pending = {package: asset for package, asset, applied in (
                (ACTIONS, actions, before['bell_applied']), (CAT, cat, before['cat_applied'])) if not applied}
            report['backups'] = {package: backup(package) for package in pending}
            if ACTIONS in pending:
                author_actions(actions)
            if CAT in pending:
                author_cat(cat)
            after = inspect_assets(cat, actions, contract, require_applied=True)
            assert after['animation_class'] == before['animation_class']
            assert dirty() <= set(pending), ('Unexpected dirty packages', sorted(dirty()))
            for package, asset in pending.items():
                assert AS.save_loaded_asset(asset, False), package
                report['saved'].append(package)
        else:
            after = before
        report['state'] = after
        report['owned_after'] = {package: digest(package) for package in (CAT, ACTIONS)}
        report['protected_after'] = {package: digest(package) for package in PROTECTED}
        assert report['protected_after'] == report['protected_before']
        assert {package for package in report['owned_before'] if report['owned_before'][package] != report['owned_after'][package]} == set(report['saved'])
        assert not dirty(), dirty()
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        output = OUT / f'player-resources-{mode}.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('CATRUN_PLAYER_RESOURCES_REPORT', str(output), report.get('completed', False))


main()
