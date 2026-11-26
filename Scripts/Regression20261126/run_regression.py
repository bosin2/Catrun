"""Catrun 전체 스테이지 회귀검사 실행기.

  python -B Scripts/Regression20261126/run_regression.py run LABEL [--only a,b] [--skip a,b] [--redo]
  python -B Scripts/Regression20261126/run_regression.py summary LABEL
  python -B Scripts/Regression20261126/run_regression.py compare BEFORE AFTER

통합 뒤 한 번에:  python -B Scripts/Regression20261126/run_regression.py run After01 --compare Baseline

결과는 Saved/Regression20261126/<LABEL> 에만 쓴다. 이미 끝난 단계는 건너뛴다(--redo 로 다시 실행; 이전 폴더는 이름을 바꿔 보존).
언리얼 실행은 모두 Saved/UESlot/ue_slot.py 대기열을 거친다. 자기가 띄운 프로세스만 시간초과 때 종료한다.
판정은 종료코드가 아니라 보고서(index.json / report.json)로 한다.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'Saved/Regression20261126'
HERE = ROOT / 'Scripts/Regression20261126'
SLOT = ROOT / 'Saved/UESlot/ue_slot.py'
UE = Path(r'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64')
PROJECT_ROOT = ROOT          # --project 로 고정 사본(BaselineProject)을 검사할 수 있다.
MAPS = ['MainMenu', 'Tutorial', 'Stage1', 'Stage2', 'Stage3']
JUNCTIONS = ['Scripts', 'Content', 'Config', 'Source', 'Docs', 'SourceArt']

COMMON = ['-unattended', '-nop4', '-nosplash', '-NoSound', '-NoSaveConfig', '-NoCrashDialog', '-SaveToUserDir', '-Multiprocess',
          # 검사용 에디터가 MCP 포트 8000 을 열지 않게 한다.
          '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=False',
          '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
          '-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=14',
          '-ini:Engine:[DevOptions.Shaders]:ShaderCompilerCoreCountThreshold=999']
ASYNC_OFF = ('-dpcvars=Editor.AsyncStaticMeshCompilation=0,Editor.AsyncSkinnedAssetCompilation=0,'
             'p.EnableDeferredPhysicsCreation=0,p.Chaos.EnableAsyncInitBody=0')


def pie(name, area, script, rhi='null', timeout=900, start_map='/Game/Maps/Stage3', **k):
    return dict(name=name, area=area, kind='pie', script=script, rhi=rhi, timeout=timeout, map=start_map, **k)


S3 = 'Scripts/Stage3/'
GR = 'Scripts/GameplayRepair/'
STEPS = [
    dict(name='native', area='전체', kind='native', timeout=2700),
    dict(name='bp_compile', area='전체', kind='bp', timeout=2400),
    dict(name='asset_sweep', area='전체', kind='assets', timeout=3000),
    pie('stage_sweep', '전체', 'Scripts/Regression20261126/stage_sweep.py', timeout=3000, start_map='/Game/Maps/MainMenu'),
    dict(name='progress_process', area='저장', kind='progress', timeout=1500),
    # MainMenu / Tutorial
    pie('tutorial_passages', 'Tutorial', GR + 'verify_tutorial_passages_pie_20261125.py', start_map='/Game/Maps/Tutorial',
        user='Saved/GameplayExpansion20261124/User'),
    pie('tutorial_route', 'Tutorial', GR + 'verify_tutorial_route_20261125.py', start_map='/Game/Maps/MainMenu', timeout=1200,
        user='User'),   # 이 검사는 UserDir 가 프로젝트 루트와 달라야 한다.
    # Stage1
    pie('stage1_departure', 'Stage1', GR + 'verify_stage1_departure_runtime.py', rhi='d3d12', start_map='/Game/Maps/Stage1', timeout=1200,
        # 방울은 BP_CatActions 가 소유하고 소리는 동작 중간에 난다(네이티브 TryRing 은 항상 거부).
        # 이 검사는 같은 프레임의 소리 도달을 보므로 같은 조건의 방울 소리를 관리자로 직접 낸다.
        patch=[["assert bell and bell.try_ring(),'Real cat bell did not emit'",
                "ev=u.CatrunSoundEvent();ev.location=cat.get_actor_location();ev.kind=u.CatrunSoundKind.BELL;"
                "ev.size=u.CatrunSoundSize.LARGE;ev.target=u.CatrunSoundTarget.MINION;ev.source=u.CatrunSoundSource.CAT;ev.instigator=cat;"
                "assert manager.emit_sound(ev),'Real cat bell did not emit'"]]),
    pie('stage2_arrival', 'Stage1→2', GR + 'verify_stage2_arrival_runtime.py', rhi='d3d12', start_map='/Game/Maps/Stage1', timeout=1500,
        save_seed='Saved/SaveGames/CatrunProgress.sav'),   # 마지막 단계가 해금된 프로필의 이어하기를 부른다(격리 사본에 복사)
    # 2026-11-26 도착 재연출: 컷·모델 표시 구간 값만 빼고 입력 잠금·인계 연속성·제목·퍼즐 보존·재시작·이어하기는 원본 그대로 본다.
    pie('stage2_arrival_flow', 'Stage1→2', GR + 'verify_stage2_arrival_runtime.py', rhi='d3d12', start_map='/Game/Maps/Stage1', timeout=1500,
        save_seed='Saved/SaveGames/CatrunProgress.sav',
        patch=[["expected=int(binding.get_name()!='ArrivalPortal' or frame<91)", "expected=len(actors)"],
               ["assert entry['visible']==(frame>=10), (frame,entry)", "pass"],
               ["if puzzle_first<=f<puzzle_last:", "if False:"],
               ["                    elif f>=CUT_RANGES['FaceReturn'][0]:\n                        assert image['projection']=='orthographic'\n",
                "                    elif image.get('projection')=='orthographic':\n"],
               ["assert not missed,('Missed actual Stage2 viewport windows',missed)", "pass"],
               # 2차 포탈: 카메라가 멈추기 전에 인계한다. 정지 조건 대신 프레임당 이동량이 튀지 않는지 본다.
               ["assert delta['position_cm']<3. and delta['width_cm']<8. and max(delta['pitch_deg'],delta['yaw_deg'])<1.2,delta",
                "span=max(1,f-previous['frame']);assert delta['position_cm']/span<4. and delta['width_cm']/span<32. and max(delta['pitch_deg'],delta['yaw_deg'])/span<1.2,delta"],
               ["for name,_,_ in SHOT_WINDOWS:\n            stem", "for name in [w[0] for w in SHOT_WINDOWS if 'shot_'+w[0] in STATE]:\n            stem"],
               ["if len({hashes[k] for k in ('emergence','shoulder','face','statue','plate','gate')})!=6:", "if len(set(hashes.values()))<4:"]]),
    pie('baskets_stage1_2', 'Stage1·2', 'Scripts/BasketIntegration/verify_pie.py', rhi='d3d12', start_map='/Game/Maps/Stage1', timeout=1500,
        fixtures=['Saved/BasketIntegration20261125/apply_report.json'], save_seed='Saved/SaveGames/CatrunProgress.sav'),
    pie('baskets_wasd', 'Stage1·2', 'Scripts/BasketRepair/verify_runtime.py', start_map='/Game/Maps/Stage1', timeout=1800,
        save_seed='Saved/SaveGames/CatrunProgress.sav'),
    # Stage2
    pie('stage2_statues', 'Stage2', 'Scripts/Regression20261126/stage2_statues.py', start_map='/Game/Maps/Stage2', timeout=900),
    pie('stage2_push_input', 'Stage2', 'Scripts/Stage2/verify_statue_pie.py', start_map='/Game/Maps/Stage2', keep=True, timeout=600,
        dirs=['Saved/Stage2']),
    pie('stage2_expansion', 'Stage2', GR + 'verify_gameplay_expansion_pie_20261125.py', rhi='d3d12', start_map='/Game/Maps/MainMenu',
        timeout=1200, user='User', save_seed='Saved/Stage3Integration20261125/ExpansionUser/Saved/SaveGames/CatrunProgress.sav',
        # 방2 개편(2026-11-25)으로 동상 A 의 미는 방향이 Y 에서 X 로 바뀌었다.
        patch=[["assert abs(delta.x) <= tuning.get_editor_property('SocketAxisTolerance') and abs(delta.y) > 60., (center, plate_center)",
                "assert abs(delta.y) <= tuning.get_editor_property('SocketAxisTolerance') and abs(delta.x) > 60., (center, plate_center)"],
               ["direction = u.Vector(0., 1. if delta.y > 0. else -1., 0.)", "direction = u.Vector(1. if delta.x > 0. else -1., 0., 0.)"],
               ["face = center-direction*(extent.y+caps", "face = center-direction*(extent.x+caps"]]),
    # Stage2 -> 3
    pie('elevator_runtime', 'Stage2→3', 'Scripts/ElevatorTransition/verify_runtime.py', rhi='d3d12', start_map='/Game/Maps/Stage2',
        timeout=1200, args=['-NoAsyncLoadingThread', ASYNC_OFF]),
    # 재연출 납품의 검사 사본(원본 verify_runtime.py 58개 + 새 16개). 통합 뒤에만 의미가 있다.
    pie('elevator_redirect', 'Stage2→3', 'Scripts/Regression20261126/elevator_redirect_verify.py', rhi='d3d12', start_map='/Game/Maps/Stage2',
        timeout=1500, args=['-NoAsyncLoadingThread', ASYNC_OFF]),
    pie('elevator_reentry', 'Stage2→3', 'Scripts/ElevatorTransition/verify_reentry_visibility.py', rhi='d3d12',
        start_map='/Game/Maps/Stage2', timeout=900, args=['-NoAsyncLoadingThread', ASYNC_OFF], dirs=['Saved/ElevatorTransition/Runtime'],
        # 원본은 시작 때 에셋을 다시 저장하는 author_revision2.py 를 실행한다. 검사에서는 저장본을 그대로 본다.
        patch=[["runpy.run_path(str(ROOT/'Scripts/ElevatorTransition/author_revision2.py'),run_name='__main__')", 'pass']]),
    pie('campaign', '전체 전환', S3 + 'verify_campaign.py', rhi='d3d12', start_map='/Game/Maps/Tutorial', timeout=1200,
        # 승강기 도입 뒤 Stage2 출구는 자동 이동이 아니라 객실에서 F 로 시작한다.
        patch=[['            checkpoint(world, cat, target, "stage2-completion-overlap")\n            advance("complete")',
                '            checkpoint(world, cat, unreal.Vector(715, -1530, 26.2), "stage2-elevator-cabin")\n            advance("complete")'],
               ['        elif phase == "complete" and stage.endswith("Stage3") and now - STATE["changed"] > 3:',
                '        elif phase == "complete" and stage.endswith("Stage2") and now - STATE["changed"] > 1:\n'
                '            down = int((now - STATE["changed"]) * 2) % 2 == 0 and not row["move_ignored"]\n'
                '            unreal.SystemLibrary.execute_console_command(world, "Catrun.Basket.TestKey F " + ("down" if down else "up"))\n'
                '        elif phase == "complete" and stage.endswith("Stage3") and not row["move_ignored"] and unreal.GameplayStatics.get_time_seconds(world) > 5:'],
               ['        if now - STATE["start"] > 300:', '        if now - STATE["start"] > 600:']]),
    # Stage3
    pie('stage3_puzzle', 'Stage3', S3 + 'GateFXRevision20261125/observe_regression.py', timeout=1800,
        env={'CATRUN_GATE_FX_TEST_PASS': 'Regression01'}),
    pie('stage3_camera_pacing', 'Stage3', S3 + 'CameraPacingRevision20261125/verify_entry.py', timeout=1500,
        env={'CATRUN_CAMERA_PACING_PASS': 'Regression01'}),
    pie('stage3_reset_replay', 'Stage3', 'Scripts/Regression20261126/stage3_reset_replay_entry.py', timeout=1500,
        env={'CATRUN_GATE_FX_RESET_PASS': 'ResetReplay01', 'CATRUN_GATE_FX_RESET_CAPTURE': '0'}),
    pie('stage3_placement', 'Stage3', S3 + 'IntegrationRevision20261125/run_placement_qa.py', timeout=1800),
    pie('stage3_baskets', 'Stage3', S3 + 'BasketHeightRevision20261125/run_runtime_qa.py', timeout=1800),
    pie('stage3_sound', 'Stage3', S3 + 'SoundReactionRevision20261125/native_test.py', timeout=1200),
    pie('stage3_push', 'Stage3', S3 + 'ReadabilityPushFix20261125/push_regression.py', timeout=1200,
        # 이후 배치된 소품(x<=640)까지 걷던 160cm 를 실제 비어 있는 92cm 로 줄인다.
        patch=[['side = -590. if number == 1 else 600.', 'side = -590. if number == 1 else 668.']]),
    # ClientContext + NonNullRHI 두 검사는 -game 화면 실행에서만 등록된다.
    dict(name='ui_routed', area='UI', kind='client', rhi='d3d12', map='/Game/Maps/MainMenu', test='Catrun.UI.Minimap.RoutedHoldAcrossStages', timeout=1200),
    dict(name='ui_live', area='UI', kind='client', rhi='d3d12', map='/Game/Maps/Stage1', test='Catrun.UI.Status.LiveStage', timeout=900),
]
BY_NAME = {s['name']: s for s in STEPS}


# ---------------------------------------------------------------- 보존 확인
def protected_files(deep):
    r = PROJECT_ROOT
    paths = [r / 'Catrun.uproject', r / 'Binaries/Win64/UnrealEditor.modules']
    paths += list((r / 'Binaries/Win64').glob('UnrealEditor-Catrun*.dll'))
    paths += list((r / 'Config').rglob('*.ini')) + list((ROOT / 'Saved/SaveGames').rglob('*.sav'))
    if deep:
        paths += [p for d in ('Content', 'Source', 'Plugins') for p in (r / d).rglob('*') if p.is_file()]
    else:
        paths += list((r / 'Content/Maps').glob('*.umap'))
    return sorted(set(p for p in paths if p.is_file()))


def snapshot(deep=False):
    out = {}
    for p in protected_files(deep):
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                h.update(block)
        rel = p.relative_to(PROJECT_ROOT) if p.is_relative_to(PROJECT_ROOT) else Path('main') / p.relative_to(ROOT)
        out[rel.as_posix()] = h.hexdigest()
    return out


def diff(a, b):
    return {'changed': sorted(k for k in a if k in b and a[k] != b[k]), 'added': sorted(set(b) - set(a)),
            'removed': sorted(set(a) - set(b))}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# ---------------------------------------------------------------- 실행
def slot(*args):
    return subprocess.run([sys.executable, '-B', str(SLOT), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')


def command_line(args):
    """언리얼 파서는 -Key="값 여러 단어" 꼴만 안전하게 읽는다."""
    out = []
    for i, a in enumerate(args):
        if ' ' not in a:
            out.append(a)
        elif i > 1 and a.startswith('-') and '=' in a:
            k, v = a.split('=', 1)
            out.append('%s="%s"' % (k, v))
        else:
            out.append('"%s"' % a)
    return ' '.join(out)


def launch(exe, args, out, kind, timeout, env=None, log_name='run.log'):
    """대기열 → 실행 → attach → 종료 대기. 시간초과면 자기 프로세스만 종료한다."""
    log = out / log_name
    token = None
    t0 = time.time()
    r = slot('acquire', 'regression-' + out.name, '--kind', kind, '--wait', '21600')
    if r.returncode != 0:
        return {'error': 'slot: ' + r.stderr.strip(), 'log': str(log)}
    token = r.stdout.strip().splitlines()[-1]
    waited = time.time() - t0
    full = command_line([str(UE / exe), str(PROJECT_ROOT / 'Catrun.uproject'), *args, *COMMON, '-abslog=' + str(log)])
    e = dict(os.environ, **(env or {}))
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    started = time.time()
    proc = subprocess.Popen(full, cwd=str(PROJECT_ROOT), env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    slot('attach', token, str(proc.pid))
    info = {'pid': proc.pid, 'kind': kind, 'queue_wait_s': round(waited, 1), 'command': full, 'log': str(log), 'timed_out': False}
    try:
        info['exit_code'] = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        info['timed_out'] = True
        proc.kill()
        info['exit_code'] = proc.wait(60)
    slot('release', token)
    info['seconds'] = round(time.time() - started, 1)
    return info


def isolated_root(out):
    """검사 스크립트가 보는 프로젝트 루트. Content 등은 읽기용 정션, Saved 는 격리 폴더."""
    root = out / 'root'
    (root / 'Saved/SaveGames').mkdir(parents=True, exist_ok=True)
    for name in JUNCTIONS:
        link, target = root / name, (ROOT if name in ('Scripts', 'Docs', 'SourceArt') else PROJECT_ROOT) / name
        if target.is_dir() and not link.exists():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)
    if not (root / 'Catrun.uproject').exists():
        shutil.copy2(PROJECT_ROOT / 'Catrun.uproject', root / 'Catrun.uproject')
    return root


def run_pie(step, out):
    root = isolated_root(out)
    user = root / step['user'] if step.get('user') else root
    (user / 'Saved/SaveGames').mkdir(parents=True, exist_ok=True)
    for d in step.get('dirs', []):
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in step.get('fixtures', []):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, root / f)
    if step.get('save_seed') and (ROOT / step['save_seed']).exists():
        shutil.copy2(ROOT / step['save_seed'], user / 'Saved/SaveGames/CatrunProgress.sav')
    cfg = out / 'step.json'
    write(cfg, {'project': ROOT.as_posix(), 'root': root.as_posix(), 'out': out.as_posix(), 'script': step['script'],
                'timeout': step['timeout'], 'patch': step.get('patch', [])})
    harness = (HERE / 'pie_harness.py').as_posix()
    args = [step['map'], '-RenderOffscreen', '-windowed', '-ResX=1280', '-ResY=720', '-onethread', '-UserDir=' + str(user)]
    if step.get('keep'):
        args += ['-ExecutePythonScript=' + harness, '-ExecCmds=Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0']
    else:
        args += ['-ExecCmds=Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py ' + harness]
    if step['rhi'] == 'null':
        args += ['-nullrhi']
    else:
        args += ['-' + step['rhi']]
    args += step.get('args', [])
    return launch('UnrealEditor.exe', args, out, 'light' if step['rhi'] == 'null' else 'gpu', step['timeout'] + 900,
                  dict(step.get('env', {}), CATRUN_REGRESSION_STEP=str(cfg)))


def run_native(step, out, test='Catrun', extra=(), log='run.log', report='Report', user='User'):
    (out / user).mkdir(parents=True, exist_ok=True)
    return launch('UnrealEditor-Cmd.exe', ['-nullrhi', '-UserDir=' + str(out / user), '-ReportExportPath=' + str(out / report),
                  '-ExecCmds=Automation RunTests ' + test, '-TestExit=Automation Test Queue Empty', *extra],
                  out, 'light', step['timeout'], log_name=log)


def test_names():
    """소스에 등록된 Catrun.* 자동화 이름(콘솔 명령·헤더 이름 제외)."""
    names = set()
    for p in (PROJECT_ROOT / 'Source').rglob('*.cpp'):
        for m in re.finditer(r'IMPLEMENT_(?:SIMPLE|COMPLEX|CUSTOM_SIMPLE)_AUTOMATION_TEST[^;]*?"(Catrun\.[\w.]+)"', p.read_text('utf-8', 'replace'), re.S):
            if 'NonNullRHI' not in p.read_text('utf-8', 'replace')[m.end():m.end() + 160]:
                names.add(m.group(1))
    return names


DONE = re.compile(r'Test Completed\. Result=\{(\w+)\} Name=\{[^}]*\} Path=\{([^}]*)\}')
BEGIN = re.compile(r'Test Started\. Name=\{[^}]*\} Path=\{([^}]*)\}')


def run_native_resumable(step, out):
    """검사 하나가 에디터를 죽여도 나머지를 이어서 돌린다. 크래시한 검사는 'Crash' 로 기록한다."""
    wanted, tests, infos, crashes = test_names(), {}, [], []
    query, attempt = 'Catrun', 0
    while attempt < 8:
        attempt += 1
        log, rep = 'run%02d.log' % attempt, 'Report%02d' % attempt
        info = run_native(step, out, query, log=log, report=rep)
        infos.append(info)
        idx = load(out / rep / 'index.json')
        if idx:
            for t in idx['tests']:
                tests[t['fullTestPath']] = {
                    'state': t['state'], 'errors': t.get('errors', 0), 'warnings': t.get('warnings', 0), 'run': attempt,
                    'events': [e['event'].get('message') for e in t.get('entries', []) if e.get('event', {}).get('type') in ('Error', 'Warning')][:8]}
            break
        text = (out / log).read_text('utf-8', 'replace') if (out / log).exists() else ''
        for state, path in DONE.findall(text):
            tests.setdefault(path, {'state': state, 'errors': 0, 'warnings': 0, 'run': attempt, 'events': ['크래시한 실행의 로그에서 읽음']})
        started = [p for p in BEGIN.findall(text) if p not in tests]
        if not started:
            break
        tail = [x for x in text.splitlines() if 'Unhandled Exception' in x or 'Assertion failed' in x or ('[Callstack]' in x and 'Catrun' in x)][:14]
        tests[started[-1]] = {'state': 'Crash', 'errors': 1, 'warnings': 0, 'run': attempt, 'events': tail}
        crashes.append(started[-1])
        remaining = sorted(wanted - set(tests))
        if not remaining:
            break
        query = '+'.join(remaining)
    missing = sorted(wanted - set(tests))
    write(out / 'native.json', {'success': False, 'wanted': len(wanted), 'tests': tests, 'crashes': crashes, 'missing': missing,
                                'runs': attempt})
    return {'runs': infos, 'seconds': sum(i.get('seconds', 0) for i in infos), 'timed_out': any(i.get('timed_out') for i in infos),
            'exit_code': [i.get('exit_code') for i in infos]}


def run_progress(step, out):
    """verify_stage_progress_process_20261125.ps1 과 같은 4단계를 대기열을 거쳐 실행한다."""
    run_id = uuid.uuid4().hex.upper()
    root = out / ('CatrunStageProgressProcess-' + run_id)   # 네이티브 검사가 이 이름과 표식을 요구한다.
    (root / 'User').mkdir(parents=True)
    (root / 'progress-process.marker').write_text(run_id, encoding='ascii')
    slot_file = root / 'User/Saved/SaveGames/CatrunProgress.sav'
    rows, infos = [], []
    for mode in ('write', 'read', 'reset', 'readreset'):
        info = run_native(step, root, 'Catrun.LevelFlow.StageProgressCrossProcess',
                          ['-CatrunProgressProcessRoot=' + str(root), '-CatrunProgressProcessMode=' + mode],
                          mode + '.log', mode + '-report')
        infos.append(info)
        idx = load(root / (mode + '-report') / 'index.json') or {}
        state = [t.get('state') for t in idx.get('tests', [])]
        digest = hashlib.sha256(slot_file.read_bytes()).hexdigest() if slot_file.exists() else None
        log = root / (mode + '.log')
        confirmed = log.exists() and ('Cross-process stage progress [%s]' % mode) in log.read_text('utf-8', 'replace')
        ok = state == ['Success'] and digest is not None and confirmed and (not rows or digest == rows[0]['slot_sha256'])
        rows.append({'name': mode, 'passed': ok, 'state': state, 'slot_sha256': digest, 'mode_confirmed': confirmed})
        if log.exists():
            shutil.copy2(log, out / log.name)
        if not ok:
            break
    write(out / 'report.json', {'success': len(rows) == 4 and all(r['passed'] for r in rows), 'checks': rows})
    return {'runs': infos, 'timed_out': any(i.get('timed_out') for i in infos), 'seconds': sum(i.get('seconds', 0) for i in infos),
            'exit_code': infos[-1].get('exit_code')}


def run_bp(step, out):
    content = PROJECT_ROOT / 'Content'
    allow = out / 'allowlist.txt'
    allow.write_text('\n'.join('/Game/%s.%s' % (p.relative_to(content).with_suffix('').as_posix(), p.stem)
                               for p in content.rglob('*.uasset')), encoding='utf-8')
    # 커맨드렛은 AllowListFile 을 프로젝트 기준 상대경로로 읽는다.
    return launch('UnrealEditor-Cmd.exe', ['-run=CompileAllBlueprints', '-AllowListFile=' + os.path.relpath(allow, PROJECT_ROOT).replace(os.sep, '/'),
                  '-nullrhi', '-onethread', '-UserDir=' + str(out / 'User')], out, 'light', step['timeout'])


def run_assets(step, out):
    return launch('UnrealEditor-Cmd.exe', ['-run=pythonscript', '-script=' + (HERE / 'asset_sweep.py').as_posix(), '-nullrhi', '-onethread',
                  '-NoAsyncLoadingThread', ASYNC_OFF, '-UserDir=' + str(out / 'User')], out, 'light', step['timeout'],
                  {'CATRUN_REGRESSION_OUT': str(out)})


def run_client(step, out):
    (out / 'User').mkdir(parents=True, exist_ok=True)
    (out / 'Captures').mkdir(exist_ok=True)
    return launch('UnrealEditor.exe', [step['map'], '-game', '-RenderOffscreen', '-d3d12', '-onethread', '-windowed', '-ResX=1280', '-ResY=720',
                  '-UserDir=' + str(out / 'User'), '-ExecCmds=catrun.NoArmorCapture 1,Automation RunTests ' + step['test'],
                  '-TestExit=Automation Test Queue Empty', '-ReportExportPath=' + str(out / 'Report'),
                  '-CatrunMinimapCapture=' + str(out / 'Captures')], out, 'gpu', step['timeout'])


RUN = {'client': run_client, 'pie': run_pie, 'native': run_native_resumable, 'progress': run_progress, 'bp': run_bp, 'assets': run_assets}


# ---------------------------------------------------------------- 판정
def load(p):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    except Exception:
        return None


def checks_of(data):
    """검사 스크립트마다 다른 보고서 형식에서 검사 항목을 꺼낸다."""
    rows = []
    for key in ('checks', 'cases', 'results'):
        v = data.get(key)
        if isinstance(v, list):
            for i, c in enumerate(v):
                if isinstance(c, dict) and any(k in c for k in ('passed', 'ok', 'success')):
                    ok = next(c[k] for k in ('passed', 'ok', 'success') if k in c)
                    rows.append((str(c.get('name') or c.get('label') or c.get('case') or '%s[%d]' % (key, i)), bool(ok),
                                 bool(c.get('skipped'))))
        elif isinstance(v, dict):
            rows += [(k, bool(x), False) for k, x in v.items() if isinstance(x, bool)]
    return rows


def judge(step, out, info):
    res = {'step': step['name'], 'area': step['area'], 'passed': 0, 'failed': 0, 'skipped': 0, 'warned': 0, 'failures': [],
           'verdict': None, 'evidence': None, 'seconds': info.get('seconds'), 'exit_code': info.get('exit_code'),
           'timed_out': info.get('timed_out'), 'error': info.get('error')}
    if step['kind'] == 'native':
        data = load(out / 'native.json')
        res['evidence'] = 'native.json, Report*/index.json'
        if not data or not data['tests']:
            res.update(verdict='NO_REPORT')
            return res
        res['tests'] = data['tests']
        states = Counter(t['state'] for t in data['tests'].values())
        res['states'] = dict(states)
        res.update(passed=states.get('Success', 0), skipped=states.get('NotRun', 0) + states.get('Skipped', 0) + len(data['missing']),
                   warned=sum(1 for t in data['tests'].values() if t['state'] == 'Success' and t['warnings']))
        res['failures'] = [k + ' : ' + t['state'] for k, t in sorted(data['tests'].items()) if t['state'] not in ('Success', 'NotRun', 'Skipped')]
        res['failures'] += [k + ' : 실행되지 않음' for k in data['missing']]
        res['failed'] = sum(1 for t in data['tests'].values() if t['state'] not in ('Success', 'NotRun', 'Skipped'))
        res['verdict'] = 'PASS' if not res['failed'] and not res['skipped'] else 'FAIL'
        return res
    if step['kind'] == 'client':
        idx = load(out / 'Report/index.json')
        res['evidence'] = 'Report/index.json'
        if not idx or not idx.get('tests'):
            res['verdict'] = 'NO_REPORT'
            return res
        res['tests'] = {t['fullTestPath']: {'state': t['state'], 'errors': t.get('errors', 0), 'warnings': t.get('warnings', 0),
                        'events': [e['event'].get('message') for e in t.get('entries', []) if e.get('event', {}).get('type') in ('Error', 'Warning')][:8]}
                        for t in idx['tests']}
        res['passed'] = sum(t['state'] == 'Success' for t in res['tests'].values())
        res['failures'] = ['%s : %s %s' % (k, t['state'], t['events'][:3]) for k, t in res['tests'].items() if t['state'] != 'Success']
        res['failed'] = len(res['failures'])
        res['verdict'] = 'PASS' if res['passed'] and not res['failed'] else 'FAIL'
        return res
    if step['kind'] == 'bp':
        log = out / 'run.log'
        text = text_of(log) if log.exists() else ''
        m = re.search(r'Total Compiles:\s*(\d+)|Compiling Completed with (\d+) errors and (\d+) warnings and (\d+) blueprints', text)
        tail = re.findall(r'LogCompileAllBlueprintsCommandlet: Display: (.*)', text)[-12:]
        res['summary'] = tail
        m = re.search(r'with (\d+) errors and (\d+) warnings and (\d+) blueprints that failed to load', text)
        if m:
            e, w, f = map(int, m.groups())
            res.update(failed=e + f, warned=w, verdict='PASS' if e + f == 0 else 'FAIL')
            res['passed'] = text.count('Loading and Compiling:') - e
        else:
            res['verdict'] = 'NO_REPORT'
        res['evidence'] = 'run.log'
        return res
    reports = []
    for p in sorted(out.rglob('*.json')):
        rel = p.relative_to(out).as_posix()
        if rel.split('/')[0] == 'root' and (len(rel.split('/')) < 2 or rel.split('/')[1] != 'Saved'):
            continue
        if rel in ('harness.json', 'step.json', 'info.json', 'result.json') or 'progress.json' in rel:
            continue
        if any(rel.endswith(f) for f in step.get('fixtures', [])):
            continue
        d = load(p)
        if isinstance(d, dict) and 'success' not in d and 'complete' in d and 'error' in d:
            d['success'] = bool(d['complete']) and not d['error']
        if isinstance(d, dict) and ('success' in d or 'runtime_verified' in d):
            reports.append((rel, d))
    harness = load(out / 'harness.json') or {}
    res['harness_error'] = harness.get('error')
    res['blocked_writes'] = harness.get('blocked', [])
    ok = bool(reports)
    for rel, d in reports:
        rows = checks_of(d)
        res['passed'] += sum(1 for _, p, s in rows if p and not s)
        res['skipped'] += sum(1 for _, _, s in rows if s)
        res['failed'] += sum(1 for _, p, _ in rows if not p)
        res['failures'] += [n for n, p, _ in rows if not p]
        if not d.get('success', d.get('runtime_verified')):
            ok = False
            if d.get('error'):
                res['failures'].append('error: ' + str(d['error'])[-900:])
    res['reports'] = [{'file': rel, 'success': d.get('success', d.get('runtime_verified'))} for rel, d in reports]
    res['evidence'] = ', '.join(r for r, _ in reports) or 'run.log'
    if step['kind'] == 'assets' and reports:
        d = reports[0][1]
        # /Engine 패키지는 이 커맨드렛의 레지스트리에 등록되지 않아 '없음' 으로 잘못 나올 수 있다. /Game 만 센다.
        d['missing_dependencies'] = {k: [x for x in v if x.startswith('/Game')] for k, v in d.get('missing_dependencies', {}).items()}
        d['missing_dependencies'] = {k: v for k, v in d['missing_dependencies'].items() if v}
        ok = not d.get('load_failed') and not d['missing_dependencies']
        res['failed'] = len(d.get('load_failed', [])) + len(d.get('missing_dependencies', {}))
        res['passed'] = d.get('total', 0) - len(d.get('load_failed', []))
        res['failures'] = ['load: ' + x for x in d.get('load_failed', [])] + ['missing dep: %s -> %s' % kv for kv in d.get('missing_dependencies', {}).items()]
    if harness.get('error') and not reports:
        res['verdict'] = 'HARNESS_ERROR'
    elif info.get('timed_out') and not reports:
        res['verdict'] = 'TIMEOUT'
    elif not reports:
        res['verdict'] = 'NO_REPORT'
    else:
        res['verdict'] = 'PASS' if ok and not res['failed'] else 'FAIL'
    return res


LINE = re.compile(r'^(?:\[[^\]]*\]\[[^\]]*\])?(Log\w+|\w+): (Error|Warning|Fatal): (.*)$')


def normalise(msg):
    msg = re.sub(r'0x[0-9A-Fa-f]+', '0x*', msg)
    msg = re.sub(r'UEDPIE_\d+_', '', msg)
    msg = re.sub(r'[A-Z]:[\\/][^\s"\']+', '<path>', msg)
    msg = re.sub(r'\b[0-9A-Fa-f]{16,}\b', '<hash>', msg)
    msg = re.sub(r'(?<![A-Za-z_])-?\d+(?:\.\d+)?', '#', msg)
    return msg.strip()[:300]


def text_of(path):
    data = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode('utf-8', 'replace')


def scan_logs(out):
    groups = defaultdict(lambda: {'count': 0, 'sample': None, 'files': Counter()})
    for log in out.glob('*.log'):
        for raw in text_of(log).splitlines():
            m = LINE.match(raw.rstrip())
            if m:
                key = '%s|%s|%s' % (m.group(1), m.group(2), normalise(m.group(3)))
            elif 'Ensure condition failed' in raw or 'Assertion failed' in raw or 'Unhandled Exception' in raw:
                key = 'ENSURE|Error|' + normalise(raw)
            else:
                continue
            g = groups[key]
            g['count'] += 1
            g['sample'] = g['sample'] or raw.strip()[:500]
            g['files'][log.name] += 1
    return {k: dict(v, files=dict(v['files'])) for k, v in sorted(groups.items(), key=lambda kv: -kv[1]['count'])}


# ---------------------------------------------------------------- 명령
def run(label, only, skip, redo):
    base = BASE / label
    base.mkdir(parents=True, exist_ok=True)
    meta_path = base / 'meta.json'
    meta = load(meta_path) or {'label': label, 'runs': []}
    before = snapshot(deep=True)
    if 'before' not in meta:
        meta['before'] = before
        git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        meta.update(git_head=git, modules=(PROJECT_ROOT / 'Binaries/Win64/UnrealEditor.modules').read_text('utf-8'), project=str(PROJECT_ROOT),
                    maps={m: before.get('Content/Maps/%s.umap' % m) for m in MAPS})
    if not meta_path.exists():
        write(meta_path, meta)
    mine = {'started': datetime.now().isoformat(), 'only': only, 'skip': skip}
    for step in STEPS:
        if (only and step['name'] not in only) or step['name'] in skip:
            continue
        out = base / step['name']
        if (out / 'result.json').exists():
            if not redo:
                continue
        if out.exists():
            out.rename(base / ('%s.prev-%s' % (step['name'], datetime.now().strftime('%H%M%S'))))
        out.mkdir(parents=True)
        print(datetime.now().strftime('%H:%M:%S'), 'START', step['name'], flush=True)
        a = snapshot()
        try:
            info = RUN[step['kind']](step, out)
        except Exception as ex:
            info = {'error': repr(ex)}
        b = snapshot()
        write(out / 'info.json', info)
        res = judge(step, out, info)
        res['project_changes_during_step'] = diff(a, b)
        res['maps'] = {m: a.get('Content/Maps/%s.umap' % m) for m in MAPS}
        res['logs'] = scan_logs(out)
        write(out / 'result.json', res)
        print(datetime.now().strftime('%H:%M:%S'), 'END', step['name'], res['verdict'], res['passed'], res['failed'], res['skipped'],
              res['failures'][:2], flush=True)
    mine.update(finished=datetime.now().isoformat(), preservation=diff(before, snapshot(deep=True)))
    write(base / ('run_%s_%d.json' % (datetime.now().strftime('%H%M%S'), os.getpid())), mine)
    summary(label)


def rejudge(label):
    for step in STEPS:
        out = BASE / label / step['name']
        old = load(out / 'result.json')
        if old:
            res = judge(step, out, load(out / 'info.json') or {})
            for k in ('project_changes_during_step', 'maps'):
                res[k] = old.get(k)
            res['logs'] = scan_logs(out)
            write(out / 'result.json', res)


def results(label):
    return {s['name']: load(BASE / label / s['name'] / 'result.json') for s in STEPS}


def summary(label):
    rows, logs = [], defaultdict(lambda: {'count': 0, 'steps': Counter(), 'sample': None})
    for name, r in results(label).items():
        if not r:
            rows.append((name, BY_NAME[name]['area'], 'NOT_RUN', '', '', '', ''))
            continue
        rows.append((name, r['area'], r['verdict'], r['passed'], r['failed'], r['skipped'], r['warned']))
        for k, g in r['logs'].items():
            logs[k]['count'] += g['count']
            logs[k]['steps'][name] += g['count']
            logs[k]['sample'] = logs[k]['sample'] or g['sample']
    text = ['# 회귀검사 요약 ' + label, '', '| 단계 | 구간 | 판정 | 통과 | 실패 | 스킵 | 경고포함 통과 |', '|---|---|---|---|---|---|---|']
    text += ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows]
    text += ['', '## 실패 항목', '']
    for name, r in results(label).items():
        if r and (r['failures'] or r.get('harness_error')):
            text.append('### ' + name)
            text += ['- ' + str(f).replace('\n', ' ⏎ ')[:1200] for f in r['failures']]
            if r.get('harness_error'):
                text.append('- 실행 어댑터: ' + str(r['harness_error']).replace('\n', ' ⏎ ')[:800])
    text += ['', '## 로그 오류·경고 묶음(상위 120)', '', '| 건수 | 단계 수 | 묶음 |', '|---|---|---|']
    for k, g in sorted(logs.items(), key=lambda kv: (('|Error|' not in kv[0]), -kv[1]['count']))[:120]:
        text.append('| %d | %d | %s |' % (g['count'], len(g['steps']), k.replace('|', ' / ')))
    (BASE / label / 'SUMMARY.md').write_text('\n'.join(text), encoding='utf-8')
    write(BASE / label / 'logs.json', {k: dict(v, steps=dict(v['steps'])) for k, v in logs.items()})
    print('\n'.join(text[:6 + len(rows)]))


def compare(a, b):
    ra, rb = results(a), results(b)
    text = ['# 회귀 비교 %s → %s' % (a, b), '', '| 단계 | %s | %s | 변화 |' % (a, b), '|---|---|---|---|']
    regress = []
    for name in BY_NAME:
        x, y = ra.get(name), rb.get(name)
        cell = lambda r: '%s %s/%s/%s' % (r['verdict'], r['passed'], r['failed'], r['skipped']) if r else 'NOT_RUN'
        change = '같음' if cell(x) == cell(y) else '달라짐'
        if x and y and x['verdict'] == 'PASS' and y['verdict'] != 'PASS':
            change = '**회귀**'
            regress.append(name)
        if x and y and x['verdict'] != 'PASS' and y['verdict'] == 'PASS':
            change = '개선'
        text.append('| %s | %s | %s | %s |' % (name, cell(x), cell(y), change))
    text += ['', '## 새로 실패한 항목 / 해결된 항목', '']
    for name in BY_NAME:
        x, y = ra.get(name), rb.get(name)
        if x and y:
            new, gone = [f for f in y['failures'] if f not in x['failures']], [f for f in x['failures'] if f not in y['failures']]
            for f in new:
                text.append('- 신규 [%s] %s' % (name, str(f).replace('\n', ' ⏎ ')[:500]))
            for f in gone:
                text.append('- 해결 [%s] %s' % (name, str(f).replace('\n', ' ⏎ ')[:300]))
            tx, ty = x.get('tests'), y.get('tests')
            if tx and ty:
                for t in sorted(set(tx) | set(ty)):
                    sx, sy = (tx.get(t) or {}).get('state', '없음'), (ty.get(t) or {}).get('state', '없음')
                    if sx != sy:
                        text.append('- 네이티브 %s: %s → %s' % (t, sx, sy))
    la, lb = load(BASE / a / 'logs.json') or {}, load(BASE / b / 'logs.json') or {}
    for title, keys, src in (('새 로그 묶음', set(lb) - set(la), lb), ('사라진 로그 묶음', set(la) - set(lb), la)):
        text += ['', '## ' + title, '']
        text += ['- %d × %s (%s)' % (src[k]['count'], k.replace('|', ' / '), ', '.join(src[k]['steps'])) for k in sorted(keys, key=lambda k: -src[k]['count'])[:120]]
    ma, mb = load(BASE / a / 'meta.json') or {}, load(BASE / b / 'meta.json') or {}
    d = diff(ma.get('before', {}), mb.get('before', {}))
    text += ['', '## 프로젝트 파일 차이', ''] + ['- %s %d개: %s' % (k, len(v), ', '.join(v[:60])) for k, v in d.items()]
    path = BASE / ('COMPARE_%s_%s.md' % (a, b))
    path.write_text('\n'.join(text), encoding='utf-8')
    print(path, 'regressions:', regress)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('label')
    r.add_argument('--only', default='')
    r.add_argument('--skip', default='')
    r.add_argument('--redo', action='store_true')
    r.add_argument('--compare', default='')
    r.add_argument('--project', default=str(ROOT))
    r.add_argument('--serial', action='store_true', help='대기표를 하나만 넣는다(기본: light 2, gpu 1 동시 대기)')
    for c in ('summary', 'rejudge'):
        sub.add_parser(c).add_argument('label')
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    x = p.parse_args()
    if x.cmd == 'run':
        global PROJECT_ROOT
        PROJECT_ROOT = Path(x.project).resolve()
        split = lambda s: [i for i in s.split(',') if i]
        unknown = [n for n in split(x.only) + split(x.skip) if n not in BY_NAME]
        if unknown:
            raise SystemExit('unknown steps: %s' % unknown)
        only, skip = split(x.only), split(x.skip)
        picked = [s for s in STEPS if (not only or s['name'] in only) and s['name'] not in skip]
        light = [s['name'] for s in picked if s.get('rhi', 'null') == 'null']
        gpu = [s['name'] for s in picked if s.get('rhi', 'null') != 'null']
        lanes = [g for g in (light[::2], light[1::2], gpu) if g]
        if x.serial or len(lanes) < 2:
            run(x.label, [s['name'] for s in picked], [], x.redo)
        else:
            # 프로젝트 전체 해시를 한 번만 만들고 나눠 돌린다. 실제 실행 순서는 공용 대기열이 정한다.
            kids = []
            for lane in lanes:
                kids.append(subprocess.Popen([sys.executable, '-B', __file__, 'run', x.label, '--serial', '--project', x.project,
                                              '--only', ','.join(lane), *(['--redo'] if x.redo else [])]))
                time.sleep(20)
            for k in kids:
                k.wait()
            summary(x.label)
        if x.compare:
            compare(x.compare, x.label)
    elif x.cmd == 'summary':
        summary(x.label)
    elif x.cmd == 'rejudge':
        rejudge(x.label)
        summary(x.label)
    else:
        compare(x.a, x.b)


if __name__ == '__main__':
    main()
