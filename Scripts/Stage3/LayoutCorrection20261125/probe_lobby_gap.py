import unreal as u
w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
hit=u.SystemLibrary.capsule_trace_single_by_profile(w,u.Vector(625,500,26.2),u.Vector(625,740,26.2),20,26,'Pawn',False,[],u.DrawDebugTrace.NONE,True)
print('LOBBY_GAP_HIT',str(hit.to_dict()) if hit else None)
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label() in ('S3_Bench','S3_Maintenance'):
        p,e=a.get_actor_bounds(True);print(a.get_actor_label(),p,e)
