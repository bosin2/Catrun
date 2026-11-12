"""Read the live editor world's architectural meshes for a one-time top-down capture."""

import math
import unreal as u


MAP_NAMES = ('Tutorial', 'Stage1', 'Stage2', 'SoundTest_Tutorial', 'SoundTest_Stage1', 'SoundTest_Stage2')


def geometry_role(label, mesh, tags):
    name = (label + ' ' + mesh).lower()
    # The remote Tutorial descent set is separate from the playable stairwell.
    if label.startswith('SET_DescentStair_'):
        return None
    # Omit overhead caps across openings so the floor path remains visible from above.
    if any(part in name for part in ('ceiling', 'roof', 'lintel', 'doorupper', 'doorleaf',
                                     'doorframe', 'stonearch', 'bedroomarch', 'gate_', 'risinggate',
                                     'occluder', '_collision', 'accessblocker')):
        return None
    if ('SoundFloor' in tags or mesh.startswith(('SM_Floor_', 'SM_Stage01_Floor_',
                                                   'SM_Stage2_Floor_', 'SM_StairTread_'))
            or label.startswith(('S1_MagicCorridor_Floor', 'S1_MagicCorridor_Threshold'))):
        return 'floor'
    if ('SoundWall' in tags or mesh.startswith(('SM_StoneWall_', 'SM_StairWall_', 'SM_Wall_Straight',
                                                 'SM_Stage01_Wall_', 'SM_Stage2_Wall', 'SM_Annex_CorridorWall_'))
            or label in ('S1_ArrivalStair_ClosedEnd', 'S1_MagicCorridor_DarkEnd')):
        return 'wall'
    return None


def capture_plan(world):
    """Return capture frame, floor actors and wall actors. Does not mutate the world."""
    name = world.get_name()
    assert name in MAP_NAMES, name
    selected = {'floor': [], 'wall': []}
    bounds = []
    for actor in sorted(u.GameplayStatics.get_all_actors_of_class(world, u.StaticMeshActor),
                        key=lambda item: item.get_name()):
        component = actor.static_mesh_component
        mesh = component.get_editor_property('static_mesh')
        if not mesh or not component.is_visible() or component.get_editor_property('hidden_in_game'):
            continue
        role = geometry_role(actor.get_actor_label(), mesh.get_name(),
                             {str(tag) for tag in actor.get_editor_property('tags')})
        if role:
            selected[role].append(actor)
            bounds.append(actor.get_actor_bounds(False, False))

    floors, walls = selected['floor'], selected['wall']
    assert floors and walls, (name, len(floors), len(walls))
    min_x = min(origin.x - extent.x for origin, extent in bounds)
    max_x = max(origin.x + extent.x for origin, extent in bounds)
    min_y = min(origin.y - extent.y for origin, extent in bounds)
    max_y = max(origin.y + extent.y for origin, extent in bounds)
    max_z = max(origin.z + extent.z for origin, extent in bounds)
    span = max(max_x - min_x, max_y - min_y)
    side = math.ceil(span + 2 * max(60., .045 * span))
    frame = {
        'center': [(min_x + max_x) * .5, (min_y + max_y) * .5],
        'size': [side, side],
        'yaw': 0.,
        'capture_z': max_z + max(side, 1000.),
        'geometry_bounds_xy': [[min_x, min_y], [max_x, max_y]],
        'floor_count': len(floors),
        'wall_count': len(walls),
    }
    return frame, floors, walls
