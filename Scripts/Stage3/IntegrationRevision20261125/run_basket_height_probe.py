"""Root read-only saved-world basket probe after physics registration."""
import importlib.util
import time
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world()
assert ed.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
state = {'start': time.monotonic(), 'ticks': 0}
u.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')


def tick(_dt):
    state['ticks'] += 1
    if state['ticks'] < 30 or time.monotonic() - state['start'] < 3:
        return
    u.unregister_slate_post_tick_callback(state['handle'])
    try:
        u.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')
        path = root / 'Scripts/Stage3/BasketHeightRevision20261125/probe.py'
        spec = importlib.util.spec_from_file_location('s3_basket_height_probe', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
    finally:
        u.SystemLibrary.execute_console_command(ed.get_editor_world(), 'QUIT_EDITOR')


state['handle'] = u.register_slate_post_tick_callback(tick)
