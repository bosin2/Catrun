"""One-time graph authoring. Finished graphs are verified, never rebuilt on rerun."""
import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
bp=AS.load_asset(PRES)
if 'ApiProbe' in [x.get_name() for x in BP.list_graphs(bp)]:BP.remove_function_graph(bp,'ApiProbe')
assert len(BP.find_nodes(graph(bp,'InitializePresentation')))==1,'Existing connected graphs: use verification, not rebuild'
CLS=PRES+'.BP_StatuePresentation_C';E='/Script/Engine.';C='/Script/Catrun.'
def f(g,n):return fn(g,E+n)
def read(g,n):return get(g,n)
def assign(g,n,last,source=None,sp=None,literal=None,ep='then'):
 x=setv(g,n);connect(last,ep,x,'execute')
 if source:connect(source,sp,x,n)
 if literal is not None:value(x,n,literal)
 return x
def call(g,n,last,ep='then'):
 x=fn(g,CLS+'.'+n);connect(last,ep,x,'execute');return x
def valid(g,src,p,last,ep='then'):
 v=f(g,'KismetSystemLibrary.IsValid');connect(src,p,v,'Object');b=node(g,'Branch');connect(last,ep,b,'execute');connect(v,'ReturnValue',b,'Condition');return b
def branch(g,src,p,last,ep='then'):
 b=node(g,'Branch');connect(last,ep,b,'execute');connect(src,p,b,'Condition');return b
def scalar(g,mid,mp,param,last,source=None,sp=None,literal=None):
 x=f(g,'MaterialInstanceDynamic.SetScalarParameterValue');connect(mid,mp,x,'self');connect(last,'then',x,'execute');value(x,'ParameterName',param)
 if source:connect(source,sp,x,'Value')
 if literal is not None:value(x,'Value',literal)
 return x
def property(g,name,cls,src,p):
 x=get(g,name,cls);connect(src,p,x,'self');return x
def equal(g,a,ap,b,bp,typ='IntInt'):
 x=f(g,'KismetMathLibrary.EqualEqual_'+typ);connect(a,ap,x,'A');connect(b,bp,x,'B');return x
def ownfilter(g,e):
 mine=read(g,'PuzzleId');eq=equal(g,e,'PuzzleId',mine,'PuzzleId','NameName');return branch(g,eq,'ReturnValue',e)
def eyes(g,last,restore=False):
 mid=read(g,'EyeMID');ok=valid(g,mid,'EyeMID',last);p=read(g,'EyeParameter');color=read(g,'EyeOriginalColor' if restore else 'SeatedEyeColor');x=f(g,'MaterialInstanceDynamic.SetVectorParameterValue');connect(ok,'then',x,'execute');connect(mid,'EyeMID',x,'self');connect(p,'EyeParameter',x,'ParameterName');connect(color,'EyeOriginalColor' if restore else 'SeatedEyeColor',x,'Value')
 strength=read(g,'EyeOriginalStrength' if restore else 'SeatedEyeStrength');p=read(g,'EyeStrengthParameter');y=f(g,'MaterialInstanceDynamic.SetScalarParameterValue');connect(x,'then',y,'execute');connect(mid,'EyeMID',y,'self');connect(p,'EyeStrengthParameter',y,'ParameterName');connect(strength,'EyeOriginalStrength' if restore else 'SeatedEyeStrength',y,'Value');return y

# Cache exactly the values this presentation changes. No original MIC is edited.
g=graph(bp,'InitializePresentation');e=BP.find_nodes(g)[0];d=read(g,'Director');last=valid(g,d,'Director',e);statue=read(g,'Statue');last=valid(g,statue,'Statue',last);gate=read(g,'Gate');last=valid(g,gate,'Gate',last)
r=property(g,'Reveal',C+'CatrunStatuePuzzle',d,'Director');last=assign(g,'Reveal',last,r,'Reveal')
mesh=f(g,'Actor.GetComponentByClass');value(mesh,'ComponentClass','/Script/Engine.StaticMeshComponent');connect(statue,'Statue',mesh,'self');last=assign(g,'EyeMesh',last,mesh,'ReturnValue');last=valid(g,mesh,'ReturnValue',last)
mid=f(g,'PrimitiveComponent.CreateDynamicMaterialInstance');connect(last,'then',mid,'execute');connect(mesh,'ReturnValue',mid,'self');ix=read(g,'EyeIndex');connect(ix,'EyeIndex',mid,'ElementIndex');last=assign(g,'EyeMID',mid,mid,'ReturnValue')
for param,kind,dest in [('EyeParameter','Vector','EyeOriginalColor'),('EyeStrengthParameter','Scalar','EyeOriginalStrength')]:
 p=read(g,param);x=f(g,'MaterialInstanceDynamic.K2_Get'+kind+'ParameterValue');connect(last,'then',x,'execute');connect(mid,'ReturnValue',x,'self');connect(p,param,x,'ParameterName');last=assign(g,dest,x,x,'ReturnValue')
bars=f(g,'KismetMaterialLibrary.CreateDynamicMaterialInstance');value(bars,'Parent',BARS+'.M_StatueRevealBars');connect(last,'then',bars,'execute');last=assign(g,'BarsMID',bars,bars,'ReturnValue')
bar=read(g,'BarHeight');last=scalar(g,bars,'ReturnValue','BarHeight',last,bar,'BarHeight')
# The placed actor is the immutable original gate-floor anchor, never attached to the moving gate.
pos=f(g,'Actor.K2_GetActorLocation');last=assign(g,'FloorAnchor',last,pos,'ReturnValue')
last=call(g,'StopDust',last)

# Fixed component pool: eight soft cards, particles rise/fade in local material, no spawned actors.
for name,shown in [('StartDust',True),('StopDust',False)]:
 g=graph(bp,name);e=BP.find_nodes(g)[0];last=assign(g,'DustActive',e,literal=str(shown).lower())
 for i in range(8):
  comp=read(g,'Dust%02d'%i)
  if shown:
   t=f(g,'GameplayStatics.GetTimeSeconds');x=f(g,'MeshComponent.SetScalarParameterValueOnMaterials');connect(last,'then',x,'execute');connect(comp,'Dust%02d'%i,x,'self');value(x,'ParameterName','StartTime');connect(t,'ReturnValue',x,'ParameterValue');last=x
  hide=f(g,'SceneComponent.SetHiddenInGame');connect(last,'then',hide,'execute');connect(comp,'Dust%02d'%i,hide,'self');value(hide,'NewHidden',str(not shown).lower());value(hide,'bPropagateToChildren','false');last=hide
 mid=read(g,'BarsMID');last=valid(g,mid,'BarsMID',last);strength=read(g,'RumbleStrength')
 scalar(g,mid,'BarsMID','Rumble',last,strength if shown else None,'RumbleStrength' if shown else None,None if shown else '0')

g=graph(bp,'ClearPresentation');e=BP.find_nodes(g)[0];last=assign(g,'PresentationActive',e,literal='false');last=assign(g,'PhaseTime',last,literal='0');last=call(g,'StopDust',last)
cam=read(g,'OwnedCamera');good=valid(g,cam,'OwnedCamera',last);mid=read(g,'BarsMID');remove=f(g,'CameraComponent.RemoveBlendable');connect(good,'then',remove,'execute');connect(cam,'OwnedCamera',remove,'self');connect(mid,'BarsMID',remove,'InBlendableObject');clear=assign(g,'OwnedCamera',remove);connect(good,'else',clear,'execute')

g=graph(bp,'HandlePuzzle');e=BP.find_nodes(g)[0];last=ownfilter(g,e)
rev=read(g,'Revision');ge=f(g,'KismetMathLibrary.GreaterEqual_IntInt');connect(e,'Revision',ge,'A');connect(rev,'Revision',ge,'B');last=branch(g,ge,'ReturnValue',last);last=assign(g,'Revision',last,e,'Revision');sw=node(g,'SwitchonECatrunStatueEvent');connect(last,'then',sw,'execute');connect(e,'Event',sw,'Selection')
temp=setv(g,'PhaseTime');value(temp,'PhaseTime','0');connect(sw,'Seated',temp,'execute');last=eyes(g,temp)
r=read(g,'Reveal');offset=read(g,'CameraOffset');so=setv(g,'GateCameraOffset',C+'CatrunPuzzleRevealComponent');connect(last,'then',so,'execute');connect(r,'Reveal',so,'self');connect(offset,'CameraOffset',so,'GateCameraOffset');last=so
pc=f(g,'GameplayStatics.GetPlayerController');view=f(g,'Controller.GetViewTarget');connect(pc,'ReturnValue',view,'self');cc=f(g,'Actor.GetComponentByClass');value(cc,'ComponentClass',E+'CameraComponent');connect(view,'ReturnValue',cc,'self');last=assign(g,'GameplayCamera',last,cc,'ReturnValue');last=valid(g,cc,'ReturnValue',last);width=property(g,'OrthoWidth',E+'CameraComponent',cc,'ReturnValue');assign(g,'OriginalOrthoWidth',last,width,'OrthoWidth')
res=fn(g,CLS+'.ClearPresentation');connect(sw,'Reset',res,'execute');eyes(g,res,True)
active=read(g,'PresentationActive');yes=branch(g,active,'PresentationActive',sw,'GateOpening');sid=property(g,'SessionId',C+'CatrunPuzzleRevealComponent',r,'Reveal');origin=read(g,'OriginSessionId');eq=equal(g,sid,'SessionId',origin,'OriginSessionId');yes=branch(g,eq,'ReturnValue',yes);call(g,'StartDust',yes)
call(g,'StopDust',sw,'Completed')

g=graph(bp,'HandlePhase');e=BP.find_nodes(g)[0];last=ownfilter(g,e);r=read(g,'Reveal');sid=property(g,'SessionId',C+'CatrunPuzzleRevealComponent',r,'Reveal');eq=equal(g,e,'SessionId',sid,'SessionId');last=branch(g,eq,'ReturnValue',last);sw=node(g,'SwitchonECatrunPuzzleRevealPhase');connect(last,'then',sw,'execute');connect(e,'Phase',sw,'Selection')
last=assign(g,'OriginSessionId',sw,e,'SessionId',ep='ToGate');last=assign(g,'PresentationActive',last,literal='true');last=assign(g,'PhaseTime',last,literal='0')
cam=fn(g,C+'CatrunPuzzleRevealComponent.GetRevealCamera');connect(r,'Reveal',cam,'self');last=valid(g,cam,'ReturnValue',last);cc=f(g,'Actor.GetComponentByClass');value(cc,'ComponentClass',E+'CameraComponent');connect(cam,'ReturnValue',cc,'self');last=assign(g,'OwnedCamera',last,cc,'ReturnValue');original=read(g,'GameplayCamera');last=valid(g,original,'GameplayCamera',last)
for prop,method,pin in [('ProjectionMode','SetProjectionMode','InProjectionMode'),('bConstrainAspectRatio','SetConstraintAspectRatio','bInConstrainAspectRatio'),('AspectRatio','SetAspectRatio','InAspectRatio'),('bAutoCalculateOrthoPlanes','SetAutoCalculateOrthoPlanes','bAutoCalculate'),('OrthoNearClipPlane','SetOrthoNearClipPlane','InOrthoNearClipPlane'),('OrthoFarClipPlane','SetOrthoFarClipPlane','InOrthoFarClipPlane')]:
 source=property(g,prop,E+'CameraComponent',original,'GameplayCamera');x=f(g,'CameraComponent.'+method);connect(last,'then',x,'execute');connect(cc,'ReturnValue',x,'self');connect(source,prop,x,pin);last=x
width=read(g,'OriginalOrthoWidth');x=f(g,'CameraComponent.SetOrthoWidth');connect(last,'then',x,'execute');connect(cc,'ReturnValue',x,'self');connect(width,'OriginalOrthoWidth',x,'InOrthoWidth');last=x
mid=read(g,'BarsMID');add=f(g,'CameraComponent.AddOrUpdateBlendable');connect(last,'then',add,'execute');connect(cc,'ReturnValue',add,'self');connect(mid,'BarsMID',add,'InBlendableObject');value(add,'InWeight','1');weight=f(g,'CameraComponent.SetPostProcessBlendWeight');connect(add,'then',weight,'execute');connect(cc,'ReturnValue',weight,'self');value(weight,'InPostProcessBlendWeight','1')
for phase in ['Returning','Inactive']:
 origin=read(g,'OriginSessionId');eq=equal(g,e,'SessionId',origin,'OriginSessionId');good=branch(g,eq,'ReturnValue',sw,phase)
 if phase=='Returning':last=assign(g,'PhaseTime',good,literal='0');call(g,'StopDust',last)
 else:call(g,'ClearPresentation',good)

# Tick owns only camera magnification, all native position/rotation and suspension stay native.
g=graph(bp,'UpdateCamera');e=BP.find_nodes(g)[0];active=read(g,'PresentationActive');last=branch(g,active,'PresentationActive',e);r=read(g,'Reveal');last=valid(g,r,'Reveal',last);sid=property(g,'SessionId',C+'CatrunPuzzleRevealComponent',r,'Reveal');origin=read(g,'OriginSessionId');eq=equal(g,sid,'SessionId',origin,'OriginSessionId');good=branch(g,eq,'ReturnValue',last);call(g,'ClearPresentation',good,'else');cam=read(g,'OwnedCamera');last=valid(g,cam,'OwnedCamera',good)
tm=read(g,'PhaseTime');plus=f(g,'KismetMathLibrary.Add_FloatFloat');connect(tm,'PhaseTime',plus,'A');connect(e,'DeltaSeconds',plus,'B');last=assign(g,'PhaseTime',last,plus,'ReturnValue')
phase=property(g,'Phase',C+'CatrunPuzzleRevealComponent',r,'Reveal');sw=node(g,'SwitchonECatrunPuzzleRevealPhase');connect(last,'then',sw,'execute');connect(phase,'Phase',sw,'Selection')
for which,duration,start,end in [('ToGate','CameraTravelTime','OriginalOrthoWidth','RevealOrthoWidth'),('Returning','CameraReturnTime','RevealOrthoWidth','OriginalOrthoWidth')]:
 sec=property(g,duration,C+'CatrunPuzzleRevealComponent',r,'Reveal');div=f(g,'KismetMathLibrary.Divide_FloatFloat');connect(last,'Output_Get',div,'A');connect(sec,duration,div,'B');clamp=f(g,'KismetMathLibrary.FClamp');connect(div,'ReturnValue',clamp,'Value');value(clamp,'Min','0');value(clamp,'Max','1');lerp=f(g,'KismetMathLibrary.Lerp');a=read(g,start);b=read(g,end);connect(a,start,lerp,'A');connect(b,end,lerp,'B');connect(clamp,'ReturnValue',lerp,'Alpha');x=f(g,'CameraComponent.SetOrthoWidth');connect(sw,which,x,'execute');connect(cam,'OwnedCamera',x,'self');connect(lerp,'ReturnValue',x,'InOrthoWidth')

compile_checked(bp,True);assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
g=graph(bp);begin=BP.add_event(bp,'ReceiveBeginPlay');last=call(g,'InitializePresentation',begin);d=read(g,'Director');last=valid(g,d,'Director',last);r=read(g,'Reveal');last=valid(g,r,'Reveal',last)
for typeid,cls,src,p,handler in [('Puzzle|BindEventtoOnPuzzleEvent',unreal.CatrunStatuePuzzle,d,'Director','HandlePuzzle'),('Puzzle|Reveal|BindEventtoOnPhaseChanged',unreal.CatrunPuzzleRevealComponent,r,'Reveal','HandlePhase')]:
 bind=BP.create_node(g,typeid,unreal.IntPoint(0,0),cls.static_class());connect(last,'then',bind,'execute');connect(src,p,bind,'self');create=node(g,'이벤트생성');connect(create,'OutputDelegate',bind,'Delegate');BP.set_create_event_function(create,handler);assert str(unreal.BlueprintEditorLibrary.get_create_delegate_function(create))==handler;last=bind
tick=BP.add_event(bp,'ReceiveTick');update=call(g,'UpdateCamera',tick);connect(tick,'DeltaSeconds',update,'DeltaSeconds');end=BP.add_event(bp,'ReceiveEndPlay');call(g,'ClearPresentation',end)
for g in BP.list_graphs(bp):BP.arrange_nodes(BP.find_nodes(g))
strict(bp);(OUT/'presentation-after.json').write_text(json.dumps(dump(bp),indent=2),encoding='utf8');print('TASK4D_GRAPHS_STRICT_SAVED')
