"""Read startup class defaults to attribute an existing no-class spawn warning."""
import json
from pathlib import Path

import unreal


def inspect():
    cls = unreal.load_class(None, "/Game/Blueprints/GameModes/GM_Cat.GM_Cat_C")
    assert cls
    defaults = unreal.get_default_object(cls)
    result = {"class": cls.get_path_name(), "properties": {}}
    for name in ("DefaultPawnClass", "HUDClass", "PlayerControllerClass", "GameStateClass",
                 "PlayerStateClass", "SpectatorClass", "bStartPlayersAsSpectators"):
        value = defaults.get_editor_property(name)
        result["properties"][name] = value.get_path_name() if isinstance(value, unreal.Object) else value
    controller_class = defaults.get_editor_property("PlayerControllerClass")
    if controller_class:
        manager_class = unreal.get_default_object(controller_class).get_editor_property("PlayerCameraManagerClass")
        result["camera_manager_class"] = manager_class.get_path_name() if manager_class else None
    return result


result = inspect()
destination = Path(unreal.Paths.project_saved_dir()) / "Prototype20261104/Task5/spawn-defaults.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
