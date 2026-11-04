import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
fac=unreal.BlueprintFactory();fac.set_editor_property('parent_class',unreal.Actor)
bp=new(CTX,unreal.Blueprint,fac)
if not BP.list_variables(bp):
 for name,cls in [('CaptureComponent',unreal.CatrunCapturePresentationComponent),('ArmorMesh',unreal.SkeletalMeshComponent),('CatMesh',unreal.SkeletalMeshComponent),('OwnedMontage',unreal.AnimMontage),('OwnedAnimInstance',unreal.AnimInstance)]:BP.add_object_variable(bp,name,cls.static_class())
 for name,typ in [('OriginSessionId','int'),('PlaybackRate','float'),('Canceled','bool'),('Initialized','bool'),('GrabNotifyAccepted','bool'),('FinishNotifyAccepted','bool')]:BP.add_variable(bp,name,typ)
 for name,cls in [('PickupMontage',unreal.AnimMontage),('CaughtCatClip',unreal.AnimSequenceBase)]:BP.add_object_variable(bp,name,cls.static_class());BP.set_variable_instance_editable(bp,name,True)
 g=BP.add_function_graph(bp,'InitializePlayback')
 for name,cls in [('InComponent',unreal.CatrunCapturePresentationComponent),('InArmorMesh',unreal.SkeletalMeshComponent),('InCatMesh',unreal.SkeletalMeshComponent)]:BP.add_object_function_param(g,name,cls.static_class(),True)
 BP.add_function_param(g,'InSessionId','int',True);BP.add_function_param(g,'InPlayRate','float',True)
 BP.add_function_graph(bp,'CancelPlayback')
 ed(graph(bp)).add_custom_event_node('StartPlayback')
strict(bp)
g=graph(bp);choices=ed(g).list_available_nodes([])
(OUT/'context-choices.json').write_text(json.dumps([str(x) for x in choices if '몽타주' in str(x) or 'Montage' in str(x) or 'StartPlayback' in str(x)],ensure_ascii=False,indent=2),encoding='utf8')
print('CONTEXT_SCAFFOLD',[(g.get_name(),len(BP.find_nodes(g))) for g in BP.list_graphs(bp)])

