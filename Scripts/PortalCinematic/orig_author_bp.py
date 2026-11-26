"""B-01/B-10: BP_Stage2PortalArrival starts behind black and hands control back sooner. Fresh copy of main each time.

Run with -EnablePlugins=UMGToolSet,EditorToolset -culture=en (NullRHI).
"""
import hashlib
import json
import shutil
import sys
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
assert 'CompactPortal_20261125' in str(ROOT)
T = Path('C:/Users/whghk/.codex/workspaces/CompactPortal_20261125/Tools')
OUT = ROOT / 'Saved/CompactPortal'
REL = 'Content/Cinematics/Stage2/Arrival/BP_Stage2PortalArrival.uasset'
MAIN, CAND, BEFORE = Path('C:/Users/whghk/Catrun') / REL, ROOT / REL, OUT / 'Before/BP_Stage2PortalArrival.uasset'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if not BEFORE.exists():
    shutil.copy2(MAIN, BEFORE)
assert sha(BEFORE) == sha(MAIN), 'main BP changed'
shutil.copy2(BEFORE, CAND)
sys.dont_write_bytecode = True
for d in ('Scripts/Menu', 'Scripts/GameplayRepair'):
    sys.path.insert(0, str(ROOT / d))
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from menu_graph import Graph, compile_bp, literal, pin, wire

H = json.loads((T / 'shots2.json').read_text(encoding='utf-8'))['handoff']
rep = {'success': False}


def only(x):
    x = list(x)
    assert len(x) == 1, x
    return x[0]


def linked(n, name='then', out=True):
    return only(pin(n, name, out).list_connected_pins()).get_owning_node()


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
    rep['before'] = {'handoff_seconds': pin(threshold, 'B').get_pin_value(), 'finish_timer': pin(finish, 'Time').get_pin_value(),
                     'watchdog': pin(watchdog, 'Time').get_pin_value(), 'blend': pin(blend, 'BlendTime').get_pin_value(),
                     'lock_outgoing': pin(blend, 'bLockOutgoing').get_pin_value(), 'nodes': len(infos)}
    print('COMPACT_BP_BEFORE', rep['before'])
    bp.modify()
    literal(threshold, 'B', H['seconds'])
    literal(blend, 'BlendTime', H['blend'])
    literal(finish, 'Time', round(H['blend'] + .06, 3))
    # 1) readiness: hold black from BeginPlay until the sequence's own fade track takes over.
    qualified = linked(only(nodes('IsStage2PortalArrival')), 'ReturnValue')
    claim = linked(qualified)
    pin(qualified, 'then', True).break_single_pin_link(pin(claim, 'execute'))
    q = Graph(graph, 600, -900)
    pcm = q.fn('/Script/Engine.GameplayStatics:GetPlayerCameraManager', PlayerIndex='0')
    fade = q.fn('/Script/Engine.PlayerCameraManager:SetManualCameraFade', target=(pcm, 'ReturnValue'), InFadeAmount='1.0', bInFadeAudio='false')
    wire(qualified, 'then', fade, 'execute')
    wire(fade, 'then', claim, 'execute')
    q.comment('Portal arrival starts black; LS_Stage2_PortalArrival fades the portal in.')
    # 2) arrival never started (readiness aborted): remove that black. A started arrival is handled by the sequence.
    abort = only(i.node for i in infos if str(i.type_id).endswith('|Custom|AbortArrival'))
    closed = linked(abort)
    assert closed.find_input_pin('ReadinessOpen').is_valid()
    pin(abort, 'then', True).break_single_pin_link(pin(closed, 'execute'))
    q = Graph(graph, 200, 7900)
    waiting = q.branch(q.ref('ReadinessOpen'))
    pcm2 = q.fn('/Script/Engine.GameplayStatics:GetPlayerCameraManager', PlayerIndex='0')
    ok = q.fn('/Script/Engine.KismetSystemLibrary:IsValid', Object=(pcm2, 'ReturnValue'))
    alive = q.branch((ok, 'ReturnValue'))
    stop = q.fn('/Script/Engine.PlayerCameraManager:StopCameraFade', target=(pcm2, 'ReturnValue'))
    for a, ap, b in ((abort, 'then', waiting), (waiting, 'else', closed), (waiting, 'then', alive),
                     (alive, 'then', stop), (alive, 'else', closed), (stop, 'then', closed)):
        wire(a, ap, b, 'execute')
    q.comment('Never leave the readiness black on screen when the arrival cannot start.')
    # 3) AcquireExitLease refuses to start while any camera fade is active: clear it for that one call, then cover again.
    acquire = only(nodes('AcquireExitLease'))
    prior_pins = pin(acquire, 'execute').list_connected_pins()
    prior_pin = only(prior_pins)
    after_branch = linked(acquire)
    prior_pin.break_single_pin_link(pin(acquire, 'execute'))
    assert not pin(after_branch, 'else', True).list_connected_pins()
    q = Graph(graph, 2600, 700)
    pcm3 = q.fn('/Script/Engine.GameplayStatics:GetPlayerCameraManager', PlayerIndex='0')
    clear = q.fn('/Script/Engine.PlayerCameraManager:StopCameraFade', target=(pcm3, 'ReturnValue'))
    cover = q.fn('/Script/Engine.PlayerCameraManager:SetManualCameraFade', target=(pcm3, 'ReturnValue'), InFadeAmount='1.0', bInFadeAudio='false')
    assert prior_pin.try_create_connection(pin(clear, 'execute'))
    wire(clear, 'then', acquire, 'execute')
    # Success: the sequence's fade track covers from its first evaluation in this same tick, and restores 'no fade' at its end.
    wire(after_branch, 'else', cover, 'execute')
    q.comment('The exit lease rejects an active fade. Lift it for this call only; nothing renders in between.')
    # 4) A sequence fade track restores through SetManualCameraFade(0), which leaves bEnableFading set and would make every
    #    later exit lease in this world (elevator included) refuse to start. Clear it once playback has been stopped.
    reset = only(nodes('ResetBindings'))
    has_actor = linked(reset, 'execute', False)
    stopped = linked(has_actor, 'execute', False)
    pin(stopped, 'then', True).break_single_pin_link(pin(has_actor, 'execute'))
    q = Graph(graph, 4300, 7900)
    pcm4 = q.fn('/Script/Engine.GameplayStatics:GetPlayerCameraManager', PlayerIndex='0')
    ok4 = q.fn('/Script/Engine.KismetSystemLibrary:IsValid', Object=(pcm4, 'ReturnValue'))
    alive4 = q.branch((ok4, 'ReturnValue'))
    stop4 = q.fn('/Script/Engine.PlayerCameraManager:StopCameraFade', target=(pcm4, 'ReturnValue'))
    for a, ap, b in ((stopped, 'then', alive4), (alive4, 'then', stop4), (alive4, 'else', has_actor), (stop4, 'then', has_actor)):
        wire(a, ap, b, 'execute')
    q.comment('End the arrival fade state so later exit leases are accepted.')
    compile_bp(bp)
    infos = BP.get_node_infos(BP.find_nodes(graph))
    rep['after'] = {'handoff_seconds': pin(threshold, 'B').get_pin_value(), 'finish_timer': pin(finish, 'Time').get_pin_value(),
                    'blend': pin(blend, 'BlendTime').get_pin_value(), 'fade_color': pin(fade, 'Color').get_pin_value(),
                    'fade_amount': pin(fade, 'InFadeAmount').get_pin_value(), 'nodes': len(infos), 'status': str(bp.get_editor_property('status'))}
    assert linked(stopped) == alive4 and linked(alive4) == stop4 and linked(stop4) == has_actor and linked(alive4, 'else') == has_actor
    assert linked(clear) == acquire and linked(acquire) == after_branch and linked(after_branch, 'else') == cover
    assert linked(qualified) == fade and linked(fade) == claim and linked(abort) == waiting and linked(waiting, 'else') == closed
    assert u.EditorAssetLibrary.save_loaded_asset(bp, False)
    rep['dirty'] = [p.get_path_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                                *u.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not rep['dirty'], rep['dirty']
    rep['sha256'] = sha(CAND)
    rep['success'] = True
except Exception:
    rep['error'] = traceback.format_exc()
(OUT / 'author_bp.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
print('COMPACT_BP', rep['success'], rep.get('after'), str(rep.get('error'))[-900:])
