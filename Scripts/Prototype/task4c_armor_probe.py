import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
bp=AS.load_asset(ARM_BP);g=graph(bp)
existing=set(BP.list_variables(bp))
print('VARS',existing)
for name,cls in [('LastRequestedAsset',unreal.AnimationAsset),('OwnedActionMontage',unreal.AnimMontage),('CapturePlaybackContext',AS.load_asset(CTX).generated_class())]:
 if name not in existing:BP.add_object_variable(bp,name,cls.static_class() if isinstance(cls,type) else cls)
if 'LocomotionBlendSeconds' not in existing:BP.add_variable(bp,'LocomotionBlendSeconds','float');BP.set_variable_instance_editable(bp,'LocomotionBlendSeconds',True)
req=BP.add_event(bp,'AnimationRequested');assert req
phase=ed(g).add_custom_event_node('CapturePhaseChanged');assert phase
bind=BP.create_node(g,'캡처|BindEventtoOnPhaseChanged',unreal.IntPoint(0,0),unreal.CatrunCapturePresentationComponent.static_class());connect(phase,'OutputDelegate',bind,'Delegate')
spawn=node(g,'SpawnActorfromClass');value(spawn,'Class',CTX+'.BP_CapturePlayback_C')
play=function(g,'/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage')
cast=node(g,'CastToAnimSequenceBase')
(OUT/'armor-probe-pins.json').write_text(json.dumps({k:{'name':n.get_name(),'pins':[{'name':str(p.get_pin_name()),'dir':str(p.get_pin_direction()),'value':p.get_pin_value()} for p in n.list_all_pins()]} for k,n in [('req',req),('phase',phase),('spawn',spawn),('play',play),('cast',cast)]},indent=2),encoding='utf8')
print('ARMOR_PROBE_DONE')


