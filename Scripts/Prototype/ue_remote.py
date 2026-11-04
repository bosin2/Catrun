"""Run a project inspection/validation script in the existing local Unreal editor.

Uses Epic's installed Python remote-execution protocol on loopback only.
Remote execution is enabled temporarily by the integration controller, not saved.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution

parser = argparse.ArgumentParser()
parser.add_argument('script', nargs='?')
parser.add_argument('--isolated', action='store_true', help='Execute temporary scripts in a separate namespace, then collect Python wrappers. Slate callbacks retain their own scope until unregistered.')
args = parser.parse_args()
remote = remote_execution.RemoteExecution()
remote.start()
try:
    deadline = time.monotonic() + 5
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(.2)
    nodes = [n for n in remote.remote_nodes if n.get('project_name') == 'Catrun']
    if len(nodes) != 1:
        raise RuntimeError('Expected exactly one Catrun editor: ' + str(remote.remote_nodes))
    remote.open_command_connection(nodes[0]['node_id'])
    if args.script:
        script = Path(args.script).resolve()
        command = 'exec(compile(' + repr(script.read_text(encoding='utf-8-sig')) + ', ' + repr(str(script)) + ", 'exec')" + (', {"__name__": "__catrun_remote_script__"})' if args.isolated else ')')
        if args.isolated: command = 'import gc; gc.collect(); ' + command + '; gc.collect()'
    else:
        command = 'import unreal; print(unreal.Paths.get_project_file_path()); print(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name())'
    result = remote.run_command(command, unattended=True, exec_mode=remote_execution.MODE_EXEC_STATEMENT if args.isolated else remote_execution.MODE_EXEC_FILE)
    result.pop('command', None)
    print(json.dumps(result, ensure_ascii=False))
    if not result.get('success'):
        raise SystemExit(1)
finally:
    remote.stop()
