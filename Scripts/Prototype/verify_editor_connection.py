"""Verify the live editor map, then enable temporary loopback Python for inspection."""
import json
from ue_mcp import EditorMCP
client=EditorMCP()
print('LIVE_LEVEL',json.dumps(client.call('call_tool',{'toolset_name':'editor_toolset.toolsets.scene.SceneTools','tool_name':'get_current_level','arguments':{}})))
print('TEMPORARY_PYTHON',json.dumps(client.call('call_tool',{'toolset_name':'editor_toolset.toolsets.object.ObjectTools','tool_name':'set_properties','arguments':{'instance':{'refPath':'/Script/PythonScriptPlugin.Default__PythonScriptPluginSettings'},'values':json.dumps({'bRemoteExecution':True})}})))
