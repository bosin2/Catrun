import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
fac=unreal.BlueprintFactory();fac.set_editor_property('parent_class',unreal.Actor)
bp=new(PRES,unreal.Blueprint,fac)
if not BP.list_variables(bp):
 for name,cls in [('Director',unreal.CatrunStatuePuzzle),('Statue',unreal.Actor),('Gate',unreal.Actor),('EyeMID',unreal.MaterialInstanceDynamic),('BarsMID',unreal.MaterialInstanceDynamic),('Reveal',unreal.CatrunPuzzleRevealComponent),('OwnedCamera',unreal.CameraComponent),('GameplayCamera',unreal.CameraComponent),('EyeMesh',unreal.StaticMeshComponent)]:
  BP.add_object_variable(bp,name,cls.static_class())
  if name in ['Director','Statue','Gate']:BP.set_variable_instance_editable(bp,name,True)
 for name,typ in [('PuzzleId','name'),('EyeParameter','name'),('EyeStrengthParameter','name'),('EyeIndex','int'),('OriginSessionId','int'),('Revision','int'),('EyeOriginalColor','LinearColor'),('EyeOriginalStrength','float'),('SeatedEyeColor','LinearColor'),('SeatedEyeStrength','float'),('CameraOffset','Vector'),('FloorAnchor','Vector'),('OriginalOrthoWidth','float'),('RevealOrthoWidth','float'),('PhaseTime','float'),('DustActive','bool'),('PresentationActive','bool'),('BarHeight','float'),('RumbleStrength','float')]:
  BP.add_variable(bp,name,typ)
  if name in ['PuzzleId','EyeParameter','EyeStrengthParameter','EyeIndex','SeatedEyeColor','SeatedEyeStrength','CameraOffset','RevealOrthoWidth','BarHeight','RumbleStrength']:BP.set_variable_instance_editable(bp,name,True)
 g=graph(bp)
 for fname,enumvar,cls,param in [('HandlePhase','Phase','/Script/Catrun.CatrunPuzzleRevealComponent','Phase'),('HandlePuzzle',None,None,'Event')]:
  fg=BP.add_function_graph(bp,fname);BP.add_function_param(fg,'PuzzleId','name',True)
  if enumvar:
   probe=get(g,enumvar,cls);pt=outp(probe,enumvar).get_pin_type()
  else:
   probe=node(g,'SwitchonECatrunStatueEvent');pt=inp(probe,'Selection').get_pin_type()
  assert ed(fg).add_graph_input_parameter(param,pt,'');ed(g).remove_nodes([probe]);BP.add_function_param(fg,'SessionId' if enumvar else 'Revision','int',True)
 for fname in ['ClearPresentation','InitializePresentation','StartDust','StopDust','UpdateCamera']:BP.add_function_graph(bp,fname)
 BP.add_function_param(graph(bp,'UpdateCamera'),'DeltaSeconds','float',True)
strict(bp)
cdo=unreal.get_default_object(bp.generated_class())
for k,v in {'EyeParameter':'EyesColor','EyeStrengthParameter':'EyesStrength','EyeIndex':0,'SeatedEyeColor':unreal.LinearColor(1,.005,.002,1),'SeatedEyeStrength':5.,'CameraOffset':unreal.Vector(0,-650,850),'RevealOrthoWidth':650.,'BarHeight':.075,'RumbleStrength':.0007}.items():cdo.set_editor_property(k,v)
assert AS.save_loaded_asset(bp,False)
(OUT/'node-choices.json').write_text(json.dumps([str(x) for x in ed(graph(bp)).list_available_nodes([]) if any(y in str(x) for y in ['OnPuzzleEvent','OnPhaseChanged','Switchon','StaticMesh','DynamicMaterial'])],ensure_ascii=False,indent=2),encoding='utf8')
print('TASK4D_SCAFFOLD_SAVED')
