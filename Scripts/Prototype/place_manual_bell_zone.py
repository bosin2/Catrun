"""API checkpoint placement only; the controller presses physical SpaceBar afterward."""
import unreal

def place_checkpoint():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world and world.get_name() == 'Tutorial'
    cat = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    assert cat and controller and not controller.is_move_input_ignored()
    cat.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
    cat.set_actor_location(unreal.Vector(-275, 465, 26.5), False, True)
    assert (cat.get_actor_location() - unreal.Vector(-275, 465, 26.5)).length() < 1
    unreal.log('CANONICAL_MANUAL_API_CHECKPOINT_INSIDE_NO_BELL')
    print('CHECKPOINT', cat.get_actor_location())

place_checkpoint()
