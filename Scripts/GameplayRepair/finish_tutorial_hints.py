"""RETIRED: user requires the original initial-game transient hint flow.

Do not run this former author/audit pipeline. Its two asset writes were reverted
to the verified immediately-before bytes in TutorialHintRevert01. Preserve the
original intro, key hint animation/dismissal, retry and stair sequence.
"""
raise RuntimeError('Retired by user: preserve original tutorial hint flow; do not reconnect onboarding.')
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import Graph, audit, compile_bp, editor, entry, pin, ui, widgets, wire

HINT = '/Game/UI/Tutorial/WBP_Tutorial_KeyHint'
INTRO = '/Game/Blueprints/BP_TutorialIntro'
AS = unreal.EditorAssetLibrary
OUT = ROOT / 'Saved/GameplayRepair20261105/TutorialHints' / datetime.datetime.now().strftime('%H%M%S-%f')
OUT.mkdir(parents=True, exist_ok=False)
AUDIT = '-catrunhintaudit' in unreal.SystemLibrary.get_command_line().lower()
REPORT = {'completed': False, 'audit_only': AUDIT, 'process_id': os.getpid(), 'saved': [], 'errors': [], 'backups': []}
LABELS = {'KeyLabel_' + group + '_' + key: slot for group in ('Move', 'Sneak', 'Run')
          for key, slot in (('W', 'Forward'), ('A', 'Left'), ('S', 'Back'), ('D', 'Right'))}
LABELS.update(KeyLabel_Sneak_Modifier='Sneak', KeyLabel_Run_Modifier='Run', KeyLabel_Bell='Bell', KeyLabel_Hide='Interact')


def dirty():
    return sorted(p.get_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def disk(package):
    return ROOT / ('Content/' + package[6:] + '.uasset')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persist():
    (OUT / 'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def graph_snapshot(bp):
    return [{'name': g.get_name(), 'nodes': [
        {'name': n.node.get_name(), 'type': n.type_id,
         'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in n.input_pins],
         'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in n.output_pins]}
        for n in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]


def after(node, next_node):
    """Insert one event call without removing an existing animation/delay chain."""
    out = pin(node, 'then', True)
    old = list(out.list_connected_pins())
    for p in old:
        out.break_single_pin_link(p)
    wire(node, 'then', next_node, 'execute')
    for p in old:
        assert pin(next_node, 'then', True).try_create_connection(p)


def unique(graph, suffix):
    nodes = [i.node for i in BP.get_node_infos(BP.find_nodes(graph)) if i.type_id.endswith('|' + suffix)]
    assert len(nodes) == 1, (suffix, [n.get_name() for n in nodes])
    return nodes[0]


def inspect(hint, intro):
    rows = graph_snapshot(hint)
    generated = next(g for g in rows if g['name'] == 'RefreshEffectiveHintKeys')
    calls = [n for n in generated['nodes'] if n['type'].endswith('|GetEffectiveKeyLabel')]
    assert len(calls) == len(LABELS)
    assert {p['value'] for n in calls for p in n['inputs'] if p['name'] == 'Slot'} == set(LABELS.values())
    assert all(widgets(hint)[name] for name in LABELS)
    intro_rows = graph_snapshot(intro)
    functions = [n for g in intro_rows for n in g['nodes']]
    assert sum(n['type'].endswith('|ShouldShowTutorialControls') for n in functions) == 1
    assert sum(n['type'].endswith('|MarkTutorialOnboardingCompleted') for n in functions) == 1
    assert sum(n['type'].endswith('|CreateWidget') for n in functions) == 1
    return {'hint': audit(hint), 'intro_graphs': intro_rows,
            'status': {p: str(b.get_editor_property('status')) for p, b in ((HINT, hint), (INTRO, intro))}}


def main():
    command = unreal.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and (AUDIT or '-catrunhintauthor' in command)
    assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() and not dirty()
    hint, intro = AS.load_asset(HINT), AS.load_asset(INTRO)
    assert hint and intro
    REPORT['before_hashes'] = {p: sha(disk(p)) for p in (HINT, INTRO)}
    if AUDIT:
        REPORT['after'] = inspect(hint, intro)
        assert all(b.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE for b in (hint, intro))
        assert REPORT['before_hashes'] == {p: sha(disk(p)) for p in (HINT, INTRO)}
        assert not dirty()
        REPORT['completed'] = True
        persist()
        print('CATRUN_HINT_AUDITED', str(OUT / 'report.json'))
        return
    assert not any(g.get_name() == 'RefreshEffectiveHintKeys' for g in BP.list_graphs(hint)), 'Already authored: run audit'
    for p in (HINT, INTRO):
        source = disk(p)
        target = OUT / 'Before' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert sha(source) == sha(target)
        REPORT['backups'].append({'package': p, 'sha256': sha(source)})
    REPORT['before'] = {'hint': audit(hint), 'intro_graphs': graph_snapshot(intro)}
    persist()
    old_widgets = {(w['name'], w['type'], w['parent']) for w in REPORT['before']['hint']['widgets']}
    ws = widgets(hint)
    for name in LABELS:
        assert isinstance(ws[name], unreal.TextBlock)
        ui('ToggleWidgetAsVariable', hint, ws[name], True)
    compile_bp(hint)
    q = Graph(BP.add_function_graph(hint, 'RefreshEffectiveHintKeys'))
    last = entry(q)
    for name, slot in LABELS.items():
        label = q.fn('/Script/Catrun.CatrunInputBindings.GetEffectiveKeyLabel', Slot=slot)
        set_text = q.fn('/Script/UMG.TextBlock.SetText', target=q.ref(name), InText=(label, 'ReturnValue'))
        q.chain(last, set_text)
        last = set_text
    eg = BP.get_graph(hint, 'EventGraph')
    construct = unique(eg, 'EventConstruct')
    after(construct, Graph(eg, 2400, 1600).fn('RefreshEffectiveHintKeys'))
    # Reuse the original hint creation and its original animation/dismissal behavior.
    eg = BP.get_graph(intro, 'EventGraph')
    add_viewport = unique(eg, 'AddToViewport')
    create = unique(eg, 'CreateWidget')
    restore = unique(eg, 'RestorePlayableStart')
    assert not pin(add_viewport, 'then', True).list_connected_pins()
    assert not pin(restore, 'then', True).list_connected_pins()
    q = Graph(eg, 8000, 4000)
    shown = q.fn('/Script/UMG.Widget.IsInViewport', target=(create, 'ReturnValue'))
    branch = q.branch((shown, 'ReturnValue'))
    mark = q.fn('/Script/Catrun.CatrunLevelFlowLibrary.MarkTutorialOnboardingCompleted')
    q.chain(add_viewport, branch)
    wire(branch, 'then', mark, 'execute')
    q = Graph(eg, 8000, 4800)
    restored = q.branch((restore, 'ReturnValue'))
    query = q.fn('/Script/Catrun.CatrunLevelFlowLibrary.ShouldShowTutorialControls')
    needed = q.branch((query, 'ReturnValue'))
    q.chain(restore, restored)
    wire(restored, 'then', query, 'execute')
    q.chain(query, needed)
    wire(needed, 'then', create, 'execute')
    compile_bp(hint)
    compile_bp(intro)
    REPORT['after'] = inspect(hint, intro)
    assert old_widgets == {(w['name'], w['type'], w['parent']) for w in REPORT['after']['hint']['widgets']}
    for before_g in REPORT['before']['intro_graphs']:
        current = next(g for g in REPORT['after']['intro_graphs'] if g['name'] == before_g['name'])
        assert {(n['name'], n['type']) for n in before_g['nodes']} <= {(n['name'], n['type']) for n in current['nodes']}
    assert set(dirty()) <= {HINT, INTRO}, ('Unrelated dirty package', dirty())
    persist()
    for p, bp in ((HINT, hint), (INTRO, intro)):
        assert AS.save_loaded_asset(bp, False)
        REPORT['saved'].append(p)
    assert not dirty()
    REPORT['after_hashes'] = {p: sha(disk(p)) for p in (HINT, INTRO)}
    REPORT['completed'] = True
    persist()
    print('CATRUN_HINT_SAVED', str(OUT / 'report.json'))


try:
    main()
except Exception:
    REPORT['errors'].append(traceback.format_exc())
    REPORT['dirty_on_abort'] = dirty()
    persist()
    raise
