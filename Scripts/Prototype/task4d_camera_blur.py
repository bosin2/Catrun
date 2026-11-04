"""Suppress travel blur only on the fresh native reveal camera, before its bars.
No existing connected graph is rebuilt; one exec edge receives the PP assignment.
"""
import sys,unreal,json,re
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
bp=AS.load_asset(PRES)
if 'ConfigureCameraMotionBlur' in [x.get_name() for x in BP.list_graphs(bp)]:
 # The failed, disconnected authoring probe only; no installed behavior used it.
 probe=graph(bp,'ConfigureCameraMotionBlur');assert len(BP.find_nodes(probe))==2;BP.remove_function_graph(bp,'ConfigureCameraMotionBlur')
if 'RevealPostProcess' not in BP.list_variables(bp):
 native=unreal.get_default_object(unreal.CameraActor).get_component_by_class(unreal.CameraComponent);original=native.get_editor_property('post_process_settings');settings=original.copy();assert original.export_text()==settings.export_text()
 settings.set_editor_property('override_motion_blur_amount',True);settings.set_editor_property('motion_blur_amount',0.)
 def normalized(v):
  if hasattr(v,'export_text'):return v.export_text()
  if hasattr(v,'__iter__') and not isinstance(v,str):return [normalized(x) for x in v]
  return v
 props=re.findall(r'^- ``([^`]+)``',unreal.PostProcessSettings.__doc__,re.M);changed=[name for name in props if normalized(original.get_editor_property(name))!=normalized(settings.get_editor_property(name))];assert sorted(changed)==['motion_blur_amount','override_motion_blur_amount'],changed
 BP.add_struct_variable(bp,'RevealPostProcess',unreal.PostProcessSettings.static_struct());BP.set_variable_instance_editable(bp,'RevealPostProcess',True);compile_checked(bp,True);unreal.get_default_object(bp.generated_class()).set_editor_property('RevealPostProcess',settings)
 g=graph(bp,'HandlePhase');infos=BP.get_node_infos(BP.find_nodes(g));add=next(i.node for i in infos if 'AddOrUpdateBlendable' in i.type_id)
 before=inp(add,'execute').list_connected_pins();assert len(before)==1
 camera=inp(add,'self').list_connected_pins();assert len(camera)==1
 assign=setv(g,'PostProcessSettings','/Script/Engine.CameraComponent');source=get(g,'RevealPostProcess');assert camera[0].try_create_connection(inp(assign,'self'));connect(source,'RevealPostProcess',assign,'PostProcessSettings')
 assert before[0].break_single_pin_link(inp(add,'execute'));assert before[0].try_create_connection(inp(assign,'execute'));connect(assign,'then',add,'execute')
 BP.arrange_nodes(BP.find_nodes(g));strict(bp);(OUT/'camera-blur-change.json').write_text(json.dumps({'copied_native_camera_default':True,'changed_fields':changed,'owned_camera_only':True,'inserted_before':'AddOrUpdateBlendable'},indent=2),encoding='utf8');(OUT/'presentation-after.json').write_text(json.dumps(dump(bp),indent=2),encoding='utf8')
else:
 pp=unreal.get_default_object(bp.generated_class()).get_editor_property('RevealPostProcess');assert pp.get_editor_property('override_motion_blur_amount') and pp.get_editor_property('motion_blur_amount')==0.
print('TASK4D_OWNED_CAMERA_BLUR_VERIFIED')
