import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
bp=AS.load_asset(ARM_BP);g=graph(bp)
assert 'HandleCapturePhase' not in [x.get_name() for x in BP.list_graphs(bp)],'Connected armor graphs must be verified/reused through setup_task4c_presentation.py; do not destructively rebuild them.'
existing=set(BP.list_variables(bp))
for name,cls in [('LastRequestedAsset',unreal.AnimationAsset.static_class()),('OwnedActionMontage',unreal.AnimMontage.static_class()),('CapturePlaybackContext',AS.load_asset(CTX).generated_class())]:
 if name not in existing:BP.add_object_variable(bp,name,cls)
if 'LocomotionBlendSeconds' not in existing:BP.add_variable(bp,'LocomotionBlendSeconds','float');BP.set_variable_instance_editable(bp,'LocomotionBlendSeconds',True)
original=json.loads((OUT/'armor-before.json').read_text());oldnames={n['name'] for gg in original['graphs'] if gg['name']=='EventGraph' for n in gg['nodes']}
ed(g).remove_nodes([n for n in BP.find_nodes(g) if n.get_name() not in oldnames])
# Handler is a typed function; native inherited components are not in SCS, so bind once in BeginPlay.
try:phaseg=graph(bp,'HandleCapturePhase')
except Exception:phaseg=None
if not phaseg:
 phaseg=BP.add_function_graph(bp,'HandleCapturePhase')
 probe=get(g,'Phase','/Script/Catrun.CatrunCapturePresentationComponent')
 assert ed(phaseg).add_graph_input_parameter('Phase',outp(probe,'Phase').get_pin_type(),'')
 ed(g).remove_nodes([probe]);BP.add_function_param(phaseg,'SessionId','int',True)
else:ed(phaseg).remove_nodes([n for n in BP.find_nodes(phaseg) if not isinstance(n,unreal.K2Node_FunctionEntry)])
# Override the native presentation request exactly once.
req=BP.add_event(bp,'AnimationRequested');assert req
use=get(g,'bUseBlueprintAnimation');gate=node(g,'Branch');connect(req,'then',gate,'execute');connect(use,'bUseBlueprintAnimation',gate,'Condition')
validrequest=function(g,'/Script/Engine.KismetSystemLibrary.IsValid');connect(req,'Animation',validrequest,'Object');validgate=node(g,'Branch');connect(gate,'then',validgate,'execute');connect(validrequest,'ReturnValue',validgate,'Condition')
cast=node(g,'CastToAnimSequenceBase');connect(validgate,'then',cast,'execute');connect(req,'Animation',cast,'Object')
mesh=get(g,'Mesh');instance=function(g,'/Script/Engine.SkeletalMeshComponent.GetAnimInstance');connect(mesh,'Mesh',instance,'self')
play=function(g,'/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage');connect(cast,'then',play,'execute');connect(instance,'ReturnValue',play,'self');connect(cast,next(str(p.get_pin_name()) for p in cast.list_output_pins() if str(p.get_pin_name()).startswith('As')),play,'Asset');connect(req,'PlayRate',play,'InPlayRate');value(play,'SlotNodeName','DefaultSlot');value(play,'BlendOutTime','0');value(play,'InTimeToStartMontageAt','0')
loop=function(g,'/Script/Engine.KismetMathLibrary.SelectInt');value(loop,'A','100000');value(loop,'B','1');connect(req,'bLoop',loop,'bPickA');connect(loop,'ReturnValue',play,'LoopCount')
# Never blend an authored turn/door offset after native commits its matching actor transform.
last=get(g,'LastRequestedAsset');boundary=None
for assetname in ['TurnLeftAnim','TurnRightAnim','DoorOpenAnim']:
 asset=get(g,assetname)
 for source,pinname in [(req,'Animation'),(last,'LastRequestedAsset')]:
  eq=function(g,'/Script/Engine.KismetMathLibrary.EqualEqual_ObjectObject');connect(source,pinname,eq,'A');connect(asset,assetname,eq,'B')
  if boundary is None:boundary=eq
  else:
   ornode=function(g,'/Script/Engine.KismetMathLibrary.BooleanOR');connect(boundary,'ReturnValue',ornode,'A');connect(eq,'ReturnValue',ornode,'B');boundary=ornode
blend=function(g,'/Script/Engine.KismetMathLibrary.SelectFloat');value(blend,'A','0');seconds=get(g,'LocomotionBlendSeconds');connect(seconds,'LocomotionBlendSeconds',blend,'B');connect(boundary,'ReturnValue',blend,'bPickA');connect(blend,'ReturnValue',play,'BlendInTime')
owned=setv(g,'OwnedActionMontage');connect(play,'then',owned,'execute');connect(play,'ReturnValue',owned,'OwnedActionMontage')
lastset=setv(g,'LastRequestedAsset');connect(owned,'then',lastset,'execute');connect(req,'Animation',lastset,'LastRequestedAsset')
error=function(g,'/Script/Engine.KismetSystemLibrary.PrintString');connect(cast,'CastFailed',error,'execute');value(error,'InString','Armor presentation requires an AnimSequenceBase');value(error,'bPrintToScreen','false');value(error,'bPrintToLog','true')
# Pickup only resolves the single-player pawn after native token and phase validation.
h=phaseg;entry=BP.find_nodes(h)[0];component=get(h,'CapturePresentation');current=get(h,'SessionId','/Script/Catrun.CatrunCapturePresentationComponent');connect(component,'CapturePresentation',current,'self')
eq=function(h,'/Script/Engine.KismetMathLibrary.EqualEqual_IntInt');connect(entry,'SessionId',eq,'A');connect(current,'SessionId',eq,'B');guard=node(h,'Branch');connect(entry,'then',guard,'execute');connect(eq,'ReturnValue',guard,'Condition')
switch=node(h,'SwitchonECatrunCapturePhase');connect(guard,'then',switch,'execute');connect(entry,'Phase',switch,'Selection')
player=function(h,'/Script/Engine.GameplayStatics.GetPlayerCharacter');value(player,'PlayerIndex','0')
valid=function(h,'/Script/Engine.KismetSystemLibrary.IsValid');connect(player,'ReturnValue',valid,'Object');ok=node(h,'Branch');usecapture=get(h,'bUseBlueprintPresentation','/Script/Catrun.CatrunCapturePresentationComponent');connect(component,'CapturePresentation',usecapture,'self');capgate=node(h,'Branch');connect(switch,'Pickup',capgate,'execute');connect(usecapture,'bUseBlueprintPresentation',capgate,'Condition');connect(capgate,'then',ok,'execute');connect(valid,'ReturnValue',ok,'Condition')
ismine=function(h,'/Script/Engine.Pawn.IsPlayerControlled');connect(player,'ReturnValue',ismine,'self');pcguard=node(h,'Branch');connect(ok,'then',pcguard,'execute');connect(ismine,'ReturnValue',pcguard,'Condition')
# Authoring flags do not change native actor movement or participant detection.
spawn=node(h,'SpawnActorfromClass');value(spawn,'Class',CTX+'.BP_CapturePlayback_C');transform=function(h,'/Script/Engine.KismetMathLibrary.MakeTransform');value(transform,'Scale','1,1,1');connect(transform,'ReturnValue',spawn,'SpawnTransform');value(spawn,'CollisionHandlingOverride','AlwaysSpawn');connect(pcguard,'then',spawn,'execute')
selfnode=node(h,'셀프레퍼런스가져오기');connect(selfnode,'self',spawn,'Owner')
saved=setv(h,'CapturePlaybackContext');connect(spawn,'then',saved,'execute');connect(spawn,'ReturnValue',saved,'CapturePlaybackContext')
initialize=function(h,CTX+'.BP_CapturePlayback_C.InitializePlayback');connect(saved,'then',initialize,'execute');connect(spawn,'ReturnValue',initialize,'self');connect(component,'CapturePresentation',initialize,'InComponent');connect(entry,'SessionId',initialize,'InSessionId')
armmesh=get(h,'Mesh');catmesh=function(h,'/Script/Engine.Actor.GetComponentByClass');value(catmesh,'ComponentClass','/Script/Engine.SkeletalMeshComponent');connect(player,'ReturnValue',catmesh,'self');connect(armmesh,'Mesh',initialize,'InArmorMesh');connect(catmesh,'ReturnValue',initialize,'InCatMesh')
rate=get(h,'PickupPlayRate','/Script/Catrun.CatrunCapturePresentationComponent');connect(component,'CapturePresentation',rate,'self');connect(rate,'PickupPlayRate',initialize,'InPlayRate')
# Native restores modes/classes before Inactive. Only cancel the matching context here.
context=get(h,'CapturePlaybackContext');cv=function(h,'/Script/Engine.KismetSystemLibrary.IsValid');connect(context,'CapturePlaybackContext',cv,'Object');cb=node(h,'Branch');connect(switch,'Inactive',cb,'execute');connect(cv,'ReturnValue',cb,'Condition')
origin=get(h,'OriginSessionId',CTX+'.BP_CapturePlayback_C');connect(context,'CapturePlaybackContext',origin,'self');ceq=function(h,'/Script/Engine.KismetMathLibrary.EqualEqual_IntInt');connect(origin,'OriginSessionId',ceq,'A');connect(entry,'SessionId',ceq,'B');cg=node(h,'Branch');connect(cb,'then',cg,'execute');connect(ceq,'ReturnValue',cg,'Condition')
cancel=function(h,CTX+'.BP_CapturePlayback_C.CancelPlayback');connect(cg,'then',cancel,'execute');connect(context,'CapturePlaybackContext',cancel,'self');clear=setv(h,'CapturePlaybackContext');connect(cancel,'then',clear,'execute')
# Compile function signature before constructing its delegate binding.
compile_checked(bp,True);assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
begin=next(n for n in BP.find_nodes(g) if n.get_name()=='K2Node_Event_0')
bind=BP.create_node(g,'캡처|BindEventtoOnPhaseChanged',unreal.IntPoint(0,0),unreal.CatrunCapturePresentationComponent.static_class())
comp=get(g,'CapturePresentation');connect(comp,'CapturePresentation',bind,'self');connect(begin,'then',bind,'execute')
create=node(g,'이벤트생성');connect(create,'OutputDelegate',bind,'Delegate');BP.set_create_event_function(create,'HandleCapturePhase');assert str(unreal.BlueprintEditorLibrary.get_create_delegate_function(create))=='HandleCapturePhase'
for gg in [g,h]:BP.arrange_nodes(BP.find_nodes(gg))
strict(bp)
cdo=unreal.get_default_object(bp.generated_class());cdo.set_editor_property('LocomotionBlendSeconds',.08)
# Still disabled until the complete graph is strictly compiled. Runtime testing will enable both together.
cdo.get_editor_property('Mesh').set_editor_property('anim_class',AS.load_asset(ARM_ABP).generated_class());cdo.get_editor_property('Mesh').set_editor_property('animation_mode',unreal.AnimationMode.ANIMATION_BLUEPRINT)
cdo.set_editor_property('bUseBlueprintAnimation',True);cap=cdo.get_editor_property('CapturePresentation');cap.set_editor_property('CatPickupAnimation',AS.load_asset(CAT_CLIP));cap.set_editor_property('bUseBlueprintPresentation',True)
assert AS.save_loaded_asset(bp,False)
(OUT/'armor-after.json').write_text(json.dumps(dump(bp),indent=2),encoding='utf8')
print('ARMOR_STRICT_SAVED',str(bp.get_editor_property('status')))
