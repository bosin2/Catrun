"""Run via -ExecCmds="py <absolute path to this file>" in a dedicated Unreal editor.

Use -RenderOffscreen -onethread -SaveToUserDir -UserDir="<absolute isolated directory>"
and -ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False.
The wrapper requests PIE and invokes StartNewGame on MainMenu. The original route drives gameplay.
Results live in Saved/GameplayExpansion20261124/TutorialRoute/<timestamp>/ under the project.
"""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import traceback

import unreal as u


ROOT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve()
SOURCE = ROOT / 'Scripts/Prototype/verify_tutorial_complete_route.py'
OUT = ROOT / 'Saved/GameplayExpansion20261124/TutorialRoute' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(parents=True)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
STARTED = time.monotonic()
ROUTE = {'__name__': 'catrun_original_tutorial_route', '__file__': str(SOURCE)}
SCOPE = 'Offscreen editor PIE; MainMenu StartNewGame API; AddMovementInput, injected IA_Run and original BP_CatActions.TryBell.'
RESULT = {'scope': SCOPE, 'source': str(SOURCE), 'start_requested': False, 'phase': 'arming'}
HANDLE = None


def write_result(final=False):
    path = OUT / ('report.json' if final else 'progress.json')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def finish(error=None):
    previous = RESULT['phase']
    RESULT.update(phase='shutdown', final_phase=previous, success=error is None,
                  error=error, wall_seconds=time.monotonic()-STARTED)
    try:
        if 'STATE' in ROUTE:
            original_result = ROUTE['OUT'] / 'observations.json'
            if not original_result.exists() and 'handle' in ROUTE['STATE']:
                ROUTE['finish'](error or 'Wrapper stopped before original route finished')
            for name in ('observations.json', 'progress.json'):
                raw = ROUTE['OUT'] / name
                if raw.is_file():
                    (OUT / ('route-' + name)).write_bytes(raw.read_bytes())
    finally:
        write_result(final=True)
        print('CATRUN_TUTORIAL_ROUTE_DONE', RESULT['success'], OUT / 'report.json', error or '')
        if RESULT.get('owns_editor') and EDITOR.get_game_world():
            LEVEL.editor_request_end_play()


def arm():
    cmd = u.SystemLibrary.get_command_line()
    for flag in ('SaveToUserDir', 'RenderOffscreen'):
        assert re.search(r'(?:^|\s)-' + flag + r'(?:\s|$)', cmd, re.I), 'Need dedicated editor flag ' + flag
    user = re.search(r'(?:^|\s)-UserDir=(?:"([^"]+)"|([^"\s]+))', cmd, re.I)
    assert user, 'Missing isolated -UserDir'
    user_dir = Path(user.group(1) or user.group(2))
    saved = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())).resolve()
    assert user_dir.is_absolute() and saved == user_dir.resolve() / 'Saved' and saved != ROOT / 'Saved', (user_dir, saved)
    assert not EDITOR.get_game_world() and not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    RESULT['owns_editor'] = True
    RESULT['isolated_saved'] = str(saved)
    assert LEVEL.load_level('/Game/Maps/MainMenu')
    u.CatrunUserSettings.set_no_armor_capture_enabled(False)
    assert not u.CatrunUserSettings.is_no_armor_capture_enabled()
    source = SOURCE.read_bytes()
    RESULT['source_sha256'] = hashlib.sha256(source).hexdigest()
    # The older script resolves a possibly engine-relative Saved path with pathlib.
    cwd = os.getcwd()
    try:
        os.chdir(u.Paths.convert_relative_path_to_full('.'))
        assert Path(u.Paths.project_saved_dir()).resolve() == saved
        exec(compile(source, str(SOURCE), 'exec'), ROUTE)
    finally:
        os.chdir(cwd)
    ROUTE['STATE']['scope'] = SCOPE
    ROUTE['save']()
    RESULT.update(phase='waiting_for_menu', original_output=str(ROUTE['OUT']), no_armor_capture=False)
    write_result()
    print('CATRUN_TUTORIAL_ROUTE_ARMED', OUT)
    LEVEL.editor_request_begin_play()


def collect(raw):
    events = raw['events']
    samples = raw['samples']
    doors = {}
    for label, name in RESULT.get('door_names', {}).items():
        observed = [s['doors'][name] for s in samples if name in s['doors']]
        doors[label] = {'initial_open': observed[0] if observed else None,
                        'ever_open': any(observed), 'ever_closed': False in observed}
    RESULT.update(worlds=raw['worlds'], original_phase=raw['phase'], sample_count=len(samples),
                  intro_seen=raw['intro_seen'], saw_exit_overlap=raw.get('saw_exit_overlap', False),
                  saw_stairs=raw.get('saw_stairs', False), doors=doors,
                  bells_completed=[e['ordinal'] for e in events if e['kind']=='original-bell-finished'],
                  waypoints=[e['target'] for e in events if e['kind']=='waypoint-reached-by-movement'],
                  stage1_arrival=next((e for e in events if e['kind']=='automatic-Stage1-arrival'), None))
    assert raw['final'] and raw['success'], raw.get('error')
    assert RESULT['start_requested'] and RESULT['intro_seen'] and RESULT['saw_exit_overlap']
    assert RESULT['saw_stairs'] and RESULT['stage1_arrival'] and RESULT['bells_completed'] == [1, 2]
    assert doors['Door_Tutorial_Bedroom']['initial_open'] is False, doors
    assert doors['Door_Tutorial_Bedroom']['ever_open'], doors
    assert doors['Door_Tutorial_Corridor']['initial_open'] is True, doors


def tick(_delta):
    if RESULT['phase'] == 'shutdown':
        if not EDITOR.get_game_world() or time.monotonic() - STARTED - RESULT['wall_seconds'] > 10.:
            u.unregister_slate_post_tick_callback(HANDLE)
            if RESULT.get('owns_editor'):
                u.SystemLibrary.execute_console_command(EDITOR.get_editor_world(), 'QUIT_EDITOR')
        return
    try:
        elapsed = time.monotonic() - STARTED
        if elapsed > 315. or (not RESULT['start_requested'] and elapsed > 60.):
            raise TimeoutError('Tutorial wrapper exceeded deadline in ' + RESULT['phase'])
        raw = ROUTE['OUT'] / 'observations.json'
        if raw.exists():
            collect(json.loads(raw.read_text(encoding='utf-8')))
            finish()
            return
        world = EDITOR.get_game_world()
        if not world:
            return
        if world.get_name().endswith('MainMenu') and ROUTE['STATE']['menu_seen'] and not RESULT['start_requested']:
            assert not u.CatrunUserSettings.is_no_armor_capture_enabled()
            assert u.CatrunLevelFlowLibrary.start_new_game(world), 'MainMenu StartNewGame returned false'
            RESULT.update(start_requested=True, phase='route', menu_world=world.get_path_name())
            write_result()
        elif world.get_name().endswith('Tutorial') and 'door_names' not in RESULT:
            doors = u.GameplayStatics.get_all_actors_of_class(world, u.CatrunDoor)
            labels = ('Door_Tutorial_Bedroom', 'Door_Tutorial_Corridor')
            names = {d.get_actor_label(): d.get_name() for d in doors if d.get_actor_label() in labels}
            assert set(names) == set(labels), names
            RESULT['door_names'] = names
            write_result()
    except Exception:
        finish(traceback.format_exc())


HANDLE = u.register_slate_post_tick_callback(tick)
try:
    arm()
except Exception:
    finish(traceback.format_exc())
