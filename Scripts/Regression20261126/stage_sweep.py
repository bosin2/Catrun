"""정식 맵 5개를 실제 PIE로 순회하며 시작·입력·순찰·포획·재시작·시간초과·메뉴 복귀를 확인한다.

pie_harness.py 를 통해서만 실행한다. 맵·에셋·설정·사용자 저장을 쓰지 않는다.
- 포획은 가장 가까운 갑옷을 고양이 옆 안전한 바닥에 놓고 실제 인지/포획이 일어나는지 본다(배치는 fixture).
- 시간초과는 메모리 안의 제한시간만 6초로 줄이고 끝나면 되돌린다. Config 는 저장하지 않는다.
- 한 단계가 실패해도 기록하고 다음 단계/맵으로 넘어간다.
"""
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS = u.GameplayStatics
FLOW = u.CatrunLevelFlowLibrary
SYS = u.load_object(None, '/Script/Engine.Default__SubsystemBlueprintLibrary')
WBL = u.WidgetLibrary
OUT = Path(u.Paths.project_dir()) / 'Saved/StageSweep'
OUT.mkdir(parents=True, exist_ok=True)
MAPS = os.environ.get('CATRUN_SWEEP_MAPS', 'MainMenu,Tutorial,Stage1,Stage2,Stage3').split(',')
BUDGET = {'Stage1': 'Stage1BudgetSeconds', 'Stage2': 'Stage2BudgetSeconds', 'Stage3': 'Stage3BudgetSeconds'}
R = {'scope': __doc__, 'command_line': u.SystemLibrary.get_command_line(), 'stages': {}, 'checks': [],
     'started': time.time(), 'success': False}
S = {'queue': list(MAPS), 'phase': 'idle', 'map': None, 'changed': time.monotonic(), 'ctx': {}}


def persist():
    (OUT / 'report.json').write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def check(name, ok, detail=None, skipped=False):
    R['checks'].append({'stage': S['map'], 'name': '%s: %s' % (S['map'], name), 'passed': bool(ok),
                        'skipped': skipped, 'detail': detail})
    persist()
    return ok


def skip(name, why):
    check(name, True, why, skipped=True)


def phase(name):
    S['phase'] = name
    S['changed'] = time.monotonic()
    S['game0'] = None
    u.log('REGRESSION_SWEEP %s %s' % (S['map'], name))


def xyz(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def all_of(w, cls):
    return list(GS.get_all_actors_of_class(w, cls))


def reflected(w, cls):
    return SYS.call_method('GetWorldSubsystem', args=(w, cls.static_class()))


def clock(w):
    flow = reflected(w, u.CatrunLevelFlowSubsystem)
    if not flow:
        return None
    c = flow.get_stage_clock_state()
    return {n: c.get_editor_property(n) for n in ('RemainingSeconds', 'BudgetSeconds', 'bRunning', 'bTimed')}


def widgets(w):
    rows = []
    for x in WBL.get_all_widgets_of_class(w, u.UserWidget, True):
        rows.append({'class': x.get_class().get_name(), 'visibility': x.get_visibility().name,
                     'in_viewport': x.is_in_viewport()})
    return rows


def texts(w):
    rows = []
    for t in u.ObjectIterator(u.TextBlock):
        try:
            if t.get_world() == w and t.is_visible() and str(t.get_text()):
                rows.append('%s=%s' % (t.get_name(), t.get_text()))
        except Exception:
            pass
    return sorted(set(rows))[:80]


def playable(w, pc):
    return not pc.is_move_input_ignored() and not FLOW.should_hide_gameplay_hud(w)


def enemies(w):
    return {a.get_actor_label(): a for a in all_of(w, u.CatrunArmor) + all_of(w, u.CatrunCandle)}


def capturing(w):
    for a in all_of(w, u.CatrunArmor):
        c = a.get_component_by_class(u.CatrunCapturePresentationComponent)
        if c and c.is_capturing():
            return {'armor': a.get_actor_label(), 'phase': str(c.get_editor_property('Phase'))}
    return None


def place_armor(w, cat):
    """기존 verify_gameplay_expansion_pie_20261125.py 와 같은 배치 방식."""
    here = cat.get_actor_location()
    armors = sorted(all_of(w, u.CatrunArmor), key=lambda a: (a.get_actor_location() - here).length())
    for armor in armors:
        cap = armor.get_component_by_class(u.CapsuleComponent)
        for x, y in ((72, 0), (-72, 0), (0, 72), (0, -72), (60, 60), (-60, 60), (60, -60), (-60, -60)):
            p = here + u.Vector(x, y, 0)
            ignored = [armor, cat]
            hit = u.SystemLibrary.capsule_trace_single_by_profile(
                w, p + u.Vector(0, 0, 190), p - u.Vector(0, 0, 160), cap.get_scaled_capsule_radius(),
                cap.get_scaled_capsule_half_height(), 'Pawn', False, ignored, u.DrawDebugTrace.NONE, False)
            if not hit:
                continue
            f = hit.to_dict()
            floor_z = here.z - cat.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height()
            if f['initial_overlap'] or f['impact_normal'].z < .7 or abs(f['impact_point'].z - floor_z) > 20:
                continue
            target = f['location'] + u.Vector(0, 0, 2.)
            if u.SystemLibrary.line_trace_single(w, u.Vector(target.x, target.y, here.z), here,
                                                 u.TraceTypeQuery.ECC_VISIBILITY, False, ignored,
                                                 u.DrawDebugTrace.NONE, False):
                continue
            armor.set_actor_location_and_rotation(target, u.Rotator(yaw=math.degrees(math.atan2(-y, -x))), False, True)
            return {'armor': armor.get_actor_label(), 'placed': xyz(armor.get_actor_location()), 'cat': xyz(here)}
    return None


def static_audit(w):
    """저장된 맵의 정적 상태: 빈 메시, 빈 재질 슬롯, 겹친 액터, 레벨 수."""
    issues = {'null_static_mesh': [], 'null_material_slot': [], 'null_skeletal_mesh': []}
    actors = all_of(w, u.Actor)
    for a in actors:
        for c in a.get_components_by_class(u.StaticMeshComponent):
            m = c.get_editor_property('static_mesh')
            if not m:
                if c.is_visible():
                    issues['null_static_mesh'].append('%s.%s' % (a.get_actor_label(), c.get_name()))
                continue
            for i in range(c.get_num_materials()):
                if not c.get_material(i):
                    issues['null_material_slot'].append('%s.%s[%d] %s' % (a.get_actor_label(), c.get_name(), i, m.get_name()))
        for c in a.get_components_by_class(u.SkeletalMeshComponent):
            if not c.get_editor_property('skeletal_mesh_asset') and c.is_visible():
                issues['null_skeletal_mesh'].append('%s.%s' % (a.get_actor_label(), c.get_name()))
    counts = {}
    for a in actors:
        n = a.get_class().get_name()
        counts[n] = counts.get(n, 0) + 1
    return {'actor_count': len(actors), 'issues': issues,
            'classes': {k: v for k, v in counts.items() if k.startswith(('BP_', 'Catrun'))}}


def stage_row():
    return R['stages'].setdefault(S['map'], {'events': []})


def end_stage():
    ctx = S['ctx']
    if 'budget' in ctx:
        settings = u.load_object(None, '/Script/Catrun.Default__CatrunLevelFlowSettings')
        settings.set_editor_property(BUDGET[S['map']], ctx.pop('budget'), u.PropertyAccessChangeNotifyMode.NEVER)
    u.CatrunUserSettings.set_no_armor_capture_enabled(False)
    phase('ending')
    LE.editor_request_end_play()


def fail_stage(name, detail):
    check(name, False, detail)
    end_stage()


def next_stage():
    if not S['queue']:
        R['finished'] = time.time()
        bad = [c for c in R['checks'] if not c['passed']]
        R.update(success=not bad, failed=len(bad), phase='done')
        persist()
        u.unregister_slate_post_tick_callback(S['handle'])
        u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
        return
    S['map'], S['ctx'] = S['queue'].pop(0), {}
    stage_row()
    phase('load')
    if not check('editor map loads', LE.load_level('/Game/Maps/' + S['map'])):
        next_stage()
        return
    w = ED.get_editor_world()
    u.SystemLibrary.execute_console_command(w, 'Editor.AsyncAssetCompilationFinishAll')
    stage_row()['static'] = static_audit(w)
    issues = stage_row()['static']['issues']
    check('no visible empty mesh or material slot', not any(issues.values()),
          {k: v[:30] for k, v in issues.items() if v})
    u.log('REGRESSION_MAPCHECK_BEGIN ' + S['map'])
    u.SystemLibrary.execute_console_command(w, 'MAP CHECK')
    u.log('REGRESSION_MAPCHECK_END ' + S['map'])
    u.CatrunUserSettings.set_no_armor_capture_enabled(True)
    phase('begin')
    LE.editor_request_begin_play()


def world_changed(w):
    return hash(w) != S['ctx'].get('world')


def remember(w):
    S['ctx']['world'] = hash(w)


def after_restart(w, pc, cat, label, full_clock=True):
    """재시작 이후 공통 확인. 조작 가능해질 때까지 기다린 뒤 True."""
    if not world_changed(w) or not playable(w, pc):
        return False
    if S.get('game0') is None:
        S['game0'] = GS.get_time_seconds(w)
        S['restart_playable_game'] = S['game0']
    if GS.get_time_seconds(w) - S['game0'] < .8:
        return False
    c = clock(w)
    start = S['ctx']['start']
    here = xyz(cat.get_actor_location())
    dist = math.dist(here[:2], start[:2])
    check(label + ' returns to stage start', dist < 60, {'distance_cm': dist, 'here': here, 'start': start})
    check(label + ' restores input', not pc.is_move_input_ignored() and not pc.is_look_input_ignored())
    check(label + ' is not paused or capturing', not GS.is_game_paused(w) and not capturing(w))
    if c and S['ctx']['clock'] and S['ctx']['clock']['bTimed']:
        check(label + ' clock running', c['bRunning'], c)
        if full_clock:
            check(label + ' refills clock', c['BudgetSeconds'] - c['RemainingSeconds'] < 8, c)
    status = cat.get_component_by_class(u.CatrunSprintComponent)
    if status:
        check(label + ' refills stamina', abs(status.get_stamina() - status.get_max_stamina()) < .5,
              [status.get_stamina(), status.get_max_stamina()])
    stage_row()['events'].append({'event': label, 'playable_after_game_s': S['restart_playable_game'],
                                  'wall_s': time.monotonic() - S['changed'], 'clock': c})
    return True


def step(w):
    p, ctx, row = S['phase'], S['ctx'], stage_row()
    pc = GS.get_player_controller(w, 0)
    if not pc:
        return
    game = GS.get_time_seconds(w)
    name = w.get_name()
    if S['map'] == 'MainMenu':
        if p == 'begin':
            if game < 6:
                return
            row['menu_widgets'], row['menu_texts'] = widgets(w), texts(w)
            visible = [x for x in row['menu_widgets'] if x['in_viewport']]
            check('menu widget shown', bool(visible), visible)
            check('menu cursor available', bool(pc.get_editor_property('show_mouse_cursor')))
            row['has_continue'] = FLOW.has_continue_game(w)
            row['unlocked'] = [str(x) for x in FLOW.get_unlocked_stages(w)]
            check('fresh profile has no continue', not row['has_continue'], row['unlocked'])
            check('new game accepted', FLOW.start_new_game(w))
            phase('menu_travel')
        elif p == 'menu_travel' and name.endswith('Tutorial'):
            row['tutorial_arrival_wall_s'] = time.monotonic() - S['changed']
            check('new game travels to Tutorial', True)
            phase('menu_intro')
        elif p == 'menu_intro':
            if not playable(w, pc):
                ctx['locked'] = True
                return
            check('tutorial intro locks then releases input', ctx.get('locked'), {'game_s': game})
            check('return to menu accepted', FLOW.return_to_main_menu(w))
            phase('menu_return')
        elif p == 'menu_return' and name.endswith('MainMenu') and time.monotonic() - S['changed'] > 5:
            check('returns to MainMenu', True)
            end_stage()
        return
    if p == 'menu_wait':
        if name.endswith('MainMenu') and time.monotonic() - S['changed'] > 3:
            check('returns to MainMenu', True)
            end_stage()
        return
    cat = GS.get_player_character(w, 0)
    if not cat:
        return
    if p == 'begin':
        ctx.setdefault('world', hash(w))
        if not playable(w, pc):
            ctx['locked_at'] = game
            return
        if S.get('game0') is None:
            S['game0'] = game
        if game - S['game0'] < 1.:
            return
        ctx['start'] = xyz(cat.get_actor_location())
        ctx['clock'] = clock(w)
        row.update(playable_game_s=S['game0'], start=ctx['start'], clock=ctx['clock'], hud_texts=texts(w),
                   hud_widgets=[x for x in widgets(w) if x['in_viewport']], view=pc.get_view_target().get_name())
        check('becomes playable', True, {'game_s': S['game0']})
        check('cat grounded at start', cat.character_movement.is_moving_on_ground(), ctx['start'])
        if S['map'] != 'Tutorial':
            check('stage clock timed and running', ctx['clock']['bTimed'] and ctx['clock']['bRunning'], ctx['clock'])
            check('clock starts near full', ctx['clock']['BudgetSeconds'] - ctx['clock']['RemainingSeconds'] < 60, ctx['clock'])
        hud = WBL.get_all_widgets_of_class(w, u.CatrunPlayHUD, False)
        # 튜토리얼은 CatrunPlayHUD 대신 키 안내(WBP_Tutorial_KeyHint)를 쓴다.
        check('play HUD or tutorial key hint present', any(x.is_visible() for x in hud)
              or any('Tutorial_KeyHint' in x['class'] for x in row['hud_widgets']))
        ctx['npc'] = {k: [xyz(a.get_actor_location())] for k, a in enemies(w).items()}
        ctx['npc_max'] = {k: 0. for k in ctx['npc']}
        phase('patrol')
        S['game0'] = game
        return
    if p == 'patrol':
        for k, a in enemies(w).items():
            if k in ctx['npc']:
                d = math.dist(xyz(a.get_actor_location()), ctx['npc'][k][0])
                ctx['npc_max'][k] = max(ctx['npc_max'][k], d)
        if game - S['game0'] < 14:
            return
        row['enemy_travel_cm_14s'] = ctx['npc_max']
        still = [k for k, v in ctx['npc_max'].items() if v < 5]
        routes = {}
        for k, a in enemies(w).items():
            try:
                routes[k] = len([x for x in a.get_editor_property('PatrolPoints') if x])
            except Exception:
                routes[k] = None
        row['enemies_still'], row['patrol_points'] = still, routes
        routed = [k for k, n in routes.items() if n]
        if routed:
            check('every enemy with patrol points moves', not [k for k in routed if k in still],
                  {'travel_cm': ctx['npc_max'], 'patrol_points': routes})
        else:
            skip('enemy patrol', {'reason': 'no enemy with patrol points in this map', 'patrol_points': routes})
        c = clock(w)
        if c and c['bTimed']:
            check('clock advances', ctx['clock']['RemainingSeconds'] - c['RemainingSeconds'] > 8, c)
        ctx['walk0'], ctx['walk_dir'], ctx['walk_best'] = xyz(cat.get_actor_location()), 0, 0.
        phase('walk')
        S['game0'] = game
        return
    if p == 'walk':
        dirs = [u.Vector(1, 0, 0), u.Vector(-1, 0, 0), u.Vector(0, 1, 0), u.Vector(0, -1, 0)]
        ctx['walk_best'] = max(ctx['walk_best'], math.dist(xyz(cat.get_actor_location()), ctx['walk0']))
        if game - S['game0'] > 1.2 * (ctx['walk_dir'] + 1):
            ctx['walk_dir'] += 1
        if ctx['walk_dir'] >= 4 or ctx['walk_best'] > 60:
            check('movement input moves cat', ctx['walk_best'] > 30, {'cm': ctx['walk_best']})
            cat.character_movement.stop_movement_immediately()
            if not all_of(w, u.CatrunArmor):
                skip('capture', 'no CatrunArmor in this map')
                phase('restart_request')
                return
            placed = place_armor(w, cat)
            if not check('armor capture fixture placed', placed, placed):
                phase('restart_request')
                return
            remember(w)
            u.CatrunUserSettings.set_no_armor_capture_enabled(False)
            ctx['fixture'] = placed
            phase('capture')
            return
        cat.add_movement_input(dirs[ctx['walk_dir']], 1., False)
        return
    if p == 'capture':
        rec = capturing(w)
        if rec and not ctx.get('captured'):
            ctx['captured'] = rec
            ctx['capture_wall'] = time.monotonic()
            check('armor captures cat', True, rec)
        if ctx.get('captured') and world_changed(w) and not ctx.get('capture_reload'):
            ctx['capture_reload'] = time.monotonic() - ctx['capture_wall']
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        if not ctx.get('captured') and time.monotonic() - S['changed'] > 40:
            check('armor captures cat', False, {'fixture': ctx['fixture'], 'waited_s': 40})
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            phase('restart_request')
            return
        if ctx.get('captured') and after_restart(w, pc, cat, 'capture restart', full_clock=S['map'] != 'Stage1'):
            phase('restart_request')
        return
    if p == 'restart_request':
        if not playable(w, pc):
            return
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        remember(w)
        if not check('manual restart accepted', FLOW.restart_current_stage(w)):
            phase('menu_request')
            return
        phase('restart_wait')
        return
    if p == 'restart_wait':
        if not after_restart(w, pc, cat, 'manual restart'):
            return
        if S['map'] not in BUDGET:
            skip('timeout', 'untimed stage')
            phase('menu_request')
            return
        settings = u.load_object(None, '/Script/Catrun.Default__CatrunLevelFlowSettings')
        ctx['budget'] = settings.get_editor_property(BUDGET[S['map']])
        settings.set_editor_property(BUDGET[S['map']], 6., u.PropertyAccessChangeNotifyMode.NEVER)
        remember(w)
        check('timeout arm restart accepted', FLOW.restart_current_stage(w))
        phase('timeout_arm')
        return
    if p == 'timeout_arm':
        if not world_changed(w) or not playable(w, pc):
            return
        c = clock(w)
        check('timeout fixture budget applied', c['BudgetSeconds'] == 6., c)
        ctx['notice'] = []
        remember(w)
        phase('timeout_wait')
        return
    if p == 'timeout_wait':
        if not world_changed(w):
            for t in texts(w):
                if '마왕' in t and t not in ctx['notice']:
                    ctx['notice'].append(t)
            return
        if not after_restart(w, pc, cat, 'timeout restart'):
            return
        check('timeout notice shown', bool(ctx['notice']), ctx['notice'])
        phase('menu_request')
        return
    if p == 'menu_request':
        if not playable(w, pc):
            return
        check('return to menu accepted', FLOW.return_to_main_menu(w))
        phase('menu_wait')
        return


LIMIT = {'begin': 150, 'menu_travel': 90, 'menu_intro': 150, 'menu_return': 90, 'capture': 150,
         'restart_wait': 120, 'timeout_arm': 120, 'timeout_wait': 120, 'menu_wait': 90, 'patrol': 240}


def tick(_dt):
    try:
        p = S['phase']
        if p == 'idle':
            next_stage()
            return
        if p == 'ending':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > 1:
                next_stage()
            return
        if time.monotonic() - S['changed'] > LIMIT.get(p, 120):
            w = ED.get_game_world()
            detail = {'phase': p, 'world': w.get_name() if w else None}
            if w:
                pc = GS.get_player_controller(w, 0)
                detail.update(move_ignored=pc.is_move_input_ignored() if pc else None,
                              hud_hidden=FLOW.should_hide_gameplay_hud(w), clock=clock(w),
                              game_s=GS.get_time_seconds(w))
            fail_stage('phase finishes: ' + p, detail)
            return
        w = ED.get_game_world()
        if w:
            step(w)
    except Exception:
        try:
            fail_stage('no script exception in ' + S['phase'], traceback.format_exc())
        except Exception:
            u.log_error('REGRESSION_SWEEP ' + traceback.format_exc())


assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
persist()
S['handle'] = u.register_slate_post_tick_callback(tick)
