"""Root-writer-only short mechanical connections. apply() never saves a map.

All meshes are separate NoCollision actors. Existing E chain actors remain the
animation drivers; their transforms, scales, mesh assignments and collision stay
unchanged. Original ring/pin geometry and bite height are untouched.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GothicRevision20261125'
PREFIX = 'S3_GothicConnections_'
TAG = 'Stage3GothicConnections20261125'
SOURCE = Path('C:/Users/whghk/Desktop/CastleKit/Stage3/Mechanisms03_20261125')


def add(a, b): return [x + y for x, y in zip(a, b)]
def sub(a, b): return [x - y for x, y in zip(a, b)]
def mul(a, s): return [x * s for x in a]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def norm(a):
    length = math.sqrt(dot(a, a))
    if length < 1e-6: raise RuntimeError('Zero direction')
    return mul(a, 1 / length)
def xyz(v): return [v.x, v.y, v.z]


def nearest_wall_face(point, walls, max_distance=120, width_margin=21, minimum=4):
    """Only normal-to-wall, short, same-height routes to solid wall modules.

    Excludes gate/cathole frames: their AABBs do not establish a solid wall.
    Requires the entire intake width/height to sit inside one real wall segment.
    """
    candidates = []
    for label, box in walls.items():
        lo, hi = box
        sizes = sub(hi, lo)
        normal_axis = 0 if sizes[0] < sizes[1] else 1
        along = 1 - normal_axis
        if sizes[normal_axis] > 60:
            continue
        if not lo[along] <= point[along] <= hi[along]:
            continue
        if not lo[2] + 24 <= point[2] <= hi[2] - 28:
            continue
        if point[normal_axis] < lo[normal_axis]:
            face, sign = lo[normal_axis], 1
        elif point[normal_axis] > hi[normal_axis]:
            face, sign = hi[normal_axis], -1
        else:
            continue
        length = abs(face - point[normal_axis])
        if not minimum <= length <= max_distance:
            continue
        # A legitimate intake may straddle a modular-wall seam. Establish that
        # adjacent coplanar actual wall boxes cover its entire backing width.
        spans = []
        support = []
        for other_label, (a, b) in walls.items():
            other_sizes = sub(b, a)
            other_axis = 0 if other_sizes[0] < other_sizes[1] else 1
            other_face = a[normal_axis] if sign > 0 else b[normal_axis]
            if other_axis == normal_axis and abs(other_face - face) <= .2 and a[2] + 24 <= point[2] <= b[2] - 28:
                spans.append((a[along], b[along])); support.append(other_label)
        reach = point[along] - width_margin
        for a, b in sorted(spans):
            if a <= reach + .2 and b >= reach:
                reach = max(reach, b)
        if reach < point[along] + width_margin:
            continue
        endpoint = list(point); endpoint[normal_axis] = face
        direction = [0., 0., 0.]; direction[normal_axis] = sign
        candidates.append({'wall': label, 'wall_bounds': box, 'start': point,
            'wall_point': endpoint, 'direction': direction, 'length_cm': length,
            'coplanar_backing_candidates': support})
    if not candidates:
        raise RuntimeError('No safe real-wall intake within %.1f cm of %s' % (max_distance, point))
    return min(candidates, key=lambda r: (r['length_cm'], r['wall']))


def connection_axis_map(imported):
    """Infer the shared Connection exporter mapping from asymmetric parts.

    Link/wheel AABBs alone are symmetric. Cover disambiguates X; intake and mount
    disambiguate Y. Refuse rather than silently guess an unsupported convention.
    """
    common = None
    for name in ('SM_S3_ChainConnection_Cover', 'SM_S3_ChainWallIntake', 'SM_S3_WallPulley_Mount'):
        options = {tuple(r['ue_axes_from_blender']) for r in imported['meshes'][name]['axis_mapping_candidates']}
        common = options if common is None else common & options
    if len(common or ()) != 1:
        raise RuntimeError('Connection source/UE axes are not uniquely established: ' + str(common))
    return list(next(iter(common)))


def apply(import_report=None, include_release_skins=True):
    import unreal as u
    ea = u.EditorAssetLibrary
    act = u.get_editor_subsystem(u.EditorActorSubsystem)
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if editor.get_editor_world().get_path_name() != '/Game/Maps/Stage3.Stage3':
        raise RuntimeError('Load saved Stage3 before applying connections')
    imported = import_report or json.loads((OUT / 'import_report.json').read_text())
    if not imported.get('success') or len(imported.get('meshes', {})) != 24:
        raise RuntimeError('Need a successful current 24-mesh import report')
    mapping = connection_axis_map(imported)
    assembly = json.loads((SOURCE / 'Assemblies/WallTransmission_Connected.json').read_text())
    # The reviewed source route establishes physically interlinked pitch/stock;
    # it does not authorize copying its 150cm wall placement into the actual map.
    samples = assembly['chain_samples']
    pitch = math.dist(samples[0][0], samples[1][0]) * 100
    # Final independent QA increased reviewed link pitch from 8.76 to 9.16 cm.
    # Take the current source sample spacing; do not pin it to an older batch.
    if not 8.0 < pitch < 10.0:
        raise RuntimeError('Unexpected reviewed chain pitch: ' + str(pitch))
    lookup = {a.get_actor_label(): a for a in act.get_all_level_actors()}
    meshes = {}
    for name, row in imported['meshes'].items():
        mesh = ea.load_asset(row['path'])
        if not isinstance(mesh, u.StaticMesh): raise RuntimeError('Missing imported mesh: ' + name)
        box = mesh.get_bounding_box()
        actual = [xyz(box.min), xyz(box.max)]
        expected = row.get('bounds_cm', row['bounds'])
        if max(abs(actual[r][c] - expected[r][c]) for r in range(2) for c in range(3)) > .05:
            raise RuntimeError('Imported mesh bounds drift: ' + name)
        meshes[name] = mesh

    def actor_box(actor):
        origin, extent = actor.get_actor_bounds(False)
        return [xyz(origin - extent), xyz(origin + extent)]

    walls = {label: actor_box(actor) for label, actor in lookup.items() if label.startswith('S3_Wall_')}
    if not walls: raise RuntimeError('No actual S3_Wall actors found')
    plans = []
    for n in (1, 2):
        label = 'S3_GothicVisual_Dock%d_DockChainTerminal' % n
        terminal = lookup[label]
        # Use the corrected, already-placed actor. Never infer a dock +/-X sign
        # from Blender source translation or a symmetric imported mesh.
        eye = xyz(terminal.get_actor_location())
        initial_route = nearest_wall_face(eye, walls)
        # The load eye moves +5.847 cm on seating. Connect the wall run to the
        # FIXED receiver shell, not to that moving eye. Source receiver shell is
        # Z101.8..118.45 cm, half-width4.95; open eye origin isZ119.8367cm.
        anchor=add(eye,mul(initial_route['direction'],4.95))
        anchor[2]-=9.
        route = nearest_wall_face(anchor, walls)
        plans.append(dict(route, name='Dock%d' % n,
            anchor_actor='S3_GothicVisual_Dock%d_DockArch' % n,
            fixed_receiver_offset_from_open_eye_cm=sub(anchor,eye),guide=False))
    for n in (1, 2, 3):
        label = 'S3_GothicVisual_Lock%d_Housing' % n
        housing = lookup[label]
        lo, hi = actor_box(housing)
        # A short fixed chain emerges from a guide on the stationary front face.
        # It never attaches to the retracting bolt, so bolt motion cannot stretch it.
        anchor = [(lo[0] + hi[0]) / 2, lo[1] - 10., (lo[2] + hi[2]) / 2]
        route = nearest_wall_face(anchor, walls, max_distance=90)
        plans.append(dict(route, name='D2Lock%d' % n, anchor_actor=label,
                          guide=True, guide_wall_point=[anchor[0], lo[1], anchor[2]]))

    driver_labels = [label for label in lookup if any(label.startswith('S3_Release%d_' % n) for n in (1, 2, 3))]
    driver_labels += ['S3_Lock%d_%s' % (n, part) for n in (1, 2, 3) for part in ('Housing', 'Bolt', 'Keeper')]
    original = {label: {'transform': lookup[label].get_actor_transform().export_text(),
                'mesh': lookup[label].static_mesh_component.static_mesh.get_path_name(),
                'collision': str(lookup[label].static_mesh_component.get_collision_enabled())}
                for label in driver_labels}
    for n in (1, 2, 3):
        if abs(lookup['S3_Release%d_Ring' % n].get_actor_location().z - 27.5) > .01:
            raise RuntimeError('Original bite ring height is not 27.5 cm')
    report = {'success': False, 'import_sha256': imported['input_sha256'],
              'source_to_ue_axes': mapping, 'chain_pitch_cm': pitch,
              'routes': plans, 'actors': {}, 'old_chain_hidden': [],
              'map_saved': False, 'runtime_verified': False,
              'notes': ['Wall throats conceal continuation; existing wall geometry/collision is not cut.',
                        'Fixed routes terminate at stationary guides/housings; no tether spans a moving bolt.',
                        'E chain children follow existing animation actors; original ring/pin positions are unchanged.']}

    def transform_basis(basis, scales=(1., 1., 1.)):
        # mapping gives UE local axis components in Blender coordinates. Convert
        # those axes to the desired world basis, including handedness via scale.
        axes, native_scales = [], []
        for token in mapping:
            j = 'XYZ'.index(token[1]); sign = -1 if token[0] == '-' else 1
            axes.append(mul(basis[j], sign)); native_scales.append(scales[j])
        if dot(cross(axes[0], axes[1]), axes[2]) < 0:
            axes[1] = mul(axes[1], -1); native_scales[1] *= -1
        rotation = u.MathLibrary.make_rotation_from_axes(*[u.Vector(*a) for a in axes])
        return rotation, native_scales

    spawned = []
    def spawn(label, name, position, basis, scales=(1., 1., 1.), parent=None):
        rotation, native_scales = transform_basis(basis, scales)
        actor = act.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*position), rotation)
        if not actor: raise RuntimeError('Spawn failed: ' + label)
        spawned.append(actor)
        actor.set_actor_label(PREFIX + label)
        actor.tags = [u.Name(TAG)]
        actor.set_folder_path('Stage3/GothicRevision/Connections')
        comp = actor.static_mesh_component
        comp.set_mobility(u.ComponentMobility.MOVABLE)
        comp.set_static_mesh(meshes[name])
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        comp.set_collision_response_to_all_channels(u.CollisionResponseType.ECR_IGNORE)
        comp.set_editor_property('can_ever_affect_navigation', False)
        actor.set_actor_scale3d(u.Vector(*native_scales))
        if parent:
            actor.attach_to_actor(parent, u.Name('None'), u.AttachmentRule.KEEP_WORLD,
                                  u.AttachmentRule.KEEP_WORLD, u.AttachmentRule.KEEP_WORLD, False)
        comp.set_collision_profile_name('NoCollision')
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        report['actors'][actor.get_actor_label()] = {'mesh': meshes[name].get_path_name(),
            'position': xyz(actor.get_actor_location()), 'rotation': str(actor.get_actor_rotation()),
            'scale': xyz(actor.get_actor_scale3d()), 'parent': parent.get_actor_label() if parent else None,
            'collision': str(comp.get_collision_enabled())}
        return actor

    try:
        # Cleanup is restricted to our own tag as well as our reserved prefix.
        for label, actor in lookup.items():
            if label.startswith(PREFIX):
                if TAG not in [str(t) for t in actor.tags]:
                    raise RuntimeError('Unowned actor under connection prefix: ' + label)
                if not act.destroy_actor(actor): raise RuntimeError('Cannot remove previous connection: ' + label)
        up = [0., 0., 1.]
        for route in plans:
            label, start, end, direction = route['name'], route['start'], route['wall_point'], route['direction']
            # Intake local +Y enters wall; back plane is exactly on actual wall face.
            side = cross(direction, up)
            spawn(label + '_Intake', 'SM_S3_ChainWallIntake', sub(end, [0, 0, 23]), [side, direction, up])
            if route['guide']:
                # Guide +Z chain axis rotates to the route tangent while backing
                # plane remains flush to the stationary housing's -Y front face.
                by = [0., 1., 0.]
                bx = norm(cross(by, direction))
                spawn(label + '_Guide', 'SM_S3_ChainGuide_Bracket', route['guide_wall_point'], [bx, by, direction])
            # Keep full-size link stock/pitch. Adjust only the last hidden segment;
            # do not stretch a 100cm chain mesh to arbitrary route lengths.
            length = route['length_cm']
            count = max(1, math.ceil((length + 3) / pitch))
            for index in range(count):
                distance = min(length + 2, index * pitch + 2)
                position = add(start, mul(direction, distance))
                by = norm(cross(up, direction)) if index % 2 else up
                bx = norm(cross(by, direction))
                spawn(label + '_Chain%02d' % index, 'SM_S3_MechanismChain_Link', position, [bx, by, direction])
            # A short folded cover is anchored at dock and intake. Do not cover
            # very short connections, and never make an unsupported room-wide run.
            if not route['guide'] and length > 45:
                by = norm(cross(up, direction))
                cover_start = add(add(start, mul(direction, 8)), mul(by, 7.5))
                spawn(label + '_Cover', 'SM_S3_ChainConnection_Cover', cover_start,
                      [direction, by, up], ((length - 18) / 100., 1., 1.))
        if include_release_skins:
            for n in (1, 2, 3):
                for i in range(6):
                    old = lookup['S3_Release%d_Chain%d' % (n, i)]
                    transform = old.get_actor_transform()
                    # Existing centers and animation timing remain authoritative.
                    # Old links have ~7.8cm pitch; keep new links at matching pitch
                    # using one uniform scale, preserving round stock proportions.
                    next_old = lookup['S3_Release%d_Chain%d' % (n, min(i + 1, 5))]
                    previous = lookup['S3_Release%d_Chain%d' % (n, max(i - 1, 0))]
                    tangent = norm(xyz(next_old.get_actor_location() - previous.get_actor_location()))
                    normal = [1., 0., 0.] if i % 2 == 0 else norm(cross(tangent, [1., 0., 0.]))
                    bx = norm(cross(normal, tangent))
                    adjacent = next_old if i < 5 else previous
                    actual_pitch = math.dist(xyz(old.get_actor_location()), xyz(adjacent.get_actor_location()))
                    scale = actual_pitch / pitch
                    if not .7 <= scale <= 1.15: raise RuntimeError('E chain spacing changed unexpectedly')
                    child = spawn('E%d_Chain%d' % (n, i), 'SM_S3_MechanismChain_Link', xyz(old.get_actor_location()),
                                  [bx, normal, tangent], (scale, scale, scale), old)
                    # Children preserve the old transform as their animated driver.
                    if old.get_actor_transform().export_text() != transform.export_text(): raise RuntimeError('Attachment moved original E chain')
                    comp = old.static_mesh_component
                    comp.set_visibility(False, False)
                    comp.set_hidden_in_game(True, False)
                    comp.set_cast_shadow(False)
                    report['old_chain_hidden'].append(old.get_actor_label())
        for label, before in original.items():
            actor = lookup[label]; comp = actor.static_mesh_component
            after = {'transform': actor.get_actor_transform().export_text(), 'mesh': comp.static_mesh.get_path_name(),
                     'collision': str(comp.get_collision_enabled())}
            if after != before: raise RuntimeError('Original gameplay actor changed: ' + label)
        report['original_driver_count_verified'] = len(original)
        report['actor_count'] = len(spawned)
        report['success'] = True
        return report
    except Exception as exc:
        report['error'] = repr(exc)
        raise
    finally:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'connections_report.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    raise SystemExit('Root writer must explicitly call connections.apply(); no map save is performed.')
