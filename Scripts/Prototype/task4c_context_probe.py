import sys,unreal,json
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
bp=AS.load_asset(CTX);g=graph(bp)
# Owned new asset only: remove unfinished probe nodes for deterministic reauthoring.
remove=[i.node for i in BP.get_node_infos(BP.find_nodes(g)) if i.node.get_class().get_name() not in ['K2Node_Event','K2Node_CustomEvent']]
if remove:ed(g).remove_nodes(remove)
nodes={}
for name,path in [('PlayCat','/Script/Engine.SkeletalMeshComponent.PlayAnimation'),('CatRate','/Script/Engine.SkeletalMeshComponent.SetPlayRate'),('GetInstance','/Script/Engine.SkeletalMeshComponent.GetAnimInstance'),('MontageStop','/Script/Engine.AnimInstance.Montage_Stop'),('Grab','/Script/Catrun.CatrunCapturePresentationComponent.NotifyGrab'),('Finished','/Script/Catrun.CatrunCapturePresentationComponent.NotifyFinished')]:nodes[name]=function(g,path)
nodes['Montage']=node(g,'몽타주재생')
(OUT/'node-pins.json').write_text(json.dumps({k: {'name':n.get_name(),'pins':[{'name':str(p.get_pin_name()),'dir':str(p.get_pin_direction()),'value':p.get_pin_value()} for p in n.list_all_pins()]} for k,n in nodes.items()},indent=2),encoding='utf8')
print('PINS_READY')
