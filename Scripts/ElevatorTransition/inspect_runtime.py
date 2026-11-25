import unreal as u
e=u.get_editor_subsystem(u.UnrealEditorSubsystem)
print('world',e.get_editor_world().get_path_name())
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a,u.CatrunElevatorTransition):print(a.get_actor_label(),str(a.get_transition_state()),repr(a.get_transition_state()),dir(a.get_transition_state()))
print('dirty',[x.get_name() for x in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
