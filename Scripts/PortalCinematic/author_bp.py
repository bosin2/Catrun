"""BP_Stage2PortalArrival: move the sequence hand-off to the new slower arrival (edits the current main BP in place).

Only four pin literals change: hand-off threshold (Sequencer seconds), view blend, finish timer, active-play watchdog.
Graph wiring (readiness black, fade clearing, lease handling) from the 2026-11-26 delivery is left as is.
Needs -EnablePlugins=UMGToolSet,EditorToolset.
"""
import hashlib
import json
import sys
import traceback
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
ROOT = Path(u.Paths.project_dir()).resolve()
for d in ('Scripts/Menu', 'Scripts/GameplayRepair'):
    if str(ROOT / d) not in sys.path:
        sys.path.insert(0, str(ROOT / d))
sys.dont_write_bytecode = True
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from menu_graph import compile_bp, literal, pin

OUT = ROOT / 'Saved/PortalCinematic'
REL = 'Content/Cinematics/Stage2/Arrival/BP_Stage2PortalArrival.uasset'
H = json.loads((HERE / 'shots_s2.json').read_text(encoding='utf-8'))['handoff']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rep = {'success': False, 'sha_before': sha(ROOT / REL)}


def only(x):
    x = list(x)
    assert len(x) == 1, x
    return x[0]


try:
    bp = u.load_asset('/Game/Cinematics/Stage2/Arrival/BP_Stage2PortalArrival')
    graph = BP.get_graph(bp, 'EventGraph')
    infos = BP.get_node_infos(BP.find_nodes(graph))

    def nodes(suffix):
        return [i.node for i in infos if str(i.type_id).endswith('|' + suffix)]

    def timer(name, test):
        return only(n for n in nodes('SetTimerbyFunctionName')
                    if str(pin(n, 'FunctionName').get_pin_value()).strip('"') == name and test(float(pin(n, 'Time').get_pin_value())))
    threshold = only(i.node for i in infos if str(i.type_id).endswith('float>=float') and float(pin(i.node, 'B').get_pin_value()) > 1.)
    finish = timer('FinishArrival', lambda v: True)
    watchdog = timer('AbortArrival', lambda v: v > 2.)
    blend = only(n for n in nodes('SetViewTargetWithBlend') if float(pin(n, 'BlendTime').get_pin_value()) > 0)
    read = lambda: {'handoff_seconds': pin(threshold, 'B').get_pin_value(), 'finish_timer': pin(finish, 'Time').get_pin_value(),
                    'watchdog': pin(watchdog, 'Time').get_pin_value(), 'blend': pin(blend, 'BlendTime').get_pin_value()}
    rep['before'] = read()
    print('PORTALCINE_BP_BEFORE', rep['before'])
    assert float(rep['before']['handoff_seconds']) in (9.6, H['seconds']), rep['before']
    assert H['watchdog'] > H['seconds'] + H['blend'] + 2. - 1e-6
    bp.modify()
    literal(threshold, 'B', H['seconds'])
    literal(blend, 'BlendTime', H['blend'])
    literal(finish, 'Time', round(H['blend'] + .06, 3))
    literal(watchdog, 'Time', H['watchdog'])
    compile_bp(bp)
    rep['after'] = read()
    rep['nodes'] = len(BP.get_node_infos(BP.find_nodes(graph)))
    assert rep['nodes'] == len(infos)
    assert u.EditorAssetLibrary.save_loaded_asset(bp, False)
    rep['dirty'] = [p.get_path_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                                *u.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not rep['dirty'], rep['dirty']
    rep['sha_after'] = sha(ROOT / REL)
    rep['success'] = True
except Exception:
    rep['error'] = traceback.format_exc()
(OUT / 'author_bp.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
print('PORTALCINE_BP', rep['success'], rep.get('after'), str(rep.get('error'))[-900:])
if not rep['success']:
    raise RuntimeError('BP retime failed')
