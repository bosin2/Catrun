"""Task-owned editor channel on loopback multicast 6777 (not shared MCP 8000)."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,r'C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution as re
config=re.RemoteExecutionConfig();config.multicast_group_endpoint=('239.0.0.1',6777);config.command_endpoint=('127.0.0.1',6787)
r=re.RemoteExecution(config);r.start()
try:
    end=time.monotonic()+5
    while not r.remote_nodes and time.monotonic()<end:time.sleep(.15)
    assert len(r.remote_nodes)==1,r.remote_nodes
    r.open_command_connection(r.remote_nodes[0]['node_id'])
    if len(sys.argv)>1:
        p=Path(sys.argv[1]).resolve();code='exec(compile('+repr(p.read_text(encoding='utf-8-sig'))+','+repr(str(p))+',"exec"),{"__name__":"__main__"})'
    else:code='import unreal,os;print(os.getpid());print(unreal.Paths.get_project_file_path())'
    # The payload is one exec(...) statement, not a path. ExecuteFile can
    # mistake an embedded .py string in a script/comment for the filename.
    result=r.run_command(code,unattended=True,exec_mode=re.MODE_EXEC_STATEMENT);result.pop('command',None)
    print(json.dumps(result,ensure_ascii=False));assert result['success'],result
finally:r.stop()
