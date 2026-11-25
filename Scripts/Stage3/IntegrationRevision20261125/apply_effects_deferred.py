"""Wait for loaded editor physics/render registration before strict save preflight."""
import importlib.util
import json
import os
import time
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
assert ED.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
S = {'started': time.monotonic(), 'ticks': 0, 'initial_finish_all_returned': False}
u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')
S['initial_finish_all_returned'] = True
S['ready_started'] = time.monotonic()


def tick(_dt):
    S['ticks'] += 1
    if S['ticks'] < 30 or time.monotonic() - S['ready_started'] < 3:
        return
    u.unregister_slate_post_tick_callback(S['handle'])
    try:
        u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')
        folder = ROOT / 'Saved/Stage3IntegrationRevision20261125' / os.environ.get('CATRUN_STAGE3_EFFECTS_PASS', 'Effects03')
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'readiness.json').write_text(json.dumps({k: v for k, v in S.items() if k != 'handle'}, indent=2), encoding='utf8')
        name = os.environ.get('CATRUN_STAGE3_WRITE_SCRIPT', 'apply_effects.py')
        assert name in ('apply_effects.py', 'apply_followup.py', 'apply_fx_orientation.py', 'apply_stage2_dust_match.py', 'apply_camera_pillars_basket.py')
        spec = importlib.util.spec_from_file_location('stage3_deferred_writer', ROOT / 'Scripts/Stage3/IntegrationRevision20261125' / name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')


S['handle'] = u.register_slate_post_tick_callback(tick)
