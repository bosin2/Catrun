import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
out={}
for name in ['AnimBlueprintFactory','AnimDataController','AnimPoseExtensions','AnimPoseEvaluationOptions','AnimGraphNode_SequencePlayer','OptionalPinFromProperty','AnimGraphNode_BlendListByBool','AnimGraphNode_Slot','AnimMontage','AnimMontageFactory','PlayMontageCallbackProxy','BlueprintEditorLibrary','BlueprintGraphEditor','BlueprintFactory']:
 c=getattr(unreal,name,None)
 out[name]={'doc':getattr(c,'__doc__',None),'members':dir(c) if c else []}
for c,methods in [('AnimDataController',['set_model','open_bracket','set_bone_track_keys']),('AnimPoseExtensions',['get_anim_pose_at_frame','get_bone_pose']),('AnimInstance',['play_slot_animation_as_dynamic_montage']),('AnimMontage',['create_slot_animation_as_dynamic_montage'])]:
 for m in methods:out[c+'.'+m]=getattr(getattr(getattr(unreal,c),m,None),'__doc__',None)
s=unreal.load_asset('/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Idle')
for name in ['data_model_interface','controller']:
 try:out['idle.'+name]=str(s.get_editor_property(name))
 except Exception as e:out['idle.'+name]=str(e)
for path in ['/Game/Characters/BlackCat/Final/Animations/ABP_Cat_Final','/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor']:
 b=unreal.load_asset(path)
 for g in BP.list_graphs(b):
  choices=unreal.BlueprintGraphEditor.get_graph_editor(g).list_available_nodes([])
  out[path+'/'+g.get_name()]=[str(x) for x in choices if any(k.lower() in str(x).lower() for k in ['Sequence','Slot','Montage','Notify','SpawnActor','Construct','OnPhase','AnimationRequested','ComponentBound','Session','Capture','Cast','Loop','Animation','Timer'])]
Path(unreal.Paths.project_saved_dir()+'Prototype20261104/task4c-introspection.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print('TASK4C_INSPECT',unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name())
