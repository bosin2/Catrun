"""Update the existing floorplan panel for the gameplay camera projection."""

from pathlib import Path
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))

from menu_graph import compile_bp, properties, ui, widgets
from rework_minimap_20261112 import AS, FOLDER, MARKER_INSET, OWNER, OWNER_TAG, PANEL_NAME, audit_panel_tree


def main():
    audit = '-catrunminimapprojectionaudit' in u.SystemLibrary.get_command_line().lower()
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    panel = AS.load_asset(f'{FOLDER}/{PANEL_NAME}')
    assert panel and AS.get_metadata_tag(panel, OWNER_TAG) == OWNER
    tree = widgets(panel)
    frame = tree['MinimapFrame']
    layer = tree['MarkerLayer']
    hint = tree.get('MapToggleHint')
    assert tree['MapBackground'].get_parent() == layer.get_parent() == tree['MapSurface']
    assert tree['MapSurface'].get_parent() == frame
    assert not hint or isinstance(hint, u.TextBlock) and hint.get_parent() == tree['MapSurface']

    changed = False
    if not audit:
        if hint:
            ui('RemoveWidget', panel, hint)
            changed = True
        padding = frame.get_editor_property('padding')
        if not padding.left == padding.top == padding.right == padding.bottom == MARKER_INSET:
            properties(frame, padding=u.Margin(MARKER_INSET, MARKER_INSET, MARKER_INSET, MARKER_INSET))
            changed = True
        if layer.get_editor_property('clipping') != u.WidgetClipping.INHERIT:
            properties(layer, clipping=u.WidgetClipping.INHERIT)
            changed = True
    audit_panel_tree(panel)
    if changed:
        compile_bp(panel)
        assert AS.save_loaded_asset(panel, False), panel
    print('CATRUN_MINIMAP_CAMERA_PROJECTION', panel.get_path_name(), 'updated' if changed else 'verified')


if __name__ == '__main__':
    main()
