"""Patch the two menu widgets and audit their saved state in a fresh commandlet."""

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, compile_bp, editor, pin, widgets, wire

AS = unreal.EditorAssetLibrary
PACKAGES = unreal.EditorLoadingAndSavingUtils
AUDIT_SOURCE_ENV = 'CATRUN_SETTINGS_AFFORDANCES_AUDIT_SOURCE'
SETTINGS = '/Game/UI/Settings/WBP_Setting'
MENU = '/Game/UI/WBP_MainMenu'
NAV_FUNCTION = '/Script/Catrun.CatrunSettingsSubsystem.IsNavigationFocused'
NAV_TITLE = '|IsNavigationFocused'
HOVERED = 'Widget|IsHovered'
FOCUSED = 'Widget|HasKeyboardFocus'
DESCENDANTS = 'Widget|HasUserFocusedDescendants'
OWNER = 'Widget|GetOwningPlayer'
OR = 'Math|Boolean|ORBoolean'
AND = 'Math|Boolean|ANDBoolean'
FILL = unreal.VerticalAlignment.V_ALIGN_FILL
CENTER = unreal.VerticalAlignment.V_ALIGN_CENTER

SETTINGS_CONTROLS = {
    'ScreenCategoryButton', 'AudioCategoryButton', 'ControlsCategoryButton', 'DeveloperCategoryButton',
    'DefaultsButton', 'RestartButton', 'MainMenuButton', 'ApplyButton', 'CloseButton',
    'KeyForward', 'KeyBack', 'KeyLeft', 'KeyRight', 'KeyRun', 'KeySneak', 'KeyBell', 'KeyInteract',
}
MENU_CONTROLS = {'StartButton', 'ContinueButton', 'OptionButton', 'EndButton'}
TARGETS = (
    (SETTINGS, 'UpdateSettingsAffordances', SETTINGS_CONTROLS),
    (MENU, 'UpdateMenuAffordances', MENU_CONTROLS),
)
PROTECTED = (
    'Content/Blueprints/BP_TutorialIntro.uasset',
    'Content/UI/Tutorial/WBP_Tutorial_KeyHint.uasset',
    'Content/Cinematics/LS_Tutorial.uasset',
    'Content/Cinematics/Transitions/LS_Tutorial_StairDescent.uasset',
    'Content/Cinematics/Stage1/Portal/LS_Stage1_PortalExit.uasset',
    'Content/Cinematics/Stage1/Portal/M_Stage1PortalBlue.uasset',
    'Content/Environment/UI/CatJelly.uasset',
    'Content/Tutorial.umap',
    *(f'Content/Maps/{name}.umap' for name in (
        'MainMenu', 'Tutorial', 'SoundTest_Tutorial', 'Stage1', 'SoundTest_Stage1', 'Stage2', 'SoundTest_Stage2',
    )),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_file(path):
    return ROOT / 'Content' / (path.removeprefix('/Game/') + '.uasset')


def protected_hashes():
    return {relative: digest(ROOT / relative) for relative in PROTECTED}


def no_pie():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert subsystem is not None and not subsystem.get_game_world(), 'Close PIE before patching menu assets'


def assert_clean(path):
    dirty = {package.get_name() for package in PACKAGES.get_dirty_content_packages()}
    assert path not in dirty, ('Unexpected unsaved target package', path)


def pin_key(graph_pin):
    return graph_pin.get_owning_node().get_name(), str(graph_pin.get_pin_name())


def linked(graph_pin, expected_pin=None):
    links = list(graph_pin.list_connected_pins())
    assert len(links) == 1, (pin_key(graph_pin), [pin_key(other) for other in links])
    other = links[0]
    if expected_pin is not None:
        assert str(other.get_pin_name()) == expected_pin, (pin_key(graph_pin), pin_key(other), expected_pin)
    return other


def source(node, input_name, output_name='ReturnValue'):
    return linked(pin(node, input_name), output_name).get_owning_node()


def assert_pure(node):
    assert all(str(graph_pin.get_pin_type_display_string()) != 'Exec'
               for graph_pin in node.list_all_pins()), ('Unexpected execution pin', node.get_name())


def inspect_graph(graph, controls):
    nodes = BP.find_nodes(graph)
    types = {info.node.get_name(): info.type_id for info in BP.get_node_infos(nodes)}
    counts = Counter(types.values())
    lanes = {}
    for hovered in nodes:
        if types[hovered.get_name()] != HOVERED:
            continue
        getter_pin = linked(pin(hovered, 'self'))
        control = str(getter_pin.get_pin_name())
        assert control in controls and control not in lanes, (graph.get_name(), control)
        assert types[getter_pin.get_owning_node().get_name()] == '|Get' + control, control

        first = linked(pin(hovered, 'ReturnValue', True), 'A').get_owning_node()
        assert types[first.get_name()] == OR and source(first, 'A') == hovered, control
        focus = source(first, 'B')
        focus_type = types[focus.get_name()]
        legacy = focus_type == FOCUSED
        assert legacy or focus_type.endswith(NAV_TITLE), (control, focus_type)
        assert_pure(focus)
        assert pin_key(linked(pin(focus, 'ReturnValue', True), 'B')) == (first.get_name(), 'B'), control
        focus_getter = source(focus, 'self' if legacy else 'Widget', control)
        assert types[focus_getter.get_name()] == '|Get' + control, control
        assert pin_key(linked(pin(focus_getter, control, True))) == (
            focus.get_name(), 'self' if legacy else 'Widget',
        ), control

        active = first
        removals = []
        if legacy:
            merge = linked(pin(first, 'ReturnValue', True), 'A').get_owning_node()
            assert types[merge.get_name()] == OR and source(merge, 'A') == first, control
            child = source(merge, 'B')
            assert types[child.get_name()] == DESCENDANTS, control
            assert pin_key(linked(pin(child, 'ReturnValue', True), 'B')) == (merge.get_name(), 'B'), control
            child_getter = source(child, 'self', control)
            assert types[child_getter.get_name()] == '|Get' + control, control
            assert pin_key(linked(pin(child_getter, control, True), 'self')) == (child.get_name(), 'self'), control
            owner = source(child, 'PlayerController')
            assert types[owner.get_name()] == OWNER and not pin(owner, 'self').list_connected_pins(), control
            assert pin_key(linked(pin(owner, 'ReturnValue', True), 'PlayerController')) == (
                child.get_name(), 'PlayerController',
            ), control
            active = merge
            removals = [focus, child, child_getter, owner, merge]

        consumer = linked(pin(active, 'ReturnValue', True), 'A').get_owning_node()
        assert source(consumer, 'A') == active, control
        current = consumer
        if control.startswith('Key'):
            selecting = source(current, 'B')
            assert types[current.get_name()] == OR and types[selecting.get_name()] == 'Widget|GetIsSelectingKey', control
            assert types[source(selecting, 'self', control).get_name()] == '|Get' + control, control
            current = linked(pin(current, 'ReturnValue', True), 'A').get_owning_node()
        if control.endswith('CategoryButton'):
            selected = source(current, 'B')
            assert types[current.get_name()] == OR and types[selected.get_name()] == 'Math|Integer|Equal(Integer)', control
            assert types[source(selected, 'A', 'SettingsCategoryIndex').get_name()] == '|GetSettingsCategoryIndex', control
            current = linked(pin(current, 'ReturnValue', True), 'A').get_owning_node()
        enabled = source(current, 'B')
        assert types[current.get_name()] == AND and types[enabled.get_name()] == 'Widget|GetIsEnabled', control
        assert types[source(enabled, 'self', control).get_name()] == '|Get' + control, control
        root_check = linked(pin(current, 'ReturnValue', True), 'A').get_owning_node()
        root_enabled = source(root_check, 'B')
        assert types[root_check.get_name()] == AND and types[root_enabled.get_name()] == 'Widget|GetIsEnabled', control
        assert not pin(root_enabled, 'self').list_connected_pins(), control
        branch = linked(pin(root_check, 'ReturnValue', True), 'Condition').get_owning_node()
        assert types[branch.get_name()] == 'Utilities|FlowControl|Branch', control
        lanes[control] = (focus, focus_getter, first, consumer, removals)

    assert lanes.keys() == controls, (graph.get_name(), sorted(lanes), sorted(controls))
    legacy_count = sum(bool(lane[-1]) for lane in lanes.values())
    assert legacy_count in (0, len(controls)), ('Partially edited function', graph.get_name(), legacy_count)
    assert counts[HOVERED] == len(controls), (graph.get_name(), counts[HOVERED])
    assert all(counts[name] == legacy_count for name in (FOCUSED, DESCENDANTS, OWNER)), (graph.get_name(), counts)
    assert sum(count for name, count in counts.items() if name.endswith(NAV_TITLE)) == len(controls) - legacy_count
    return lanes


def graph_snapshot(graph, omitted=(), rewired=()):
    """Compare every surviving node and connection except the two rewired inputs."""
    snapshot = {}
    for info in BP.get_node_infos(BP.find_nodes(graph)):
        name = info.node.get_name()
        if name in omitted:
            continue
        pins = []
        for graph_pin in info.node.list_all_pins():
            key = pin_key(graph_pin)
            links = sorted(pin_key(other) for other in graph_pin.list_connected_pins()
                           if pin_key(other)[0] not in omitted and pin_key(other) not in rewired)
            pins.append((str(graph_pin.get_pin_direction()), key[1], str(graph_pin.get_pin_value()),
                         [] if key in rewired else links))
        snapshot[name] = (info.type_id, info.position.x, info.position.y, pins)
    return snapshot


def snapshot_digest(snapshot):
    data = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def patch_graph(graph, lanes):
    legacy = {control: lane for control, lane in lanes.items() if lane[-1]}
    if not legacy:
        return []

    graph_editor = editor(graph)
    removed = [node for lane in legacy.values() for node in lane[-1]]
    removed_names = {node.get_name() for node in removed}
    assert len(removed_names) == 5 * len(legacy), (graph.get_name(), 'Shared focus-only nodes')
    rewired = {(node.get_name(), name) for _, _, first, consumer, _ in legacy.values()
               for node, name in ((first, 'B'), (consumer, 'A'))}
    before = graph_snapshot(graph, removed_names, rewired)

    helpers = {}
    for control, (focus, _, _, _, _) in legacy.items():
        helper = graph_editor.add_call_function_node(NAV_FUNCTION)
        assert helper is not None, ('Native Blueprint function is unavailable', NAV_FUNCTION)
        helper.set_node_pos(focus.get_node_pos())
        pin(helper, 'Widget')
        pin(helper, 'ReturnValue', True)
        assert_pure(helper)
        helpers[control] = helper

    graph_editor.remove_nodes(removed)
    for control, (_, getter, first, consumer, _) in legacy.items():
        helper = helpers[control]
        wire(getter, control, helper, 'Widget')
        wire(helper, 'ReturnValue', first, 'B')
        wire(first, 'ReturnValue', consumer, 'A')

    added_names = {node.get_name() for node in helpers.values()}
    assert before == graph_snapshot(graph, added_names, rewired), (graph.get_name(), 'Unrelated node or pin changed')
    return sorted(legacy)


def paw_state(blueprint):
    all_widgets = widgets(blueprint)
    heading, bounds, paw = (all_widgets[name] for name in ('SettingsHeading', 'SettingsPawBounds', 'SettingsPaw'))
    outer, inner = (widget.get_editor_property('slot') for widget in (bounds, paw))
    assert isinstance(heading, unreal.HorizontalBox) and isinstance(bounds, unreal.SizeBox)
    assert isinstance(paw, unreal.Image) and bounds.get_parent() == heading and paw.get_parent() == bounds
    assert isinstance(outer, unreal.HorizontalBoxSlot) and isinstance(inner, unreal.SizeBoxSlot)
    width = bounds.get_editor_property('width_override')
    height = bounds.get_editor_property('height_override')
    assert (width, height) == (36.0, 36.0), (width, height)
    assert bounds.get_editor_property('override_width_override') and bounds.get_editor_property('override_height_override')
    outer_alignment = outer.get_editor_property('vertical_alignment')
    inner_alignment = inner.get_editor_property('vertical_alignment')
    assert outer_alignment in (FILL, CENTER) and inner_alignment == FILL, (outer_alignment, inner_alignment)
    brush = paw.get_editor_property('brush')
    texture = brush.get_editor_property('resource_object')
    assert texture and texture.get_path_name() == '/Game/Environment/UI/CatJelly.CatJelly', texture
    color = paw.get_editor_property('color_and_opacity')
    return outer, {'outer_alignment': str(outer_alignment), 'inner_alignment': str(inner_alignment),
                   'size': [width, height], 'texture': texture.get_path_name(),
                   'tint': [color.r, color.g, color.b, color.a]}


def save_patch(run, report):
    no_pie()
    before_protected = protected_hashes()
    report['protected_before_sha256'] = before_protected
    blueprints = {}
    prepared = {}
    for path, function, controls in TARGETS:
        assert_clean(path)
        blueprint = AS.load_asset(path)
        assert blueprint and blueprint.get_outermost().get_name() == path, path
        assert_clean(path)
        graph = BP.get_graph(blueprint, function)
        assert graph and graph.get_name() == function, (path, function)
        prepared[path] = inspect_graph(graph, controls)
        blueprints[path] = blueprint
        original = asset_file(path)
        backup = run / 'Before' / original.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, backup)
        before_sha = digest(original)
        assert digest(backup) == before_sha, path
        report['assets'][path] = {'before_sha256': before_sha, 'backup': str(backup), 'graph': function}

    outer, report['paw_before'] = paw_state(blueprints[SETTINGS])
    paw_changed = outer.get_editor_property('vertical_alignment') != CENTER
    if paw_changed:
        outer.set_editor_property('vertical_alignment', CENTER)

    changed_paths = set()
    for path, function, controls in TARGETS:
        blueprint = blueprints[path]
        graph = BP.get_graph(blueprint, function)
        changed_controls = patch_graph(graph, prepared[path])
        report['assets'][path]['changed_controls'] = changed_controls
        post_patch = graph_snapshot(graph)
        if changed_controls or (path == SETTINGS and paw_changed):
            changed_paths.add(path)
            compile_bp(blueprint)
        assert blueprint.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE, path
        graph = BP.get_graph(blueprint, function)
        lanes = inspect_graph(graph, controls)
        assert all(not lane[-1] for lane in lanes.values()), path
        assert graph_snapshot(graph) == post_patch, (path, 'Graph changed during compilation')
        report['assets'][path].update(graph_sha256=snapshot_digest(post_patch),
                                      node_count=len(post_patch), controls=sorted(lanes))

    expected_paw = dict(report['paw_before'], outer_alignment=str(CENTER))
    assert paw_state(blueprints[SETTINGS])[1] == expected_paw, 'Unexpected paw property change'
    report['paw_expected'] = expected_paw
    assert protected_hashes() == before_protected, 'Protected package changed before save'
    for path, _, _ in TARGETS:
        assert digest(asset_file(path)) == report['assets'][path]['before_sha256'], (path, 'Disk changed before save')
    no_pie()
    for path, _, _ in TARGETS:
        if path in changed_paths:
            assert AS.save_loaded_asset(blueprints[path], only_if_is_dirty=False), path
            report['saved'].append(path)
        assert_clean(path)
        after_sha = digest(asset_file(path))
        assert (after_sha != report['assets'][path]['before_sha256']) == (path in changed_paths), path
        report['assets'][path]['after_sha256'] = after_sha

    no_pie()
    report['protected_after_sha256'] = protected_hashes()
    assert report['protected_after_sha256'] == before_protected, 'Protected package changed'


def cold_audit(source_path, report):
    no_pie()
    report['source'] = str(source_path)
    manifest = json.loads(source_path.read_text(encoding='utf-8'))
    assert manifest['mode'] == 'save' and manifest['status'] == 'awaiting_cold_audit', source_path
    before_protected = protected_hashes()
    report['protected_before_sha256'] = before_protected
    assert before_protected == manifest['protected_after_sha256'], 'Protected package changed since save'

    for path, function, controls in TARGETS:
        expected = manifest['assets'][path]
        assert expected['graph'] == function and expected['controls'] == sorted(controls), path
        assert digest(asset_file(path)) == expected['after_sha256'], (path, 'Saved package hash differs')
        assert_clean(path)
        persisted = AS.load_asset(path)
        assert persisted and persisted.get_outermost().get_name() == path, path
        graph = BP.get_graph(persisted, function)
        lanes = inspect_graph(graph, controls)
        assert all(not lane[-1] for lane in lanes.values()), path
        snapshot = graph_snapshot(graph)
        assert snapshot_digest(snapshot) == expected['graph_sha256'], (path, 'Saved graph differs')
        assert len(snapshot) == expected['node_count'], path
        compile_bp(persisted)
        assert graph_snapshot(BP.get_graph(persisted, function)) == snapshot, (path, 'Graph changed during compilation')
        assert digest(asset_file(path)) == expected['after_sha256'], (path, 'Package changed during audit')
        report['assets'][path] = {'sha256': expected['after_sha256'], 'graph_sha256': expected['graph_sha256'],
                                  'controls': sorted(lanes), 'node_count': len(snapshot),
                                  'compile_status': str(persisted.get_editor_property('status'))}
        if path == SETTINGS:
            report['paw_loaded'] = paw_state(persisted)[1]
            assert report['paw_loaded'] == manifest['paw_expected'], 'Saved paw differs'

    no_pie()
    report['protected_after_sha256'] = protected_hashes()
    assert report['protected_after_sha256'] == before_protected, 'Protected package changed'


if __name__ == '__main__':
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ')
    run_dir = ROOT / 'Saved/GameplayRepair20261105/SettingsAffordances20261111' / stamp
    run_dir.mkdir(parents=True)
    audit_path = run_dir / 'audit.json'
    source_path = os.environ.get(AUDIT_SOURCE_ENV)
    mode = 'cold_audit' if source_path else 'save'
    report = {'mode': mode, 'status': 'started', 'assets': {}, 'saved': []}
    try:
        if source_path:
            cold_audit(Path(source_path).resolve(), report)
            report['status'] = 'complete'
        else:
            save_patch(run_dir, report)
            report['status'] = 'awaiting_cold_audit'
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
        raise
    finally:
        audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = 'FAILED' if report['status'] == 'failed' else 'COMPLETE'
        unreal.log(f'CATRUN_MENU_AFFORDANCES_{mode.upper()}_{result} {audit_path}')
