import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
bp=AS.load_asset(CTX)
# Rebuild only this task's new context asset. The original actors' graphs are never cleared.
for g in BP.list_graphs(bp):
 if g.get_name()=='UserConstructionScript':continue
 keep=[i.node for i in BP.get_node_infos(BP.find_nodes(g)) if i.node.get_class().get_name() in ['K2Node_FunctionEntry','K2Node_Event','K2Node_CustomEvent']]
 ed(g).remove_nodes([n for n in BP.find_nodes(g) if n not in keep])

def chain_guard(g,start,execpin):
 # Cancellation precedes access; session equality uses this context's immutable origin token.
 cancel=get(g,'Canceled');br=node(g,'Branch');connect(start,execpin,br,'execute');connect(cancel,'Canceled',br,'Condition')
 comp=get(g,'CaptureComponent');valid=function(g,'/Script/Engine.KismetSystemLibrary.IsValid');connect(comp,'CaptureComponent',valid,'Object');bv=node(g,'Branch');connect(br,'else',bv,'execute');connect(valid,'ReturnValue',bv,'Condition')
 current=get(g,'SessionId','/Script/Catrun.CatrunCapturePresentationComponent');connect(comp,'CaptureComponent',current,'self')
 original=get(g,'OriginSessionId');eq=function(g,'/Script/Engine.KismetMathLibrary.EqualEqual_IntInt');connect(current,'SessionId',eq,'A');connect(original,'OriginSessionId',eq,'B');be=node(g,'Branch');connect(bv,'then',be,'execute');connect(eq,'ReturnValue',be,'Condition')
 return be,comp,original

g=graph(bp,'InitializePlayback');entry=BP.find_nodes(g)[0];init=get(g,'Initialized');branch=node(g,'Branch');connect(entry,'then',branch,'execute');connect(init,'Initialized',branch,'Condition')
first=setv(g,'Initialized');value(first,'Initialized','true');connect(branch,'else',first,'execute');last=first
for var,param in [('CaptureComponent','InComponent'),('ArmorMesh','InArmorMesh'),('CatMesh','InCatMesh'),('OriginSessionId','InSessionId'),('PlaybackRate','InPlayRate')]:
 n=setv(g,var);connect(last,'then',n,'execute');connect(entry,param,n,var);last=n
startcall=node(g,'StartPlayback');connect(last,'then',startcall,'execute')

g=graph(bp);start=next(i.node for i in BP.get_node_infos(BP.find_nodes(g)) if isinstance(i.node,unreal.K2Node_CustomEvent))
arm=get(g,'ArmorMesh');cat=get(g,'CatMesh');rate=get(g,'PlaybackRate');mt=get(g,'PickupMontage');clip=get(g,'CaughtCatClip')
instance=function(g,'/Script/Engine.SkeletalMeshComponent.GetAnimInstance');connect(arm,'ArmorMesh',instance,'self')
saved=setv(g,'OwnedAnimInstance');connect(start,'then',saved,'execute');connect(instance,'ReturnValue',saved,'OwnedAnimInstance')
savedmt=setv(g,'OwnedMontage');connect(saved,'then',savedmt,'execute');connect(mt,'PickupMontage',savedmt,'OwnedMontage')
catplay=function(g,'/Script/Engine.SkeletalMeshComponent.PlayAnimation');connect(savedmt,'then',catplay,'execute');connect(cat,'CatMesh',catplay,'self');connect(clip,'CaughtCatClip',catplay,'NewAnimToPlay');value(catplay,'bLooping','false')
catrate=function(g,'/Script/Engine.SkeletalMeshComponent.SetPlayRate');connect(catplay,'then',catrate,'execute');connect(cat,'CatMesh',catrate,'self');connect(rate,'PlaybackRate',catrate,'Rate')
play=node(g,'몽타주재생');connect(catrate,'then',play,'execute');connect(arm,'ArmorMesh',play,'InSkeletalMeshComponent');connect(mt,'PickupMontage',play,'MontageToPlay');connect(rate,'PlaybackRate',play,'PlayRate')
# Proxy filters montage instance; this fresh context supplies immutable session provenance.
guard,component,origin=chain_guard(g,play,'OnNotifyBegin')
nameeq=function(g,'/Script/Engine.KismetMathLibrary.EqualEqual_NameName');connect(play,'NotifyName',nameeq,'A');value(nameeq,'B','CaptureGrab');isgrab=node(g,'Branch');connect(guard,'then',isgrab,'execute');connect(nameeq,'ReturnValue',isgrab,'Condition')
grab=function(g,'/Script/Catrun.CatrunCapturePresentationComponent.NotifyGrab');connect(isgrab,'then',grab,'execute');connect(component,'CaptureComponent',grab,'self');connect(origin,'OriginSessionId',grab,'InSessionId');accepted=setv(g,'GrabNotifyAccepted');connect(grab,'then',accepted,'execute');connect(grab,'ReturnValue',accepted,'GrabNotifyAccepted')
endname=function(g,'/Script/Engine.KismetMathLibrary.EqualEqual_NameName');connect(play,'NotifyName',endname,'A');value(endname,'B','CaptureFinished');isend=node(g,'Branch');connect(isgrab,'else',isend,'execute');connect(endname,'ReturnValue',isend,'Condition')
finish=function(g,'/Script/Catrun.CatrunCapturePresentationComponent.NotifyFinished');connect(isend,'then',finish,'execute');connect(component,'CaptureComponent',finish,'self');connect(origin,'OriginSessionId',finish,'InSessionId');accepted=setv(g,'FinishNotifyAccepted');connect(finish,'then',accepted,'execute');connect(finish,'ReturnValue',accepted,'FinishNotifyAccepted')
# A genuine playback failure aborts only the originating current capture.
guard,component,origin=chain_guard(g,play,'OnInterrupted');abort=function(g,'/Script/Catrun.CatrunCapturePresentationComponent.AbortCapture');connect(guard,'then',abort,'execute');connect(component,'CaptureComponent',abort,'self')

g=graph(bp,'CancelPlayback');entry=BP.find_nodes(g)[0];canceled=setv(g,'Canceled');value(canceled,'Canceled','true');connect(entry,'then',canceled,'execute')
instance=get(g,'OwnedAnimInstance');valid=function(g,'/Script/Engine.KismetSystemLibrary.IsValid');connect(instance,'OwnedAnimInstance',valid,'Object');branch=node(g,'Branch');connect(canceled,'then',branch,'execute');connect(valid,'ReturnValue',branch,'Condition')
mt=get(g,'OwnedMontage');stop=function(g,'/Script/Engine.AnimInstance.Montage_Stop');connect(branch,'then',stop,'execute');connect(instance,'OwnedAnimInstance',stop,'self');connect(mt,'OwnedMontage',stop,'Montage');value(stop,'InBlendOutTime','0')
destroy=function(g,'/Script/Engine.Actor.K2_DestroyActor');connect(stop,'then',destroy,'execute');connect(branch,'else',destroy,'execute')
# A per-playback guard cleans up if an owner disappears before its Inactive BP handler.
# It observes native lifetime only; it never advances capture or moves either participant.
g=graph(bp);tick=BP.add_event(bp,'ReceiveTick');ready=get(g,'Initialized');gate=node(g,'Branch');connect(tick,'then',gate,'execute');connect(ready,'Initialized',gate,'Condition')
comp=get(g,'CaptureComponent');valid=function(g,'/Script/Engine.KismetSystemLibrary.IsValid');connect(comp,'CaptureComponent',valid,'Object');vb=node(g,'Branch');connect(gate,'then',vb,'execute');connect(valid,'ReturnValue',vb,'Condition')
current=get(g,'SessionId','/Script/Catrun.CatrunCapturePresentationComponent');connect(comp,'CaptureComponent',current,'self');origin=get(g,'OriginSessionId');same=function(g,'/Script/Engine.KismetMathLibrary.EqualEqual_IntInt');connect(current,'SessionId',same,'A');connect(origin,'OriginSessionId',same,'B');sb=node(g,'Branch');connect(vb,'then',sb,'execute');connect(same,'ReturnValue',sb,'Condition')
active=function(g,'/Script/Catrun.CatrunCapturePresentationComponent.IsCapturing');connect(comp,'CaptureComponent',active,'self');ab=node(g,'Branch');connect(sb,'then',ab,'execute');connect(active,'ReturnValue',ab,'Condition')
cleanup=function(g,CTX+'.BP_CapturePlayback_C.CancelPlayback');connect(vb,'else',cleanup,'execute');connect(sb,'else',cleanup,'execute');connect(ab,'else',cleanup,'execute')
for g in BP.list_graphs(bp):
 if g.get_name()!='UserConstructionScript':BP.arrange_nodes(BP.find_nodes(g))
strict(bp)
cdo=unreal.get_default_object(bp.generated_class());cdo.set_editor_property('PickupMontage',AS.load_asset(PICKUP_MT));cdo.set_editor_property('CaughtCatClip',AS.load_asset(CAT_CLIP));cdo.set_editor_property('PlaybackRate',1.0);cdo.set_editor_property('initial_life_span',0.0)
ticksettings=cdo.get_editor_property('primary_actor_tick');ticksettings.set_editor_property('tick_interval',.1);cdo.set_editor_property('primary_actor_tick',ticksettings)
assert AS.save_loaded_asset(bp,False)
(OUT/'context-after.json').write_text(json.dumps(dump(bp),indent=2),encoding='utf8')
print('CONTEXT_STRICT_SAVED',str(bp.get_editor_property('status')))
