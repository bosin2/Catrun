"""Small loopback-only MCP client for the running Catrun editor.

Used when the desktop Unreal connector is not exposed. It talks to the same
editor MCP endpoint, not a separate editor or a configuration-only substitute.
"""
import json
import sys
import urllib.request
from pathlib import Path

class EditorMCP:
    def __init__(self):
        self.url = 'http://127.0.0.1:8000/mcp'
        self.headers = {'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        self.counter = 0
        self.rpc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'catrun-local-verification','version':'1.0'}})
        self.rpc('notifications/initialized', {}, notification=True)

    def rpc(self, method, params, notification=False):
        self.counter += 1
        payload = {'jsonrpc':'2.0','method':method,'params':params}
        if not notification: payload['id'] = self.counter
        request = urllib.request.Request(self.url,json.dumps(payload).encode(),self.headers)
        with urllib.request.urlopen(request,timeout=45) as response:
            session = response.headers.get('mcp-session-id')
            if session: self.headers['mcp-session-id'] = session
            body = response.read().decode()
        if not body: return None
        if body.lstrip().startswith('{'): message = json.loads(body)
        else:
            messages = [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith('data:')]
            message = next((item for item in messages if item.get('id')==self.counter), messages[-1] if messages else {})
        if 'error' in message: raise RuntimeError(message['error'])
        return message.get('result')

    def call(self, name, arguments=None):
        result = self.rpc('tools/call', {'name':name,'arguments':arguments or {}})
        if result and result.get('isError'): raise RuntimeError(result)
        return result

if __name__ == '__main__':
    client = EditorMCP()
    if len(sys.argv)>1:
        request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        print(json.dumps(client.call(request['name'],request.get('arguments',{})),ensure_ascii=False))
    else:
        result=client.rpc('tools/list',{})
        print(json.dumps([t['name'] for t in result['tools']],ensure_ascii=False))
