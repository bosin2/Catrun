"""기준 네이티브 검사에서 크래시 때문에 실행되지 않은 나머지를 채우고, 이전 DLL 에서 같은 크래시가 나는지 본다.

  python -B Scripts/Regression20261126/native_rest.py

대기열은 한 번만 잡는다(이 스크립트 PID 를 attach). 격리 사본과 격리 UserDir 만 쓴다.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_regression as r

r.PROJECT_ROOT = r.BASE / 'BaselineProject'
OUT = r.BASE / 'Baseline/native'
OLD = r.BASE / 'OldDllProject'
BUDGET = 15 * 60


def old_project():
    """15:54 정식 빌드 DLL(UnrealEditor-Catrun.dll)을 쓰는 같은 콘텐츠의 사본."""
    OLD.mkdir(exist_ok=True)
    for name in ('Content', 'Config', 'Source', 'Plugins'):
        link = OLD / name
        if not link.exists():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(r.PROJECT_ROOT / name)], check=True, capture_output=True)
    b = OLD / 'Binaries/Win64'
    b.mkdir(parents=True, exist_ok=True)
    shutil.copy2(r.PROJECT_ROOT / 'Catrun.uproject', OLD / 'Catrun.uproject')
    for f in ('UnrealEditor-Catrun.dll',):
        shutil.copy2(r.PROJECT_ROOT / 'Binaries/Win64' / f, b / f)
    pdb = r.ROOT / 'Binaries/Win64/UnrealEditor-Catrun.pdb'
    if pdb.exists():
        shutil.copy2(pdb, b / pdb.name)
    (b / 'UnrealEditor.modules').write_text(json.dumps({'BuildId': '55116800', 'Modules': {'Catrun': 'UnrealEditor-Catrun.dll'}}), encoding='utf-8')


def run(project, out, query, tag, timeout=1500):
    user = out / 'User'
    user.mkdir(parents=True, exist_ok=True)
    log = out / (tag + '.log')
    args = r.command_line([str(r.UE / 'UnrealEditor-Cmd.exe'), str(project / 'Catrun.uproject'), '-nullrhi', '-UserDir=' + str(user),
                           '-ReportExportPath=' + str(out / ('Report_' + tag)), '-ExecCmds=Automation RunTests ' + query,
                           '-TestExit=Automation Test Queue Empty', *r.COMMON, '-abslog=' + str(log)])
    p = subprocess.Popen(args, cwd=str(project), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        p.wait(timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(60)
    return log, r.load(out / ('Report_' + tag) / 'index.json')


def absorb(tests, log, idx, tag):
    if idx:
        for t in idx['tests']:
            tests[t['fullTestPath']] = {
                'state': t['state'], 'errors': t.get('errors', 0), 'warnings': t.get('warnings', 0), 'run': tag,
                'events': [e['event'].get('message') for e in t.get('entries', []) if e.get('event', {}).get('type') in ('Error', 'Warning')][:8]}
        return None
    text = r.text_of(log) if log.exists() else ''
    for state, path in r.DONE.findall(text):
        tests.setdefault(path, {'state': state, 'errors': 0, 'warnings': 0, 'run': tag, 'events': ['크래시한 실행의 로그에서 읽음']})
    started = [p for p in r.BEGIN.findall(text) if p not in tests]
    if started:
        tail = [x for x in text.splitlines() if 'Unhandled Exception' in x or ('[Callstack]' in x and 'Catrun' in x)][:8]
        tests[started[-1]] = {'state': 'Crash', 'errors': 1, 'warnings': 0, 'run': tag, 'events': tail}
        return started[-1]
    return 'NO_PROGRESS'


def main():
    data = r.load(OUT / 'native.json')
    tests, wanted = data['tests'], r.test_names()
    old_project()
    q = r.slot('acquire', 'regression-native-rest', '--kind', 'light', '--wait', '7200')
    if q.returncode:
        raise SystemExit(q.stderr)
    token = q.stdout.strip().splitlines()[-1]
    r.slot('attach', token, str(os.getpid()))
    start = time.time()
    n = 0
    try:
        remaining = sorted(wanted - set(tests))
        first = [x for x in remaining if not x.startswith('Catrun.PrototypeAI.')]
        while first and time.time() - start < BUDGET:
            n += 1
            crash = absorb(tests, *run(r.PROJECT_ROOT, OUT, '+'.join(first), 'rest%02d' % n), 'rest%02d' % n)
            print('rest%02d' % n, len(first), 'crash:', crash, flush=True)
            if crash == 'NO_PROGRESS':
                break
            first = [x for x in first if x not in tests] if crash else []
        # 이전 DLL: 대표 크래시 두 개
        old = {}
        for k, name in enumerate(('Catrun.LevelFlow.ManualRestartDuringCaptureReleasesCaptureOwnership',
                                  'Catrun.PrototypeAI.ArmorCaptureRequiresClearBodyPath'), 1):
            oo = r.BASE / 'OldDllNative'
            log, idx = run(OLD, oo, name, 'old%d' % k, 900)
            absorb(old, log, idx, 'old%d' % k)
            text = r.text_of(log) if log.exists() else ''
            print('old', name, old.get(name, {}).get('state'), 'Catrun_ElevatorRevision3 loaded:', 'ElevatorRevision3' in text, flush=True)
        r.write(r.BASE / 'OldDllNative/result.json', old)
        while time.time() - start < BUDGET:
            left = sorted(x for x in wanted - set(tests))
            if not left:
                break
            n += 1
            crash = absorb(tests, *run(r.PROJECT_ROOT, OUT, '+'.join(left), 'rest%02d' % n), 'rest%02d' % n)
            print('rest%02d' % n, len(left), 'crash:', crash, flush=True)
            if crash == 'NO_PROGRESS':
                break
    finally:
        r.slot('release', token)
        data.update(tests=tests, missing=sorted(wanted - set(tests)), crashes=sorted(k for k, t in tests.items() if t['state'] == 'Crash'))
        r.write(OUT / 'native.json', data)
    print('done', {s: sum(1 for t in tests.values() if t['state'] == s) for s in {t['state'] for t in tests.values()}}, 'missing', len(data['missing']))


if __name__ == '__main__':
    main()
