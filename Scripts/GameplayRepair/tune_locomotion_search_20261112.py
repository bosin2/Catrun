"""Cold commandlet inspection and targeted authoring for player speed and armor search."""

import gc
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import traceback

import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/ChaptersFlow20261112/LocomotionSearch'
CAT = '/Game/Characters/BlackCat/Blueprints/BP_Cat'
ARMOR = '/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor'
CAT_ACTIONS = '/Game/Systems/Player/Interaction/BP_CatActions'
SOUND_SETTINGS = '/Game/Systems/Sound/DA_SoundSettings'
PUZZLE_SETTINGS = '/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings'
BLEND_SPACE = '/Game/Characters/BlackCat/Final/Animations/BS_CatMove_Final'
MAIN_MENU = '/Game/Maps/MainMenu'
MAPS = tuple('/Game/Maps/' + prefix + name for prefix in ('', 'SoundTest_')
             for name in ('Tutorial', 'Stage1', 'Stage2'))
MODE = os.environ.get('CATRUN_LOCOMOTION_SEARCH_MODE', 'probe').lower()
PLAYER_MODES = {
    'sneak': ('CATCTRL_SelectSneakSpeed', 'A', 48.0, 53.0),
    'walk': ('CATCTRL_SelectRunSpeed', 'B', 74.0, 79.0),
    'run': ('CATCTRL_SelectRunSpeed', 'A', 119.0, 124.0),
}
PUSH_OFFSET = 'StatuePushLocomotionOffset'
LOOK_RATE = 'ArrivalLookPlayRate'
LOOK_TARGET = .8
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
AS = u.EditorAssetLibrary


def cdo(bp):
    return u.get_default_object(bp.generated_class())


def path(obj):
    return obj.get_path_name() if obj else None


def optional(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return None


def dirty():
    return sorted({p.get_name() for p in [*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                        *u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]})


def graph_info(bp, graph_name):
    graph = BP.get_graph(bp, graph_name)
    assert graph, (path(bp), graph_name)
    return {item.node.get_name(): item for item in BP.get_node_infos(BP.find_nodes(graph))}


def node_record(info):
    return {'type': str(info.type_id), 'inputs': {
        str(pin.name): {'value': str(pin.value), 'links': str(pin.connected_pins)}
        for pin in info.input_pins}, 'outputs': {
        str(pin.name): str(pin.connected_pins) for pin in info.output_pins}}


def cat_state(cat):
    movement = cat.get_editor_property('CharacterMovement')
    mesh = cat.get_editor_property('Mesh')
    return {'class': path(cat.get_class()), 'anim_class': path(mesh.get_editor_property('anim_class')),
            'max_walk_speed': movement.get_editor_property('max_walk_speed'),
            'max_walk_speed_crouched': movement.get_editor_property('max_walk_speed_crouched'),
            'running': optional(cat, 'IsRunning'), 'sneaking': optional(cat, 'IsSneaking'),
            'statue_push_offset': optional(cat, PUSH_OFFSET),
            'actions': [path(component.get_class()) for component in cat.get_components_by_class(
                u.CatrunBasketInteractionComponent)]}


def clip_state(clip):
    if not clip:
        return None
    return {'asset': path(clip), 'class': clip.get_class().get_name(),
            'length': clip.get_play_length(), 'rate_scale': optional(clip, 'rate_scale')}


def armor_state(armor):
    look = clip_state(armor.get_editor_property('ArrivalLookAnim'))
    rate = optional(armor, LOOK_RATE)
    return {'class': path(armor.get_class()), 'look': look, 'look_play_rate': rate,
            'look_seconds': (look['length'] / ((look['rate_scale'] or 1.) * (rate or 1.))) if look else None,
            'react': path(armor.get_editor_property('SoundReactAnim')),
            'uses_bp': armor.get_editor_property('bUseBlueprintAnimation'),
            'walk_speed': armor.get_editor_property('WalkSpeed'), 'chase_speed': armor.get_editor_property('ChaseSpeed'),
            'turn_play_rate': armor.get_editor_property('TurnPlayRate')}


def map_state(package, cat_class):
    assert not dirty() and LEVEL.load_level(package), (package, dirty())
    world = ED.get_editor_world()
    assert path(world).split('.')[0] == package and not ED.get_game_world(), path(world)
    actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
    mode = world.get_world_settings().get_editor_property('default_game_mode')
    cat_class_path = path(cat_class)
    return {'default_game_mode': path(mode),
            'default_pawn_class': path(u.get_default_object(mode).get_editor_property('default_pawn_class')) if mode else None,
            'cats': {actor.get_name(): cat_state(actor) for actor in actors if path(actor.get_class()) == cat_class_path},
            'other_possessed_characters': {actor.get_name(): path(actor.get_class()) for actor in actors
                if isinstance(actor, u.Character) and path(actor.get_class()) != cat_class_path
                and actor.get_editor_property('auto_possess_player') != u.AutoReceiveInput.DISABLED},
            'armor': {actor.get_name(): armor_state(actor) for actor in actors if isinstance(actor, u.CatrunArmor)},
            'puzzles': {actor.get_name(): {'settings': path(actor.get_editor_property('Settings')),
                'push_speed': actor.get_editor_property('Settings').get_editor_property('PushSpeed')}
                for actor in actors if isinstance(actor, u.CatrunStatuePuzzle) and actor.get_editor_property('Settings')},
            'sound_settings': {actor.get_name(): path(actor.get_editor_property('Settings'))
                for actor in actors if isinstance(actor, u.SoundGridManager)}}


def snapshot(report):
    cat = AS.load_asset(CAT)
    armor = AS.load_asset(ARMOR)
    actions = AS.load_asset(CAT_ACTIONS)
    blend_space = AS.load_asset(BLEND_SPACE)
    sound = AS.load_asset(SOUND_SETTINGS)
    puzzle = AS.load_asset(PUZZLE_SETTINGS)
    report['player_default'] = cat_state(cdo(cat))
    report['speed_graph'] = {name: node_record(info) for name, info in graph_info(cat, 'UpdateMovementSpeed').items()}
    report['player_speed_callers'] = {name: node_record(info) for name, info in graph_info(cat, 'EventGraph').items()
        if 'UpdateMovementSpeed' in str(info.type_id) or 'MaxWalkSpeed' in str(info.type_id)
        or 'Crouch' in str(info.type_id)}
    report['armor_default'] = armor_state(cdo(armor))
    report['armor_playback'] = {name: node_record(info) for name, info in graph_info(armor, 'EventGraph').items()
        if any(fragment in str(info.type_id) for fragment in ('AnimationRequested', 'PlaySlotAnimation', 'PlayMontage'))}
    report['sound_armor_speed'] = {name: sound.get_editor_property(name) for name in
        ('ArmorRunSpeedMark', 'ArmorRunSpeedBell', 'ArmorRunSpeedNoise')}
    report['actions_default'] = {'class': path(cdo(actions).get_class())}
    report['puzzle_settings'] = {name: puzzle.get_editor_property(name) for name in ('PushSpeed', 'PushAcceleration', 'PushDeceleration')}
    report['blend_space'] = {'samples': [
        {'x': sample.get_editor_property('sample_value').x, 'rate_scale': sample.get_editor_property('rate_scale')}
        for sample in blend_space.get_editor_property('sample_data')],
        'max': blend_space.get_editor_property('blend_parameters')[0].get_editor_property('max')}
    report['maps'] = {}
    for package in MAPS:
        report['maps'][package] = map_state(package, cat.generated_class())


def speed_values(records):
    values = {}
    for mode, (node, pin, _before, _target) in PLAYER_MODES.items():
        record = records[node]['inputs'][pin]
        assert record['links'] == '[]', (mode, record)
        values[mode] = float(record['value'])
    return values


def asset_file(package):
    extension = '.umap' if package in (*MAPS, MAIN_MENU) else '.uasset'
    return ROOT / 'Content' / (package.removeprefix('/Game/') + extension)


def hash_asset(package):
    with asset_file(package).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def backup_asset(package):
    source = asset_file(package)
    target = OUT / 'Backups' / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)


def check(report, baseline):
    targets = {mode: row[3] for mode, row in PLAYER_MODES.items()}
    report['effective_modes'] = speed_values(report['speed_graph'])
    assert report['effective_modes'] == targets, report['effective_modes']
    expected_graph = json.loads(json.dumps(baseline['speed_graph']))
    for node, pin, _before, target in PLAYER_MODES.values():
        expected_graph[node]['inputs'][pin]['value'] = report['speed_graph'][node]['inputs'][pin]['value']
    assert report['speed_graph'] == expected_graph, 'Other movement graph links or literals changed'
    for field in ('player_speed_callers', 'armor_playback', 'sound_armor_speed', 'puzzle_settings', 'blend_space'):
        assert report[field] == baseline[field], field

    def check_cat(current, previous):
        assert current['max_walk_speed'] == targets['walk'], current
        assert current['statue_push_offset'] == 5.0, current
        for field in ('class', 'anim_class', 'max_walk_speed_crouched', 'running', 'sneaking', 'actions'):
            assert current[field] == previous[field], (field, current)

    def check_armor(current, previous):
        assert math.isclose(current['look_play_rate'], LOOK_TARGET, rel_tol=1.e-6), current
        assert math.isclose(current['look_seconds'], previous['look_seconds'] / LOOK_TARGET, rel_tol=1.e-6), current
        for field in ('class', 'look', 'react', 'uses_bp', 'walk_speed', 'chase_speed', 'turn_play_rate'):
            assert current[field] == previous[field], (field, current)

    check_cat(report['player_default'], baseline['player_default'])
    check_armor(report['armor_default'], baseline['armor_default'])
    for package, current in report['maps'].items():
        previous = baseline['maps'][package]
        for group, validate in (('cats', check_cat), ('armor', check_armor)):
            assert current[group].keys() == previous[group].keys(), (package, group)
            for name, actor in current[group].items():
                validate(actor, previous[group][name])
        for field in ('other_possessed_characters', 'puzzles', 'sound_settings'):
            assert current[field] == previous[field], (package, field)


def author(report, baseline):
    # Blueprint reinstancing may touch placed instances in the loaded world.
    # Destroy the previous editor world before loading or compiling either Blueprint.
    world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
    gc.collect()
    u.collect_garbage()
    assert world and ED.get_editor_world() == world and not path(world).startswith('/Game/'), path(world)
    assert not dirty(), dirty()
    report['author_world'] = path(world)
    assert speed_values(baseline['speed_graph']) == {mode: row[2] for mode, row in PLAYER_MODES.items()}
    cat = AS.load_asset(CAT)
    armor = AS.load_asset(ARMOR)
    infos = graph_info(cat, 'UpdateMovementSpeed')
    current_values = speed_values({name: node_record(info) for name, info in infos.items()})
    for mode, (_node, _pin, before, target) in PLAYER_MODES.items():
        assert current_values[mode] in (before, target), (mode, current_values[mode])
    movement = cdo(cat).get_editor_property('CharacterMovement')
    assert movement.get_editor_property('max_walk_speed') in (74., 79.)
    offset = optional(cdo(cat), PUSH_OFFSET)
    assert offset in (None, 0., 5.), offset
    rate = cdo(armor).get_editor_property(LOOK_RATE)
    assert any(math.isclose(rate, allowed, rel_tol=1.e-6) for allowed in (1., LOOK_TARGET)), rate
    assert armor_state(cdo(armor))['look'] == baseline['armor_default']['look']

    changed = {}
    if offset != 5. or any(current_values[mode] != row[3] for mode, row in PLAYER_MODES.items()) \
            or movement.get_editor_property('max_walk_speed') != 79.:
        backup_asset(CAT)
        cat.modify()
        if PUSH_OFFSET not in {str(name) for name in BP.list_variables(cat)}:
            BP.add_variable(cat, PUSH_OFFSET, 'float')
            BP.set_variable_instance_editable(cat, PUSH_OFFSET, True)
        for mode, (node, name, _before, target) in PLAYER_MODES.items():
            if current_values[mode] == target:
                continue
            pin = infos[node].node.find_input_pin(name)
            assert pin and pin.set_pin_value(str(target)), (mode, name, target)
        compile_blueprint(cat, True)
        assert cat.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE
        cat_default = cdo(cat)
        cat_default.modify()
        cat_default.set_editor_property(PUSH_OFFSET, 5.)
        movement = cat_default.get_editor_property('CharacterMovement')
        movement.modify()
        movement.set_editor_property('max_walk_speed', 79.)
        assert cat_default.get_editor_property(PUSH_OFFSET) == 5.
        assert movement.get_editor_property('max_walk_speed') == 79.
        changed[CAT] = cat

    if not math.isclose(rate, LOOK_TARGET, rel_tol=1.e-6):
        backup_asset(ARMOR)
        armor.modify()
        armor_default = cdo(armor)
        armor_default.modify()
        armor_default.set_editor_property(LOOK_RATE, LOOK_TARGET)
        compile_blueprint(armor, True)
        assert armor.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE
        assert math.isclose(cdo(armor).get_editor_property(LOOK_RATE), LOOK_TARGET, rel_tol=1.e-6)
        changed[ARMOR] = armor

    assert set(dirty()) <= set(changed), ('Unexpected dirty packages', dirty())
    report['saved'] = []
    for package, asset in changed.items():
        assert AS.save_loaded_asset(asset, False), package
        report['saved'].append(package)
    assert not dirty(), dirty()


def main():
    assert MODE in ('probe', 'author', 'verify'), MODE
    assert not ED.get_game_world() and not dirty(), dirty()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'mode': MODE}
    try:
        baseline = json.loads((OUT / 'probe.json').read_text(encoding='utf8')) if MODE != 'probe' else None
        protected = (*MAPS, MAIN_MENU, CAT_ACTIONS, BLEND_SPACE, SOUND_SETTINGS, PUZZLE_SETTINGS)
        report['protected_before'] = {package: hash_asset(package) for package in protected}
        report['owned_before'] = {package: hash_asset(package) for package in (CAT, ARMOR)}
        if MODE == 'author':
            assert baseline['completed']
            author(report, baseline)
        snapshot(report)
        if MODE != 'probe':
            check(report, baseline)
        report['protected_after'] = {package: hash_asset(package) for package in protected}
        report['owned_after'] = {package: hash_asset(package) for package in (CAT, ARMOR)}
        assert report['protected_after'] == report['protected_before']
        if MODE != 'author':
            assert report['owned_after'] == report['owned_before']
        assert not ED.get_game_world() and not dirty(), dirty()
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        target = OUT / f'{MODE}.json'
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
        print('CATRUN_LOCOMOTION_SEARCH_REPORT', str(target), report.get('completed', False))


main()
