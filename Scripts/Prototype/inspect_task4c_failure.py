import unreal
print('ROT',unreal.Rotator(0,90,0),unreal.Rotator(pitch=0,yaw=90,roll=0))
print('RETURN_PROP',unreal.get_default_object(unreal.load_class(None,'/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor.BP_LivingArmor_C')).get_editor_property('bReturnToPost'))
