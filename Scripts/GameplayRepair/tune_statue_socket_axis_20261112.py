"""Set the shared Stage2 statue socket-axis tolerance in the existing data asset."""
import unreal


SETTINGS_PATH = "/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings"
AXIS_TOLERANCE = 24.0


def main():
    assets = unreal.EditorAssetLibrary
    settings = assets.load_asset(SETTINGS_PATH)
    if not isinstance(settings, unreal.CatrunStatuePuzzleSettings):
        raise RuntimeError(f"Missing statue puzzle settings at {SETTINGS_PATH}")

    property_name = "SocketAxisTolerance"
    previous = settings.get_editor_property(property_name)
    if previous != AXIS_TOLERANCE:
        dirty_packages = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        if any(package.get_name() == SETTINGS_PATH for package in dirty_packages):
            raise RuntimeError(f"Shared statue puzzle settings has unsaved edits: {SETTINGS_PATH}")
        settings.set_editor_property(property_name, AXIS_TOLERANCE)
        if not assets.save_loaded_asset(settings, False):
            settings.set_editor_property(property_name, previous)
            raise RuntimeError(f"Could not save {SETTINGS_PATH}")

    unreal.log(f"{SETTINGS_PATH} {property_name}: {previous} -> {settings.get_editor_property(property_name)}")


if __name__ == "__main__":
    main()
