"""Root-only in-place execution of plan.json. Importing this module does nothing.

No level load/save, asset import, mesh edits, whole-map rebuild, or automatic
execution. Root must back up Stage3, explicitly call apply(), verify and save.
"""
import json
from pathlib import Path

OWNER = 'Stage3GateHallExtension20261125'


def apply(plan_path=None, pillar_top_cm=None, refresh_cutaway=True, rebuild_grid=True):
    import unreal as u
    import importlib
    import sys
    root = Path(u.Paths.project_dir()).resolve()
    out = root / 'Saved/Stage3GateHallRevision20261125'
    plan = json.loads(Path(plan_path or out / 'plan.json').read_text(encoding='utf-8'))
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    world = editor.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3' and not editor.get_game_world()
    existing = list(actors.get_all_level_actors())
    paths = {a.get_path_name(): a for a in existing}
    assert not any(OWNER in map(str, a.tags) for a in existing), 'Already applied; reload backup before retry'
    labels = {}
    for a in existing:
        labels.setdefault(a.get_actor_label(), []).append(a)

    def one(label):
        found = labels.get(label, [])
        assert len(found) == 1, (label, len(found))
        return found[0]

    # Validate every affected original before making the first change.
    for op in plan['moves']:
        assert paths[op['path']].get_actor_transform().export_text() == op['before_transform'], op['label']
    for op in plan['copies']:
        assert paths[op['source_path']].get_actor_transform().export_text() == op['source_transform'], op['source_label']
        assert op['label'] not in labels, op['label']
    assert pillar_top_cm is None or 900 <= pillar_top_cm <= 6000
    for spec in plan['candles']:
        assert len(paths[spec['actor_path']].get_editor_property('PatrolPoints')) == 4
    rug = one(plan['rug']['label'])
    assert abs(rug.get_actor_bounds(False, False)[1].y - 450) < .1
    before = {a.get_path_name(): a.get_actor_transform().export_text() for a in existing}
    report = {'success': False, 'level_saved': False, 'asset_imports': False,
              'moves': [], 'copies': [], 'pillar_height': [], 'pending': plan['post_apply_required']}
    out.mkdir(parents=True, exist_ok=True)
    try:
        # Copy first: original source transforms still match the reviewed plan.
        for op in plan['copies']:
            source = paths[op['source_path']]
            child = actors.duplicate_actor(source, world, u.Vector(*op['delta_world_cm']))
            assert child, op['label']
            child.set_actor_label(op['label'])
            child.tags = list(child.tags) + [u.Name(OWNER)]
            child.set_folder_path('Stage3/GateHallRevision20261125')
            labels[op['label']] = [child]
            report['copies'].append({'label': op['label'], 'path': child.get_path_name(),
                                      'source': op['source_path'], 'transform': child.get_actor_transform().export_text()})

        # Set absolute targets derived from the originals, parent-first, so an
        # attached actor is not accidentally moved twice.
        def depth(actor):
            count = 0
            while actor.get_attach_parent_actor():
                actor = actor.get_attach_parent_actor(); count += 1
            return count
        targets = []
        for op in plan['moves']:
            actor = paths[op['path']]
            transform = actor.get_actor_transform()
            transform.translation = transform.translation + u.Vector(*op['delta_world_cm'])
            targets.append((actor, transform, op))
        for actor, transform, op in sorted(targets, key=lambda row: depth(row[0])):
            actor.set_actor_transform(transform, False, True)
            report['moves'].append({'label': op['label'], 'path': op['path'],
                                     'after': actor.get_actor_transform().export_text()})

        for spec in plan['candles']:
            actor = paths[spec['actor_path']]
            for path, xy in zip(spec['waypoint_paths'], spec['canonical_route_cm']):
                waypoint = paths[path]; old = waypoint.get_actor_location()
                waypoint.set_actor_location(u.Vector(xy[0], -xy[1], old.z), False, True)
            xy = spec['canonical_route_cm'][0]; old = actor.get_actor_location()
            actor.set_actor_location(u.Vector(xy[0], -xy[1], old.z), False, True)
        scale = rug.get_actor_scale3d()
        rug.set_actor_scale3d(u.Vector(scale.x, scale.y * plan['rug']['local_y_scale_multiplier'], scale.z))
        rug.set_actor_location(u.Vector(*plan['rug']['new_center_world_cm']), False, True)
        report['rug_bounds'] = str(rug.get_actor_bounds(False, False))

        # Preserve the original 0..840cm shaft and its shadows. Reuse its540cm
        # upper module above840; only the final partial module changes scale.
        # Each continuation has one suffix so occlusion.rsplit('_',1) keeps
        # every part in the same pillar group. New high parts cannot collide.
        if pillar_top_cm is not None:
            for label, group in list(labels.items()):
                if not label.startswith('S3_GrandPillar_') or not label.endswith('_Capital'):
                    continue
                assert len(group) == 1
                capital = group[0]; shaft = one(label[:-len('Capital')] + 'ShaftUpper')
                capital_c, capital_e = capital.get_actor_bounds(False, False)
                height = capital_e.z * 2
                target_bottom = pillar_top_cm - height
                shaft_c, shaft_e = shaft.get_actor_bounds(False, False)
                shaft_bottom = shaft_c.z - shaft_e.z
                source_height = shaft_e.z * 2
                cursor = shaft_c.z + shaft_e.z
                part_index = 0
                while cursor < target_bottom - .01:
                    segment_height = min(source_height, target_bottom - cursor)
                    continuation = actors.duplicate_actor(shaft, world, u.Vector(0, 0, cursor - shaft_bottom))
                    assert continuation
                    continuation.set_actor_label(label[:-len('Capital')] + f'Continuation{part_index}')
                    continuation.tags = list(continuation.tags) + [u.Name(OWNER)]
                    continuation.set_folder_path('Stage3/GateHallRevision20261125')
                    scale = continuation.get_actor_scale3d()
                    continuation.set_actor_scale3d(u.Vector(scale.x, scale.y, scale.z * segment_height / source_height))
                    new_c, new_e = continuation.get_actor_bounds(False, False)
                    continuation.set_actor_location(continuation.get_actor_location() + u.Vector(0, 0, cursor - (new_c.z - new_e.z)), False, True)
                    component = continuation.get_component_by_class(u.StaticMeshComponent)
                    component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
                    component.set_cast_shadow(False)
                    report['copies'].append({'label': continuation.get_actor_label(), 'source': shaft.get_path_name(),
                                              'height_cm': segment_height, 'bottom_cm': cursor,
                                              'collision': 'NoCollision', 'cast_shadow': False})
                    cursor += segment_height; part_index += 1
                capital.set_actor_location(capital.get_actor_location() + u.Vector(0, 0, target_bottom - (capital_c.z - capital_e.z)), False, True)
                capital_component = capital.get_component_by_class(u.StaticMeshComponent)
                capital_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
                capital_component.set_cast_shadow(False)
                report['pillar_height'].append({'capital': label, 'top_cm': pillar_top_cm})

        sys.path.insert(0, str(root / 'Scripts/Stage3/GothicRevision'))
        if refresh_cutaway:
            import occlusion
            importlib.reload(occlusion)
            report['cutaway'] = occlusion.apply()
        if rebuild_grid:
            grid = one('S3_SoundGrid'); grid.build_grid(); assert grid.has_grid()
            report['grid'] = json.loads(grid.call_method('ExportBakedGridSnapshot'))
        # Native objectives initialize FinalLeaf start positions at BeginPlay.
        # D2 locks, puzzle links, altar and shared camera are never touched.
        one('S3_Objectives').tags = list(one('S3_Objectives').tags) + [u.Name(OWNER)]
        report['changed_existing_actor_transforms'] = [
            a.get_path_name() for a in existing
            if a.get_actor_transform().export_text() != before[a.get_path_name()]]
        report['measured_structural_bounds'] = []
        for actor in actors.get_all_level_actors():
            tags = list(map(str, actor.tags))
            if not any(tag in tags for tag in ('SoundFloor', 'SoundWall')):
                continue
            center, extent = actor.get_actor_bounds(False, False)
            report['measured_structural_bounds'].append({
                'label': actor.get_actor_label(), 'tags': tags,
                'min': [center.x - extent.x, center.y - extent.y, center.z - extent.z],
                'max': [center.x + extent.x, center.y + extent.y, center.z + extent.z]})
        report['success'] = True
        return report
    finally:
        (out / ('applied_unsaved.json' if report['success'] else 'attempt_error.json')).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
