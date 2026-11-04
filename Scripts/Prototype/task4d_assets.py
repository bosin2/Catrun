"""Task4d package ownership and small checked Blueprint graph helpers."""
import unreal,json,hashlib,shutil,datetime
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.actor import ActorTools
from toolset_registry.helpers import compile_blueprint as compile_checked
ROOT=Path(unreal.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Prototype20261104/Task4d';OUT.mkdir(exist_ok=True)
AS=unreal.EditorAssetLibrary;AT=unreal.AssetToolsHelpers.get_asset_tools()
BASE='/Game/Systems/Interaction/Puzzles/Presentation';PRES=BASE+'/BP_StatuePresentation';BARS=BASE+'/M_StatueRevealBars';DUST=BASE+'/M_GateFloorDust'
mp=OUT/'manifest.json';manifest=json.loads(mp.read_text()) if mp.exists() else {'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existing':[],'new':[]}
def save_manifest():mp.write_text(json.dumps(manifest,indent=2),encoding='utf8')
def backup(path,ext='.uasset'):
 if any(x['asset']==path for x in manifest['existing']):return
 rel='Content/'+path.removeprefix('/Game/')+ext;dst=OUT/'Backups'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dst)
 dirty=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
 row={'asset':path,'file':rel,'before_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'was_dirty':path in dirty}
 assert not row['was_dirty'],'Capture dirty snapshot before modifying '+path
 manifest['existing'].append(row);save_manifest()
def new(path,cls,factory):
 if AS.does_asset_exist(path):
  assert path in manifest['new'],'Unowned asset: '+path
  return AS.load_asset(path)
 o=AT.create_asset(path.rsplit('/',1)[1],path.rsplit('/',1)[0],cls,factory);assert o
 manifest['new'].append(path);save_manifest();return o
def strict(bp):
 compile_checked(bp,True);assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
 assert AS.save_loaded_asset(bp,False)
def graph(bp,name='EventGraph'):return BP.get_graph(bp,name)
def ed(g):return unreal.BlueprintGraphEditor.get_graph_editor(g)
def inp(n,p):
 q=n.find_input_pin(p);assert q,(n,p);return q
def outp(n,p):
 q=n.find_output_pin(p);assert q,(n,p);return q
def connect(a,ap,b,bp):assert outp(a,ap).try_create_connection(inp(b,bp)),(a,ap,b,bp)
def value(n,p,v):assert inp(n,p).set_pin_value(str(v)),(n,p,v)
def fn(g,name):
 n=ed(g).add_call_function_node(name);assert n,name;return n
def node(g,suffix,cls=None):
 choices=list(dict.fromkeys(str(x) for x in ed(g).list_available_nodes([]) if str(x).endswith('|'+suffix)))
 assert len(choices)==1,(suffix,choices)
 n=BP.create_node(g,choices[0],unreal.IntPoint(0,0),cls);assert n;return n
def get(g,name,cls=''):return ed(g).add_get_member_variable_node(name,cls)
def setv(g,name,cls=''):return ed(g).add_set_member_variable_node(name,cls)
def dump(bp):
 return {'asset':bp.get_path_name(),'status':str(bp.get_editor_property('status')),'graphs':[{'name':g.get_name(),'nodes':[{'name':i.node.get_name(),'class':i.node.get_class().get_name(),'type':i.type_id,'input':[{'name':p.name,'value':str(p.value),'links':str(p.connected_pins)} for p in i.input_pins],'output':[{'name':p.name,'links':str(p.connected_pins)} for p in i.output_pins]} for i in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]}
