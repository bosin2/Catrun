"""Read-only live inventory for the root's Stage3 obstacle-tag integration.

Call inspect(world) in the root-owned editor or isolated PIE. No mutation,
rebake, package save or actor creation. Dynamic native puzzle refs are excluded.
"""
import unreal as u

SCENE_STATIC_OBSTACLE_LABELS = tuple('S3_Gothic_' + suffix for suffix in (
    'LobbyBench', 'LobbyCabinet', 'LowerStrategy', 'LowerBench',
    'ExhibitionShield', 'WarehouseMaintenance'))


def vec(v):
    return [v.x, v.y, v.z]


def inspect(world=None):
    if world is None:
        world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    assert 'S3_SoundGrid' in actors
    grid = actors['S3_SoundGrid']
    settings = grid.get_editor_property('Settings')
    obstacle_tag = str(settings.get_editor_property('ObstacleTag'))
    excluded = set()
    for link in actors['S3_StatuePuzzles'].get_editor_property('Links'):
        excluded.update(link.get_editor_property(key) for key in ('Statue', 'Plate', 'Gate'))
    for device in actors['S3_Objectives'].get_editor_property('Devices'):
        for key in ('Housing', 'Ring', 'Pin', 'LockBolt'):
            try:
                excluded.add(device.get_editor_property(key))
            except Exception:
                pass
    names = list(SCENE_STATIC_OBSTACLE_LABELS)
    names += sorted(label for label, actor in actors.items()
                    if 'Basket' in label and label.endswith('_Body') and actor not in excluded)
    result = {'settings': settings.get_path_name(), 'obstacle_tag': obstacle_tag,
              'trace_height_cm': settings.get_editor_property('TraceHeight'),
              'armor_clearance_cm': settings.get_editor_property('ArmorClearance'),
              'floor_z': grid.get_floor_z(), 'rows': [], 'scene_static_obstacle_labels': [],
              'mutations': 0,
              'note': 'Tags affect armor WallDistance only. Root must BuildGrid after approved tags/geometry are final.'}
    for label in names:
        actor = actors.get(label)
        if actor is None:
            result['rows'].append({'label': label, 'exists': False})
            continue
        assert actor not in excluded
        components = actor.get_components_by_class(u.PrimitiveComponent)
        solid = [c for c in components if c.get_collision_enabled() != u.CollisionEnabled.NO_COLLISION
                 and c.get_collision_object_type() == u.CollisionChannel.ECC_WORLD_STATIC
                 and c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN) == u.CollisionResponseType.ECR_BLOCK]
        center, extent = actor.get_actor_bounds(True, False)
        tags = list(map(str, actor.tags))
        row = {'label': label, 'exists': True, 'static_pawn_blocking': bool(solid),
               'tags': tags, 'obstacle_tag_missing': obstacle_tag not in tags,
               'bounds_min': vec(center - extent), 'bounds_max': vec(center + extent),
               'component_names': [c.get_name() for c in solid]}
        result['rows'].append(row)
        if solid:
            result['scene_static_obstacle_labels'].append(label)
    return result
