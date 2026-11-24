"""Run with a normal offscreen editor, -onethread -SaveToUserDir -UserDir="<isolated ABS path>".
Use the process-local -ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False.

Copy the legacy v4 fixture (A/B/C solved, partial Stage2 time) to UserDir/Saved/SaveGames/CatrunProgress.sav
before launch. Execute this file via -ExecCmds="py <absolute script path>" in the dedicated
editor. Fixture placements put the pawn behind A and bring one armor into sight; movement, solve, and capture use gameplay ticks.
Reports: project Saved/GameplayExpansion20261124/ExpansionPIE/<timestamp>/report.json.
"""

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import traceback

import unreal as u

ROOT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve()
OUT = ROOT / 'Saved/GameplayExpansion20261124/ExpansionPIE' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(parents=True)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS = u.GameplayStatics
FLOW = u.CatrunLevelFlowLibrary
SYS = u.load_object(None, '/Script/Engine.Default__SubsystemBlueprintLibrary')
RUN = u.load_asset('/Game/Input/Actions/IA_Run')
S = {'phase': 'setup', 'events': [], 'readouts': [], 'started': time.monotonic()}


def persist(file):
    p = OUT / file
    tmp = p.with_suffix('.partial')
    tmp.write_text(json.dumps({k: v for k, v in S.items() if k != 'handle'}, indent=2, ensure_ascii=False), encoding='utf8')
    tmp.replace(p)


def advance(phase, **data):
    S.update(phase=phase, changed=time.monotonic())
    S['events'].append(dict(phase=phase, wall=S['changed'] - S['started'], **data))
    persist('progress.json')


def finish(error=None):
    previous = S['phase']
    if 'timeout_fixture' in S:
        fixture = S['timeout_fixture']
        setting = u.load_object(None, '/Script/Catrun.Default__CatrunLevelFlowSettings')
        setting.set_editor_property('Stage2BudgetSeconds', fixture['original_budget'], u.PropertyAccessChangeNotifyMode.NEVER)
        fixture['restored_budget'] = setting.get_editor_property('Stage2BudgetSeconds')
    S.update(success=not error, error=error, final_phase=previous, phase='shutdown', changed=time.monotonic())
    persist('report.json')
    print('CATRUN_EXPANSION_PIE_DONE', S['success'], OUT / 'report.json', error or '')
    if 'previous_capture_cvar' in S:
        u.CatrunUserSettings.set_no_armor_capture_enabled(S['previous_capture_cvar'])
    if ED.get_game_world():
        LEVEL.editor_request_end_play()


def xyz(v):
    return [v.x, v.y, v.z]


def actor_pos(actor):
    return xyz(actor.get_actor_location())


def identity(obj):
    # UE's FPyWrapperObject hash uses the native object instance. Store primitives across travel.
    return {'path': obj.get_path_name(), 'instance_hash': hash(obj)}


def reflected(world, cls):
    return SYS.call_method('GetWorldSubsystem', args=(world, cls.static_class()))


def clock(world):
    state = reflected(world, u.CatrunLevelFlowSubsystem).get_stage_clock_state()
    return {name: state.get_editor_property(name) for name in ('RemainingSeconds', 'BudgetSeconds', 'bRunning', 'bTimed')}


def all_of(world, cls):
    return list(GS.get_all_actors_of_class(world, cls))


def puzzle(world):
    [owner] = all_of(world, u.CatrunStatuePuzzle)
    result = {}
    for link in owner.get_editor_property('Links'):
        name = str(link.get_editor_property('PuzzleId'))
        row = {n: link.get_editor_property(n) for n in ('bCompleted', 'bPressed', 'GateOffset', 'RequiredGateTravel')}
        for field in ('Statue', 'Plate', 'Gate'):
            actor = link.get_editor_property(field)
            row[field] = {'actor': actor.get_actor_label(), 'origin': actor_pos(actor), 'center': xyz(actor.get_actor_bounds(False)[0])}
        result[name] = row
    assert set(result) == set('ABC'), result
    tuning = owner.get_editor_property('Settings') or u.get_default_object(u.CatrunStatuePuzzleSettings.static_class())
    return result, float(tuning.get_editor_property('PlateTravel'))


def verify_pose(world, solved_ids=()):
    live, plate_travel = puzzle(world)
    for name, row in live.items():
        original = S['authored_links'][name]
        solved = name in solved_ids
        assert row['bCompleted'] == row['bPressed'] == solved, (name, solved, row)
        for component in ('Statue', 'Plate', 'Gate'):
            assert original[component]['actor'] == row[component]['actor'], (name, component, row)
            expected = list(original[component]['origin'])
            if solved and component == 'Statue':
                for axis in (0, 1):
                    expected[axis] += original['Plate']['center'][axis] - original['Statue']['center'][axis]
            if solved and component == 'Gate':
                assert row['RequiredGateTravel'] > 0., row
                expected[2] -= row['RequiredGateTravel']
            if solved and component == 'Plate':
                expected[2] -= plate_travel
            assert math.dist(expected, row[component]['origin']) < .5, (name, component, expected, row[component])
        assert abs(row['GateOffset'] + (row['RequiredGateTravel'] if solved else 0.)) < .1, row
    return live


def unlocked(world):
    return sorted(str(x) for x in FLOW.get_unlocked_stages(world))


def disk_snapshot():
    # Observe only the scalar tags used by the seeded v4 fixture. Gameplay Continue still invokes
    # the project's strict native decoder; this read-only probe never substitutes for that decoder.
    slot = Path(S['isolated_slot'])
    raw = slot.read_bytes()
    assert raw[:4] == b'GVAS'

    def fstring(s):
        return struct.pack('<i', len(s) + 1) + s.encode('ascii') + b'\x00'

    def field(name, kind, default=None):
        marker = fstring(name) + fstring(kind) + bytes(4)
        if marker not in raw:
            assert default is not None, (name, 'missing scalar tag')
            return default
        assert raw.count(marker) == 1, name
        idx = raw.index(marker) + len(marker)
        size, flags = struct.unpack_from('<iB', raw, idx)
        if kind == 'BoolProperty':
            assert size == 0 and flags & ~0x18 == 0
            return bool(flags & 0x10)
        assert size == 4 and flags & ~0x08 == 0
        return struct.unpack_from('<i', raw, idx + 5)[0]

    return {'sha256': hashlib.sha256(raw).hexdigest(), 'write_ns':slot.stat().st_mtime_ns,
            'schema': field('SchemaVersion', 'IntProperty'),
            'stage1_ms': field('Stage1RemainingMs', 'IntProperty'), 'stage2_ms': field('Stage2RemainingMs', 'IntProperty', -1),
            'mask': field('Stage2SolvedMask', 'IntProperty', 0),
            'onboarding': field('bTutorialOnboardingCompleted', 'BoolProperty', False)}


def check_spawn(world, cat, cause):
    pos = actor_pos(cat)
    start_distance = min(math.dist(pos[:2], p['xyz'][:2]) for p in S['start_anchors'])
    gate_distance = math.dist(pos[:2], S['authored_links']['C']['Gate']['origin'][:2])
    assert start_distance < 10. and gate_distance > 150., (cause, pos, start_distance, gate_distance, S['start_anchors'])
    status = cat.get_component_by_class(u.CatrunSprintComponent)
    stamina = status.get_stamina()
    assert abs(stamina - status.get_max_stamina()) < .01 and abs(stamina-100.) < .01
    timer = clock(world)
    assert timer['bRunning'] and timer['bTimed']
    expected = S['timeout_fixture']['test_budget'] if cause == 'timeout' else S['chapter_budget']
    assert abs(timer['BudgetSeconds']-expected) < .01, (cause, timer, expected)
    assert -.02 <= expected - timer['RemainingSeconds'] < 2., (cause, expected, timer)
    S[cause] = dict(pawn=identity(cat), world=identity(world), position=pos, ordinary_start_xy_distance=start_distance,
                    c_gate_xy_distance=gate_distance, stamina=stamina, clock=timer, links=verify_pose(world))


def start_practice_push(world, cat):
    [owner] = all_of(world, u.CatrunStatuePuzzle)
    link = next(link for link in owner.get_editor_property('Links') if str(link.get_editor_property('PuzzleId')) == 'A')
    statue, plate = (link.get_editor_property(n) for n in ('Statue','Plate'))
    center, extent = statue.get_actor_bounds(False)
    plate_center = plate.get_actor_bounds(False)[0]
    delta = plate_center-center
    # The authored A route is a straight cardinal push. Position only the cat at its starting face.
    tuning = owner.get_editor_property('Settings')
    assert abs(delta.x) <= tuning.get_editor_property('SocketAxisTolerance') and abs(delta.y) > 60., (center, plate_center)
    caps = cat.get_component_by_class(u.CapsuleComponent)
    direction = u.Vector(0., 1. if delta.y > 0. else -1., 0.)
    face = center-direction*(extent.y+caps.get_scaled_capsule_radius()+4.)
    hit = u.SystemLibrary.capsule_trace_single_by_profile(world, face+u.Vector(0,0,170), face-u.Vector(0,0,220),
        caps.get_scaled_capsule_radius(),caps.get_scaled_capsule_half_height(),'Pawn',False,[cat,statue],u.DrawDebugTrace.NONE,False)
    assert hit and not hit.to_dict()['initial_overlap'] and hit.to_dict()['impact_normal'].z > .7, (center,face)
    placed = hit.to_dict()['location']+u.Vector(0,0,2.)
    cat.set_actor_location(placed, False, True)
    S['practice_push'] = {'cat_fixture':actor_pos(cat),'direction':xyz(direction),'statue_start':actor_pos(statue),
                          'slot_before':disk_snapshot(),'samples':[]}
    advance('practice_push')


def drive_practice_push(world, cat, game, playable):
    fixture = S['practice_push']
    if fixture.get('last_input') == game: return
    fixture['last_input'] = game
    [owner] = all_of(world, u.CatrunStatuePuzzle)
    link = next(link for link in owner.get_editor_property('Links') if str(link.get_editor_property('PuzzleId')) == 'A')
    pressed = link.get_editor_property('bPressed')
    complete = link.get_editor_property('bCompleted')
    if not pressed and playable:
        cat.add_movement_input(u.Vector(*fixture['direction']), 1., False)
    if not fixture['samples'] or game-fixture['samples'][-1]['game'] > .4:
        fixture['samples'].append(dict(game=game, pressed=pressed, completed=complete,
             statue=actor_pos(link.get_editor_property('Statue')), gate_offset=link.get_editor_property('GateOffset')))
    if not complete or not playable: return
    if 'completed_game' not in fixture:
        fixture['completed_game'] = game
        fixture['final_links'] = verify_pose(world, ('A',))
    if game-fixture['completed_game'] < 1.: return
    fixture['slot_after'] = disk_snapshot()
    assert fixture['slot_after'] == fixture['slot_before'], ('Stage2 solve wrote the chapter slot', fixture)
    assert math.dist(fixture['statue_start'], fixture['final_links']['A']['Statue']['origin']) > 60.
    S['previous'] = dict(pawn_hash=hash(cat), world_hash=hash(world))
    S['armor_fixture'] = place_armor(world, cat)
    u.CatrunUserSettings.set_no_armor_capture_enabled(False)
    assert not u.CatrunUserSettings.is_no_armor_capture_enabled()
    advance('capture_admitted')


def choose_walk_direction(world, cat):
    caps = cat.get_component_by_class(u.CapsuleComponent)
    start = cat.get_actor_location() + u.Vector(0, 0, 2)
    for v in ((0,-1,0), (1,0,0), (-1,0,0), (0,1,0)):
        target = start + u.Vector(*v)*180.
        hit = u.SystemLibrary.capsule_trace_single_by_profile(world, start, target, caps.get_scaled_capsule_radius(),
            caps.get_scaled_capsule_half_height(), 'Pawn', False, [cat], u.DrawDebugTrace.NONE, False)
        if not hit:
            return v
    raise AssertionError('No 180 cm clear grounded sprint segment at Stage2 start')


def place_armor(world, cat):
    cat_pos = cat.get_actor_location()
    armors = sorted(all_of(world, u.CatrunArmor), key=lambda a: math.dist(actor_pos(a), xyz(cat_pos)))
    for armor in armors:
        capsule = armor.get_component_by_class(u.CapsuleComponent)
        for x,y in ((72,0),(-72,0),(0,72),(0,-72)):
            point = cat_pos + u.Vector(x,y,0)
            ignored = [armor, cat]
            hit = u.SystemLibrary.capsule_trace_single_by_profile(world, point + u.Vector(0,0,190), point-u.Vector(0,0,160),
                capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height(), 'Pawn', False, ignored,
                u.DrawDebugTrace.NONE, False)
            if not hit: continue
            floor = hit.to_dict()
            if floor['initial_overlap'] or floor['impact_normal'].z < .7: continue
            target = floor['location'] + u.Vector(0,0,2.)
            if u.SystemLibrary.line_trace_single(world, u.Vector(target.x,target.y,cat_pos.z), cat_pos,
                    u.TraceTypeQuery.ECC_VISIBILITY, False, ignored, u.DrawDebugTrace.NONE, False): continue
            original = actor_pos(armor)
            armor.set_actor_location_and_rotation(target, u.Rotator(yaw=math.degrees(math.atan2(-y,-x))), False, True)
            assert math.dist(actor_pos(armor), xyz(target)) < 1.
            return dict(actor=armor.get_actor_label(), original=original, placed=actor_pos(armor), pawn=xyz(cat_pos))
    raise AssertionError('No supported clear catch fixture near the player')


def capture_active(world):
    for armor in all_of(world, u.CatrunArmor):
        capture = armor.get_component_by_class(u.CatrunCapturePresentationComponent)
        if capture and capture.is_capturing():
            return {'armor': armor.get_actor_label(), 'phase': str(capture.get_editor_property('Phase')),
                    'session': capture.get_editor_property('SessionId')}
    return None


def timeout_readout(world, pc, cat, game):
    fixture = S['timeout_fixture']
    assert u.CatrunUserSettings.is_no_armor_capture_enabled()
    timer = clock(world)
    if hash(world) != S['previous']['world_hash']:
        assert hash(cat) != S['previous']['pawn_hash']
        # Count observed stage worlds from zero through the post-refill observation.
        if hash(world) not in fixture['reload_worlds']:
            fixture['reload_worlds'].append(hash(world))
        assert len(fixture['reload_worlds']) == 1 and fixture.get('readable_notice'), fixture
        if FLOW.should_hide_gameplay_hud(world) or not timer['bRunning']: return
        check_spawn(world, cat, 'timeout')
        assert abs(timer['BudgetSeconds'] - fixture['test_budget']) < .01
        advance('timeout_stable', clock=timer)
        return
    remaining = timer['RemainingSeconds']
    if not fixture['samples'] or fixture['samples'][-1]['remaining']-remaining >= .3:
        fixture['samples'].append({'game':game,'remaining':remaining})
    if remaining > 0.: return
    assert not capture_active(world) and pc.is_move_input_ignored() and pc.is_look_input_ignored()
    if 'zero_time' not in fixture:
        fixture['zero_time'] = game
        fixture['samples'].append({'game':game,'remaining':remaining})
    if 'readable_notice' not in fixture:
        notices = [n for n in u.WidgetLibrary.get_all_widgets_of_class(world,u.CatrunNoticeWidget,True)
                   if n.is_in_viewport() and n.is_visible() and n.get_render_opacity() > .9]
        for block in u.ObjectIterator(u.TextBlock):
            owner = block.get_typed_outer(u.CatrunNoticeWidget)
            if owner in notices and str(block.get_text()) == '마왕이 깨어났다':
                fixture['readable_notice'] = dict(text=str(block.get_text()), widget=owner.get_path_name(), game=game)
                break
    age = game-fixture['zero_time']
    for key, lower, upper in [('before_fade', 0., .9), ('during_fade', 1.40, 1.70)]:
        if key in fixture or not lower <= age < upper: continue
        path = (OUT / (key+'_.png')).as_posix()
        u.SystemLibrary.execute_console_command(world, f'Shot filename="{path}"', pc)
        fixture[key] = {'age_after_zero':age, 'path_prefix':key+'_'}


def measure_timeout_fade():
    fixture = S['timeout_fixture']
    images = [next(OUT.glob(fixture[key]['path_prefix']+'*.png')) for key in ('before_fade','during_fade')]
    # The Windows project toolchain includes CPython/Pillow. Measure both captured frames after gameplay checks.
    script = ('from PIL import Image,ImageStat; import json,sys; '
              'print(json.dumps([ImageStat.Stat(Image.open(p).convert("L").resize((96,54))).mean[0] for p in sys.argv[1:]]))')
    result = subprocess.run([shutil.which('python'), '-I', '-c', script, *map(str,images)],
                            capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    before, during = json.loads(result.stdout)
    fixture['fade_measurement'] = {'before_luma':before, 'during_luma':during, 'frames':list(map(str,images))}
    assert before > 1. and during < .8*before, ('Timeout black fade did not darken the game backbuffer', before, during)


def step(world):
    phase = S['phase']
    wpath = world.get_path_name()
    pc = GS.get_player_controller(world, 0)
    if not pc: return
    if phase == 'menu':
        if not wpath.split('.')[-1].endswith('MainMenu'): return
        if not FLOW.can_continue_stage(world, 'Stage2'): return
        S['unlocked_before'] = unlocked(world)
        assert 'Stage2' in S['unlocked_before']
        assert FLOW.continue_stage(world, 'Stage2')
        advance('continue_arrival')
        return
    if not wpath.split('.')[-1].endswith('Stage2'): return
    cat = GS.get_player_pawn(world, 0)
    if not cat or not reflected(world, u.CatrunLevelFlowSubsystem): return
    game = GS.get_time_seconds(world)
    playable = not FLOW.should_hide_gameplay_hud(world) and clock(world)['bRunning']
    if phase == 'timeout_arm':
        if hash(world) == S['previous']['world_hash'] or not playable: return
        S['previous'] = {'world_hash':hash(world), 'pawn_hash':hash(cat)}
        timer = clock(world)
        assert timer['BudgetSeconds'] == 6. and 4. < timer['RemainingSeconds'] <= 6.
        verify_pose(world)
        advance('natural_timeout', start=timer)
        return
    if phase == 'natural_timeout':
        timeout_readout(world, pc, cat, game)
        return
    if phase == 'timeout_stable':
        assert hash(world) == S['timeout']['world']['instance_hash'] and hash(cat) == S['timeout']['pawn']['instance_hash']
        assert not capture_active(world) and unlocked(world) == S['unlocked_before']
        if S['timeout']['clock']['RemainingSeconds']-clock(world)['RemainingSeconds'] < 1.9: return
        S['after_timeout_slot'] = disk_snapshot()
        assert all(S['after_timeout_slot'][k] == S['seed'][k] for k in ('stage1_ms','onboarding'))
        measure_timeout_fade()
        finish()
        return
    if phase in ('continue_arrival', 'capture_reload', 'reset_reload'):
        cause = {'continue_arrival':'continue', 'capture_reload':'capture', 'reset_reload':'reset'}[phase]
        if phase != 'continue_arrival':
            old = S['previous']
            if hash(cat) == old['pawn_hash'] or hash(world) == old['world_hash']: return
        if not playable: return
        check_spawn(world, cat, cause)
        if cause == 'continue':
            S['direction'] = choose_walk_direction(world, cat)
            advance('sprint')
        elif cause == 'capture':
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            S['previous'] = dict(pawn_hash=hash(cat), world_hash=hash(world))
            assert FLOW.restart_current_stage(world), 'Manual reset admission rejected'
            advance('reset_reload')
        else:
            assert unlocked(world) == S['unlocked_before']
            advance('reset_verified')
        return
    if phase == 'reset_verified':
        final = disk_snapshot()
        assert final['stage1_ms'] == S['seed']['stage1_ms'] and final['onboarding'] == S['seed']['onboarding']
        S['reset_slot'] = final
        setting = u.load_object(None, '/Script/Catrun.Default__CatrunLevelFlowSettings')
        S['timeout_fixture'] = {'original_budget':setting.get_editor_property('Stage2BudgetSeconds'), 'test_budget':6.,
                                'reload_worlds':[], 'samples':[], 'armor_capture_disabled':True,
                                'setup':'In-memory Stage2 budget followed by normal confirmed-reset entry point; config is never saved.'}
        setting.set_editor_property('Stage2BudgetSeconds', 6., u.PropertyAccessChangeNotifyMode.NEVER)
        assert u.CatrunUserSettings.is_no_armor_capture_enabled()
        S['previous'] = {'world_hash':hash(world),'pawn_hash':hash(cat)}
        assert FLOW.restart_current_stage(world)
        advance('timeout_arm')
        return
    if phase == 'options_paused':
        held = clock(world)
        assert GS.is_game_paused(world) and not held['bRunning'] and abs(held['RemainingSeconds']-S['pause_clock']) < .002, held
        if time.monotonic() - S['changed'] < .8: return
        opts = u.CatrunSettingsSubsystem.get(world)
        assert opts.get_current_settings_widget()
        opts.close_settings()
        advance('options_resumed', held=held)
        return
    if phase == 'capture_admitted':
        if (record := capture_active(world)):
            S['capture_owner'] = record
            advance('capture_reload', accepted=record)
        return
    if phase == 'practice_push':
        drive_practice_push(world, cat, game, playable)
        return
    if not playable: return
    if phase == 'options_resumed':
        if S['pause_clock']-clock(world)['RemainingSeconds'] < .4: return
        S['resumed_clock'] = clock(world)
        start_practice_push(world, cat)
        return
    if S.get('last_move_frame') == game: return
    S['last_move_frame'] = game
    sprint = cat.get_component_by_class(u.CatrunSprintComponent)
    value = sprint.get_stamina()
    if phase == 'sprint':
        sub = SYS.call_method('GetLocalPlayerSubsystem', args=(pc,u.EnhancedInputLocalPlayerSubsystem.static_class()))
        row = {'game':game, 'stamina':value, 'sprinting':sprint.is_sprinting(),
               'cap':cat.get_component_by_class(u.CharacterMovementComponent).max_walk_speed, 'xyz':actor_pos(cat)}
        if not S['readouts'] or game-S['readouts'][-1]['game'] >= .08 or value <= 82.:
            S['readouts'].append(row)
        if value > 82.:
            sub.inject_input_vector_for_action(RUN, u.Vector(1,0,0), [], [])
            cat.add_movement_input(u.Vector(*S['direction']), 1., False)
        else:
            sub.inject_input_vector_for_action(RUN, u.Vector(), [], [])
            assert any(sample['sprinting'] and abs(sample['cap']-134.) < .01 for sample in S['readouts'])
            assert math.dist(S['continue']['position'][:2], row['xyz'][:2]) > 55.
            S['minimum_stamina'] = value
            advance('recovery', game=game, readout=row)
    elif phase == 'recovery':
        if value < S['minimum_stamina']: S['minimum_stamina'] = value
        if value < sprint.get_max_stamina()-.01: return
        assert value - S['minimum_stamina'] >= 18.
        S['pause_clock'] = clock(world)['RemainingSeconds']
        opts = u.CatrunSettingsSubsystem.get(world)
        assert opts.open_settings(pc, None) and GS.is_game_paused(world)
        advance('options_paused', recovered=value, game=game)


def tick(_delta):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > .5:
                u.unregister_slate_post_tick_callback(S['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        if time.monotonic() - S['changed'] > 70. or time.monotonic() - S['started'] > 240.:
            raise TimeoutError(S['phase'])
        world = ED.get_game_world()
        if world: step(world)
    except Exception:
        finish(traceback.format_exc())


def setup():
    assert not ED.get_game_world() and not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    cmd = u.SystemLibrary.get_command_line()
    assert re.search(r'(?:^|\s)-SaveToUserDir(?:\s|$)', cmd, re.I), 'Missing isolated SaveToUserDir'
    match = re.search(r'-UserDir=(?:"([^"]+)"|([^"\s]+))', cmd, re.I)
    assert match, 'Missing isolated UserDir'
    user_dir = Path(match.group(1) or match.group(2))
    saved = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())).resolve()
    assert user_dir.is_absolute() and saved == user_dir.resolve()/'Saved' and saved != ROOT/'Saved', (user_dir,saved)
    S['isolated_slot'] = str(saved/'SaveGames/CatrunProgress.sav')
    seed = disk_snapshot()
    S['chapter_budget'] = float(u.load_object(None, '/Script/Catrun.Default__CatrunLevelFlowSettings').get_editor_property('Stage2BudgetSeconds'))
    assert abs(S['chapter_budget'] - 900.) < .01, ('Expected the default Stage2 budget for this integration run', S['chapter_budget'])
    assert seed['schema'] == 4 and seed['mask'] == 7 and seed['onboarding'] and 0 < seed['stage2_ms'] < 1000*(S['chapter_budget']-2), (
        'Need legacy v4 all-solved and genuinely shortened Stage2 allocation', seed)
    S['seed'] = seed
    S['background_throttle_override_requested'] = (
        'bthrottlecpuwhennotforeground=false' in cmd.lower())
    assert LEVEL.load_level('/Game/Maps/Stage2')
    authored = ED.get_editor_world()
    S['authored_links'], _ = puzzle(authored)
    starts = [a for a in all_of(authored, u.Character) if a.get_class().get_name() == 'BP_Cat_C']
    if not starts:
        starts = all_of(authored, u.PlayerStart)
    assert starts, 'No authored ordinary player start or placed BP_Cat'
    S['start_anchors'] = [{'actor':a.get_actor_label(), 'class':a.get_class().get_name(), 'xyz':actor_pos(a)} for a in starts]
    del authored, starts
    assert LEVEL.load_level('/Game/Maps/MainMenu') and RUN
    S['previous_capture_cvar'] = u.CatrunUserSettings.is_no_armor_capture_enabled()
    u.CatrunUserSettings.set_no_armor_capture_enabled(True)
    advance('menu')
    LEVEL.editor_request_begin_play()


S['handle'] = u.register_slate_post_tick_callback(tick)
try:
    setup()
except Exception:
    finish(traceback.format_exc())
