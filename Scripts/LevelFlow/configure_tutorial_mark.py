"""Enable the user-confirmed candle -> armor rule without changing doors or cinematics."""
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert levels.load_level('/Game/Maps/SoundTest_Tutorial')
managers = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.SoundGridManager)]
assert len(managers) == 1
managers[0].set_editor_property('bMarkAttractsArmors', True)
assert all(not a.get_editor_property('bStartOpen') for a in actors.get_all_level_actors() if isinstance(a, unreal.CatrunDoor))
assert levels.save_current_level()
unreal.log('TUTORIAL_MARK_ENABLED_DOORS_UNCHANGED')
