"""Narrow, guarded bell ownership patch. Existing presentation nodes/assets are retained.
Run via ue_remote.py --isolated with PIE stopped. Repeat runs verify/reuse only.
"""
import unreal, json, hashlib, re
from decimal import Decimal
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint
ROOT=Path(unreal.Paths.project_dir()).resolve()
BASE=ROOT/'.superpowers/sdd/2026-11-04-playable-prototype/final-fix-before'
OUT=ROOT/'Saved/Prototype20261104/FinalFix'; OUT.mkdir(exist_ok=True)
PATH='/Game/Systems/Player/Interaction/BP_CatActions'
FILE=ROOT/'Content/Systems/Player/Interaction/BP_CatActions.uasset'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), 'Start from a clean editor'
bp=unreal.load_asset(PATH); assert bp
def graph(name): return BP.get_graph(bp,name)
def nodes(g): return {n.get_name():n for n in BP.find_nodes(g)}
def inp(n,p):
 q=n.find_input_pin(p); assert q,(n,p); return q
def out(n,p):
 q=n.find_output_pin(p); assert q,(n,p); return q
def connect(a,ap,b,bp): assert out(a,ap).try_create_connection(inp(b,bp)),(a,ap,b,bp)
def cut(a,ap,b,bp): assert out(a,ap).break_single_pin_link(inp(b,bp)),(a,ap,b,bp)
def dump():
 return {'asset':bp.get_path_name(),'status':str(bp.get_editor_property('status')),'variables':list(map(str,BP.list_variables(bp))),
  'graphs':[{'name':g.get_name(),'nodes':[{'name':i.node.get_name(),'class':i.node.get_class().get_name(),'type':i.type_id,'position':[i.position.x,i.position.y],
   'input':[{'name':p.name,'value':str(p.value),'links':[{'node':q.node.get_name(),'index':q.index_id,'direction':str(q.direction)} for q in p.connected_pins]} for p in i.input_pins],
   'output':[{'name':p.name,'value':str(p.value),'links':[{'node':q.node.get_name(),'index':q.index_id,'direction':str(q.direction)} for q in p.connected_pins]} for p in i.output_pins]} for i in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]}
def info(g,name): return next(i for i in BP.get_node_infos(BP.find_nodes(g)) if i.node.get_name()==name)
def output_targets(g,name,pin):
 return [q.node.get_name() for p in info(g,name).output_pins if p.name==pin for q in p.connected_pins]
def normalized(snapshot):
 # UE canonicalizes numeric defaults during serialization. Preserve every other field.
 for gg in snapshot['graphs']:
  for nn in gg['nodes']:
   for pp in nn['input']+nn['output']:
    val=pp['value']
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:,[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)*',val):
     pp['value']=','.join(str(Decimal(x).normalize()) if Decimal(x) else '0' for x in val.split(','))
 return snapshot
g=graph('TryBell'); n=nodes(g); f=graph('FinishBell'); e=graph('EmitBell'); eg=graph('EventGraph')
native=[i for i in BP.get_node_infos(BP.find_nodes(g)) if 'BeginBellAction' in i.type_id]
if not native:
 before=BASE/'BP_CatActions-semantics.json'
 assert not before.exists(), 'A partial attempt exists: inspect it, do not rebuild connected graphs'
 row=next(x for x in json.loads((BASE/'manifest.json').read_text()) if x['path'].endswith('BP_CatActions.uasset'))
 assert hashlib.sha256(FILE.read_bytes()).hexdigest()==row['before_sha256']
 assert output_targets(g,'K2Node_IfThenElse_5','else')==['K2Node_VariableSet_0']
 assert output_targets(g,'K2Node_VariableSet_3','then')==['K2Node_CallFunction_8']
 assert output_targets(g,'K2Node_CallFunction_12','then')==['K2Node_CallFunction_13']
 assert output_targets(f,'K2Node_FunctionEntry_0','then')==['K2Node_CallFunction_0']
 assert output_targets(e,'K2Node_FunctionEntry_0','then')==['K2Node_CallDelegate_0']
 before.write_text(json.dumps(dump(),ensure_ascii=False,indent=2),encoding='utf8')
 editor=unreal.BlueprintGraphEditor.get_graph_editor(g)
 begin=editor.add_call_function_node('/Script/Catrun.CatrunBasketInteractionComponent.BeginBellAction'); assert begin
 begin.set_node_pos(unreal.IntPoint(2200,700))
 for pin,val in [('EmitDelay','.566667'),('Duration','2.8')]: assert inp(begin,pin).set_pin_value(val)
 branch_type=info(g,'K2Node_IfThenElse_5').type_id
 guard=BP.create_node(g,branch_type,unreal.IntPoint(2500,700)); assert guard
 cut(n['K2Node_IfThenElse_5'],'else',n['K2Node_VariableSet_0'],'execute')
 cut(n['K2Node_VariableSet_0'],'then',n['K2Node_VariableSet_2'],'execute')
 connect(n['K2Node_IfThenElse_5'],'else',begin,'execute'); connect(begin,'then',guard,'execute')
 connect(begin,'ReturnValue',guard,'Condition'); connect(guard,'then',n['K2Node_VariableSet_2'],'execute')
 # Native acquired/snapshotted movement; retain original clip, play rate, optional sound and cooldown.
 cut(n['K2Node_VariableSet_3'],'then',n['K2Node_CallFunction_8'],'execute')
 cut(n['K2Node_CallFunction_9'],'then',n['K2Node_CallFunction_10'],'execute')
 connect(n['K2Node_VariableSet_3'],'then',n['K2Node_CallFunction_10'],'execute')
 cut(n['K2Node_CallFunction_12'],'then',n['K2Node_CallFunction_13'],'execute')
 # Legacy name-based callbacks become inert; a stale direct dispatch cannot restore/emit anything.
 cut(nodes(f)['K2Node_FunctionEntry_0'],'then',nodes(f)['K2Node_CallFunction_0'],'execute')
 cut(nodes(e)['K2Node_FunctionEntry_0'],'then',nodes(e)['K2Node_CallDelegate_0'],'execute')
 ready=BP.add_event(bp,'BellEmissionReady',unreal.IntPoint(0,1250)); assert ready
 choices=[str(x) for x in unreal.BlueprintGraphEditor.get_graph_editor(eg).list_available_nodes([]) if str(x).endswith('|CallOnBellRung')]
 assert len(choices)==1,choices
 call=BP.create_node(eg,choices[0],unreal.IntPoint(420,1250)); assert call
 connect(ready,'then',call,'execute')
else:
 assert len(native)==1
 assert (BASE/'BP_CatActions-semantics.json').exists()
 assert normalized(dump())==normalized(json.loads((OUT/'BP_CatActions-after.json').read_text(encoding='utf8'))), 'Existing graph differs from saved owned patch; do not rebuild it'
# Validate executable topology without recreating any nodes on repeat runs.
assert output_targets(g,'K2Node_CallFunction_12','then')==[]
assert output_targets(f,'K2Node_FunctionEntry_0','then')==[]
assert output_targets(e,'K2Node_FunctionEntry_0','then')==[]
assert len([i for i in BP.get_node_infos(BP.find_nodes(g)) if 'BeginBellAction' in i.type_id])==1
compile_blueprint(bp,True); assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
(OUT/'BP_CatActions-after.json').write_text(json.dumps(dump(),ensure_ascii=False,indent=2),encoding='utf8')
print('FINAL_FIX_BELL_SAVED',str(bp.get_editor_property('status')),hashlib.sha256(FILE.read_bytes()).hexdigest(),'repeat',bool(native))
