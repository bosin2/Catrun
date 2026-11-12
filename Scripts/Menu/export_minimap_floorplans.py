"""Read-only UE commandlet export of the six authored architectural floorplans.

Run with -run=pythonscript -script=<this file> -nullrhi. No actors, assets or maps
are modified. The existing capture manifest is the marker projection contract.
Actual LOD0 sections are used when the enabled Unreal Python API exposes them;
otherwise each mesh uses its transformed local bounding box, explicitly reported.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from minimap_geometry import MAP_NAMES, capture_plan

OUT = ROOT / 'Saved/GameplayRepair20261112/BasketUsability/Floorplans'
FRAMES = ROOT / 'Saved/ChaptersFlow20261112/Captures/manifest.json'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)


def hull(points):
    points = sorted(set(tuple(p) for p in points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1]+upper[:-1]]


def mesh_sections(mesh, cache):
    path = mesh.get_path_name()
    if path in cache:
        return cache[path]
    library = getattr(u, 'ProceduralMeshLibrary', None) or getattr(u, 'KismetProceduralMeshLibrary', None)
    try:
        assert library and hasattr(library, 'get_section_from_static_mesh'), 'Mesh section export API is not enabled'
        vertices, indices = [], []
        for section in range(mesh.get_num_sections(0)):
            data = library.get_section_from_static_mesh(mesh, 0, section)
            local_vertices, local_indices = data[0], data[1]
            offset = len(vertices)
            vertices.extend(local_vertices)
            indices.extend(offset+int(i) for i in local_indices)
        assert vertices and indices and len(indices) % 3 == 0, 'LOD0 section export is empty'
        assert all(0 <= i < len(vertices) for i in indices), 'LOD0 indices are invalid'
        result = (vertices, indices, None)
    except Exception as error:
        result = (None, None, str(error))
    cache[path] = result
    return result


def footprint(actor, role, cache):
    component = actor.static_mesh_component
    mesh = component.get_editor_property('static_mesh')
    transform = component.get_world_transform()
    low, high = component.get_local_bounds()
    world_bounds = [u.MathLibrary.transform_location(transform, u.Vector(x, y, z))
                    for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]
    polygon = hull([[float(p.x), float(p.y)] for p in world_bounds])
    result = {'actor': actor.get_path_name(), 'label': actor.get_actor_label(),
              'mesh': mesh.get_path_name(), 'role': role, 'bounds_polygon_xy': polygon,
              'z_range': [min(float(p.z) for p in world_bounds), max(float(p.z) for p in world_bounds)]}
    vertices, indices, reason = mesh_sections(mesh, cache)
    if vertices:
        points = [u.MathLibrary.transform_location(transform, p) for p in vertices]
        result.update(method='lod0_projected_triangle_union',
                      points_xy=[[float(p.x), float(p.y)] for p in points], triangles=indices)
    else:
        result.update(method='transformed_local_bounds_approximation', polygon_xy=polygon,
                      approximation_reason=reason)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'maps': {}, 'completed': False,
              'source_frame_manifest': str(FRAMES), 'projection': '+Y right, +X up; yaw 0',
              'selection': 'minimap_geometry.capture_plan; overhead caps and moving doors omitted',
              'limitations': ['Static architectural projection, not a navigation/pathfinding proof.',
                             'Fallback bounds can overfill irregular meshes and openings within a single mesh.',
                             'Separate doorway gaps and corridor actor placement are never inferred or closed.']}
    try:
        assert not ED.get_game_world(), 'Do not run in PIE'
        assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Do not switch away from a dirty map'
        frames = json.loads(FRAMES.read_text(encoding='utf8'))['maps']
        report['source_frame_manifest_sha256'] = hashlib.sha256(FRAMES.read_bytes()).hexdigest()
        requested = os.environ.get('CATRUN_FLOORPLAN_MAPS', ','.join(MAP_NAMES)).split(',')
        cache = {}
        for name in requested:
            assert name in MAP_NAMES and name in frames, name
            assert LEVEL.load_level('/Game/Maps/'+name), name
            calculated, floors, walls = capture_plan(ED.get_editor_world())
            source = frames[name]
            assert abs(float(source['yaw'])) < .0001, 'Only the existing yaw-0 projection is supported'
            # Never refit or crop: that would silently offset every runtime marker.
            frame = {key: source[key] for key in ('center', 'size', 'yaw')}
            actors = [footprint(actor, role, cache) for role, group in (('floor', floors), ('wall', walls))
                      for actor in group]
            payload = {'frame': frame, 'geometry': actors}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            report['maps'][name] = dict(payload, geometry_sha256=digest,
                floor_count=len(floors), wall_count=len(walls), actual_geometry_frame=calculated,
                stored_frame_matches_calculated=all(source[key] == calculated[key] for key in ('center', 'size', 'yaw')),
                actual_mesh_count=sum(a['method']=='lod0_projected_triangle_union' for a in actors),
                bounds_approximation_count=sum(a['method']=='transformed_local_bounds_approximation' for a in actors))
            assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Read-only export dirtied a map'
            (OUT/'geometry.json').write_text(json.dumps(report, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
            print('CATRUN_FLOORPLAN_EXPORTED', name, len(floors), len(walls))
        report['completed'] = all(name in report['maps'] for name in MAP_NAMES)
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        (OUT/'geometry.json').write_text(json.dumps(report, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
        print('CATRUN_FLOORPLAN_GEOMETRY', str(OUT/'geometry.json'))


if __name__ == '__main__':
    main()
