import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunDoor):
  g=a.get_editor_property('GateBox');print('DOOR',a.get_name(),g.get_world_location(),g.get_right_vector(),g.get_scaled_box_extent())
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor):print('ARMOR',a.get_name(),a.get_actor_location(),a.get_action())
