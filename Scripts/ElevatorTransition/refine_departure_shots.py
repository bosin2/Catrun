"""Place the departure low camera above the opaque warehouse floor.

Run explicitly in the isolated task editor with the saved Stage2 map loaded.
Only E23_Shot_Below plus the isolation allowlist tags on E23_Lift_/E23_Guide_
actors change. No asset, rig, animation, or other map is edited. Native playback
supplies rotation-only face tracking and the extended peek beat.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import unreal as u


TAG = 'CatrunElevatorTransition20261125'
MAP = '/Game/Maps/Stage2.Stage2'
LENS_OFFSET = (14.0, 280.0, 14.0)
HORIZONTAL_FOV = 36.0
VISIBLE_TAG = 'CatrunElevatorIsolationVisible'


def vector(value):
    return list(value.to_tuple())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(u.Paths.project_dir()).resolve()
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert not editor.get_game_world(), 'Stop task-editor PIE before authoring'
    world = editor.get_editor_world()
    assert world and world.get_path_name() == MAP, 'Load saved Stage2 explicitly'
    assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Unsaved map edits'
    lookup = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
    director = lookup['E23_Director']
    camera = lookup['E23_Shot_Below']
    assert TAG in map(str, director.tags) and TAG in map(str, camera.tags)
    assert director.get_editor_property('peek_camera') == camera
    assert not director.get_editor_property('arrival_side')
    assert isinstance(camera, u.CameraActor)
    assert not camera.get_attach_parent_actor(), 'Low camera must stay on the floor'
    pivot = director.get_editor_property('cabin_pivot').get_actor_location()
    assert abs(pivot.x - 715.0) < 0.1 and abs(pivot.y + 1590.0) < 0.1
    map_file = root / 'Content/Maps/Stage2.umap'
    before_hash = digest(map_file)
    backup = root / ('Saved/ElevatorTransition/Backups/Stage2_BeforeDepartureShots_'
                     + time.strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()) + '.umap')
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(map_file, backup)
    assert digest(backup) == before_hash
    position = pivot + u.Vector(*LENS_OFFSET)
    # Neutral preview aim at the eyes near C06's full downward-look plateau.
    # Runtime tracks the same face as the cabin rises, keeping this lens fixed.
    target = pivot + u.Vector(0.0, 96.66, 200.0)
    before = {
        'position': vector(camera.get_actor_location()),
        'rotation': vector(camera.get_actor_rotation()),
        'horizontal_fov': camera.camera_component.field_of_view,
    }
    camera.set_actor_location(position, False, True)
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(position, target), True)
    camera.camera_component.set_field_of_view(HORIZONTAL_FOV)
    camera.camera_component.set_editor_property('constrain_aspect_ratio', False)
    allowlisted = []
    for label, actor in lookup.items():
        if not label.startswith(('E23_Lift_', 'E23_Guide_')):
            continue
        assert TAG in map(str, actor.tags), ('Refusing unowned actor', label)
        if VISIBLE_TAG not in map(str, actor.tags):
            actor.tags = list(actor.tags) + [VISIBLE_TAG]
        allowlisted.append(label)
    assert allowlisted, 'No E23 lift actors found'
    # Do not overwrite a package another editor saved after this script started.
    assert digest(map_file) == before_hash, 'Stage2 file changed concurrently; do not save'
    assert level.save_current_level()
    report = {
        'success': True,
        'map': MAP,
        'changed_actor': camera.get_actor_label(),
        'isolation_allowlisted_actors': sorted(allowlisted),
        'backup': str(backup),
        'stage2_sha256_before': before_hash,
        'stage2_sha256_after': digest(map_file),
        'before': before,
        'after': {
            'position': vector(camera.get_actor_location()),
            'preview_target': vector(target),
            'horizontal_fov': camera.camera_component.field_of_view,
        },
        'reason': 'Old Z=-32 lens looked upward through the warehouse floor at Z=-5..0.',
        'native_contract': {
            'lens_position_fixed': True,
            'target': 'Midpoint of lid_upper_l_00 and lid_upper_r_00 world positions',
            'fallback_target': 'head socket plus cabin-forward 8 cm and world-up 2 cm',
            'source_peek_seconds': [3.4, 5.766666666666667],
            'intended_screen_duration_seconds': [2.5, 4.0],
        },
        'runtime_visual_validation': 'pending',
    }
    path = root / 'Saved/ElevatorTransition/departure_shots_refine_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


main()
