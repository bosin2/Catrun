import unreal, json
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world() or editor.get_editor_world()
rows = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if not any(s in actor.get_class().get_name() for s in ['Cat_C', 'Armor', 'Candle']): continue
    row = {'actor': actor.get_actor_label(), 'class': actor.get_class().get_name(), 'location': str(actor.get_actor_location()), 'capsules': []}
    for capsule in actor.get_components_by_class(unreal.CapsuleComponent):
        row['capsules'].append({'name': capsule.get_name(), 'radius': capsule.get_scaled_capsule_radius(), 'half_height': capsule.get_scaled_capsule_half_height(), 'location': str(capsule.get_world_location()), 'collision': str(capsule.get_collision_enabled()), 'pawn_response': str(capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))})
    rows.append(row)
print(json.dumps({'world': world.get_path_name(), 'actors': rows}, ensure_ascii=False))
