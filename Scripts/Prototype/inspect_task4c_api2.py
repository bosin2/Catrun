import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
b=unreal.load_asset('/Game/Characters/BlackCat/Final/Animations/ABP_Cat_Final')
g=BP.get_graph(b,'AnimGraph')
a=list(unreal.BlueprintGraphEditor.get_graph_editor(g).list_available_nodes([]))
p={'nodes':[str(x) for x in a if any(k in str(x) for k in ['플레이','슬롯','Idle','Slot','시퀀스','애니메이션']) and not any(k in str(x) for k in ['Casting','Class|','Utilities|','Get','Set','UMG'])]}
for cls,names in [(unreal.BlueprintGraphEditor,['add_component_bound_event_node','add_custom_event_node','add_get_member_variable_node','add_set_member_variable_node','add_call_function_node']), (unreal.BlueprintEditorLibrary,['create_blueprint_asset_with_parent']), (unreal.AnimMontage,['create_slot_animation_as_dynamic_montage_with_blend_settings']), (unreal.AnimDataModel,['get_number_of_keys','get_number_of_frames','get_frame_rate']), (unreal.AnimNode_Slot,[]),(unreal.AnimNode_SequencePlayer,[])]:
 p[cls.__name__]=cls.__doc__ if not names else {n:getattr(getattr(cls,n,None),'__doc__',None) for n in names}
s=unreal.load_asset('/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Idle');m=s.get_editor_property('data_model_interface');c=s.get_editor_property('controller')
p['model']={n:str(getattr(m,n)()) for n in ['get_number_of_keys','get_number_of_frames','get_frame_rate','get_bone_track_names']}
opt=unreal.AnimPoseEvaluationOptions();opt.evaluation_type=unreal.AnimDataEvalType.SOURCE;opt.should_retarget=False;opt.optional_skeletal_mesh=unreal.load_asset('/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final')
pose=unreal.AnimPoseExtensions.get_anim_pose_at_frame(s,0,opt)
p['bones']={str(n):{'local':str(unreal.AnimPoseExtensions.get_bone_pose(pose,n,unreal.AnimPoseSpaces.LOCAL)),'component':str(unreal.AnimPoseExtensions.get_bone_pose(pose,n,unreal.AnimPoseSpaces.WORLD))} for n in m.get_bone_track_names()}
Path(unreal.Paths.project_saved_dir()+'Prototype20261104/task4c-api2.json').write_text(json.dumps(p,indent=2),encoding='utf8')
print('API2_DONE')
