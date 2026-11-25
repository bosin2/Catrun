"""격리 실행 어댑터. 기존 검사 스크립트 원본을 고치지 않고 에디터 안에서 실행한다.

환경변수 CATRUN_REGRESSION_STEP = 단계 설정 JSON 경로.
- unreal.Paths.project_dir() 를 단계별 격리 루트로 바꿔 결과를 그 안에만 쓰게 한다.
- 본 프로젝트의 Saved 에 쓰려는 파일은 격리 루트로 돌리고, 그 밖의 본 프로젝트 쓰기는 막는다.
- 에셋·맵 저장 라이브러리 호출은 막고 기록한다.
"""
import builtins
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

import unreal

sys.dont_write_bytecode = True
CFG = json.loads(Path(os.environ['CATRUN_REGRESSION_STEP']).read_text(encoding='utf-8'))
REAL = Path(CFG['project'])
FAKE = Path(CFG['root'])
OUT = Path(CFG['out'])
H = {'script': CFG['script'], 'started': time.time(), 'blocked': [], 'redirected': [], 'error': None}
_open, _mkdir = io.open, os.mkdir


def flush():
    with _open(OUT / 'harness.json', 'w', encoding='utf-8') as f:
        json.dump(H, f, ensure_ascii=False, indent=2)


def norm(p):
    return os.path.normcase(os.path.abspath(os.fspath(p)))


N_REAL, N_FAKE, N_OUT, N_SAVED = norm(REAL), norm(FAKE), norm(OUT), norm(REAL / 'Saved')


def mkdirs(p):
    p = Path(p)
    if not p.exists():
        mkdirs(p.parent)
        try:
            _mkdir(p)
        except FileExistsError:
            pass


def remap(path, write):
    if not isinstance(path, (str, os.PathLike)):
        return path
    n = norm(path)
    if n == N_OUT or n.startswith(N_OUT + os.sep):
        # 격리 루트 안 정션(Content, Scripts 등)을 통해 원본에 쓰는 것을 막는다.
        if write and n.startswith(N_FAKE + os.sep):
            top = n[len(N_FAKE) + 1:].split(os.sep)[0]
            if top not in ('saved', 'intermediate', 'user'):
                H['blocked'].append(n)
                flush()
                raise PermissionError('regression harness: junction write blocked ' + n)
        if not write and n.startswith(N_FAKE + os.sep + 'saved' + os.sep) and not os.path.exists(n):
            # 과거 납품 보고서를 입력으로 읽는 검사: 격리 폴더에 없으면 본 프로젝트 것을 읽기만 한다.
            original = os.path.join(str(REAL), 'Saved', n[len(N_FAKE + os.sep + 'saved' + os.sep):])
            if os.path.exists(original):
                return original
        return path
    if n.startswith(N_SAVED + os.sep):
        target = FAKE / 'Saved' / os.path.relpath(os.path.abspath(os.fspath(path)), REAL / 'Saved')
        if write:
            mkdirs(target.parent)
            H['redirected'].append(str(target))
            return str(target)
        return str(target) if os.path.exists(target) else path
    if write and n.startswith(N_REAL + os.sep):
        H['blocked'].append(n)
        flush()
        raise PermissionError('regression harness: project write blocked ' + n)
    return path


def guarded_open(file, mode='r', *a, **k):
    return _open(remap(file, any(c in mode for c in 'wax+')), mode, *a, **k)


def guarded_mkdir(path, *a, **k):
    if os.path.isdir(path):
        raise FileExistsError(path)
    target = remap(path, True)
    if target is not path:
        mkdirs(target)
        return
    return _mkdir(path, *a, **k)


builtins.open = guarded_open
io.open = guarded_open
os.mkdir = guarded_mkdir


def guard(fn):
    def inner(path, *a, **k):
        rest = [remap(x, True) if isinstance(x, (str, os.PathLike)) else x for x in a]
        return fn(remap(path, True), *rest, **k)
    return inner


for name in ('remove', 'unlink', 'rmdir', 'rename', 'replace'):
    setattr(os, name, guard(getattr(os, name)))

SPELLINGS = [str(REAL / 'Saved').replace('\\', '/'), str(REAL / 'Saved')]
OUT_TEXT = str(OUT).replace('\\', '/').lower()


def remap_text(value):
    if isinstance(value, str) and OUT_TEXT not in value.replace('\\', '/').lower():
        for s in SPELLINGS:
            i = value.lower().find(s.lower())
            if i >= 0:
                return value[:i] + str(FAKE / 'Saved').replace('\\', '/') + value[i + len(s):]
    return value


class LibProxy:
    """정적 함수 라이브러리의 문자열 경로 인자를 격리 경로로 바꾼다."""

    def __init__(self, real, overrides=None):
        self.__dict__['_real'] = real
        self.__dict__['_over'] = overrides or {}

    def __getattr__(self, name):
        if name in self.__dict__['_over']:
            return self.__dict__['_over'][name]
        value = getattr(self.__dict__['_real'], name)
        if callable(value) and not isinstance(value, type):
            def call(*a, **k):
                return value(*[remap_text(x) for x in a], **{q: remap_text(x) for q, x in k.items()})
            return call
        return value


def deny(name):
    def blocked(*a, **k):
        H['blocked'].append(name + ' ' + repr(a)[:200])
        flush()
        raise PermissionError('regression harness: ' + name + ' blocked')
    return blocked


FAKE_TEXT = str(FAKE).replace('\\', '/') + '/'
unreal.Paths = LibProxy(unreal.Paths, {'project_dir': lambda: FAKE_TEXT})
for lib in ('SystemLibrary', 'AutomationLibrary', 'CatrunAuthoringLibrary', 'RenderingLibrary'):
    if hasattr(unreal, lib):
        setattr(unreal, lib, LibProxy(getattr(unreal, lib)))
for lib in ('EditorAssetLibrary', 'EditorLoadingAndSavingUtils'):
    if hasattr(unreal, lib):
        real_lib = getattr(unreal, lib)
        banned = {n: deny(lib + '.' + n) for n in dir(real_lib)
                  if n.startswith(('save_', 'delete_', 'rename_', 'duplicate_'))}
        setattr(unreal, lib, LibProxy(real_lib, banned))

real_get_subsystem = unreal.get_editor_subsystem


class SubsystemProxy:
    """에디터 서브시스템의 저장 계열 호출만 막고 나머지는 그대로 넘긴다."""

    def __init__(self, real):
        self.__dict__['_real'] = real

    def __getattr__(self, name):
        if name.startswith('save_'):
            return deny(type(self.__dict__['_real']).__name__ + '.' + name)
        return getattr(self.__dict__['_real'], name)


def get_editor_subsystem(cls):
    sub = real_get_subsystem(cls)
    return SubsystemProxy(sub) if sub and cls.__name__ in ('LevelEditorSubsystem', 'EditorAssetSubsystem') else sub


unreal.get_editor_subsystem = get_editor_subsystem

WATCH = {'ended': False, 'deadline': time.monotonic() + CFG['timeout']}


def watchdog(_dt):
    """스크립트 자체 종료가 동작하지 않을 때 이 검사 프로세스만 정상 종료한다."""
    if time.monotonic() < WATCH['deadline']:
        return
    if not WATCH['ended']:
        WATCH['ended'] = True
        H['error'] = H['error'] or 'harness watchdog: not finished in %ss' % CFG['timeout']
        flush()
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        except Exception:
            pass
        return
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not ed.get_game_world() or time.monotonic() > WATCH['deadline'] + 20:
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'QUIT_EDITOR')


WATCH['handle'] = unreal.register_slate_post_tick_callback(watchdog)
flush()
try:
    script = FAKE / CFG['script']
    src = script.read_text(encoding='utf-8-sig')
    src = src.replace('C:/Users/whghk/Catrun/Saved', str(FAKE / 'Saved').replace('\\', '/'))
    for old, new in CFG.get('patch', []):
        assert old in src, ('patch anchor missing', old)
        src = src.replace(old, new)
    ns = {'__name__': CFG.get('run_name', '__main__'), '__file__': str(script), '__builtins__': builtins}
    sys.path.insert(0, str(script.parent))
    unreal._catrun_regression_ns = ns
    exec(compile(src, str(script), 'exec'), ns)
    H['loaded'] = True
    flush()
except BaseException:
    H['error'] = traceback.format_exc()
    flush()
    unreal.log_error('REGRESSION_HARNESS ' + H['error'])
    WATCH['deadline'] = time.monotonic() + 1
