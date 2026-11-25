"""Stage3 functional basket/enemy + restrained dressing placement, root-only.

Import is inert. Root calls apply() in an existing non-PIE Stage3 editor world,
reviews the returned report, rebuilds native navigation/sound-grid if needed,
and saves separately. No package/map save or shared asset edits occur here.
Failure destroys only actors created in this invocation. Existing actors are
not relocated or modified. Actual F/WASD entry/exit and enemy play remain PIE QA.
"""
import hashlib
import json
import math
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3PlacementRevision20261125'
OWNER = 'Stage3PlacementRevision20261125'
PREFIX = 'S3_Placement_'
BASKETS = (
    ('Lobby', (-170., -345., 0.)),
    ('Exhibition', (-970., -2195., 0.)),
    ('Warehouse', (605., -1410., 0.)),
    ('ControlAnnex', (-304., -2045., 0.)),
)
NEW_ENEMY = (-895., -2310., 0.)
ENEMY_YAW = 90.
# Console reaches X420/Z109.5; banner at X480 has its lower cloth edge at
# X430 and therefore does not intersect the existing console below it.
BANNER = (480., -2515., 285.)
CANDLE = (815., -1430., 90.5)
FLAME = (815.45, -1430., 114.98)
DIRS = ('F', 'FR', 'R', 'BR', 'B', 'BL', 'L', 'FL')


def apply():
    import unreal as u
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'success': False, 'packages_saved': False, 'created': [], 'baskets': [],
              'enemy_change': {'Exhibition': [1, 2], 'Warehouse': [2, 2], 'Stage3': [5, 6]},
              'requires_root_runtime_qa': ['Actual F entry, camera-relative WASD/F exit and cloth animation on all four baskets.',
                                          'Blocking-body collision and sound-grid/native navigation refresh after root integration.',
                                          'Cat AND armor traverse UpperCorridor <-> ControlRoom past the west-side Annex basket; free exit points alone are insufficient.',
                                          'New fixed candle detection/marks against P1 push route and basket recovery; no full-play difficulty claim.'],
              'untouched_scope': 'Existing actors, altar structural walls/E3/P2, GateHall, shared assets and Source.'}
    created = []
    actor_subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not editor.get_game_world(), 'Apply outside PIE only'
    before = list(actor_subsystem.get_all_level_actors())
    labels = {a.get_actor_label(): a for a in before}
    assert not any(a.get_actor_label().startswith(PREFIX) for a in before), 'Refuse duplicate placement run'
    assert not any(isinstance(a, u.CatrunHideBasket) for a in before), 'Stage3 basket baseline changed; re-audit'
    before_transforms = {a.get_path_name(): a.get_actor_transform().export_text() for a in before}
    disk_map = ROOT / 'Content/Maps/Stage3.umap'
    map_hash = hashlib.sha256(disk_map.read_bytes()).hexdigest()
    cat = next(a for a in before if a.get_class().get_name() == 'BP_Cat_C')
    cap = cat.get_component_by_class(u.CapsuleComponent)
    camera = next(a for a in before if 'QuarterViewCamera' in a.get_class().get_name())
    camera_yaw = camera.get_component_by_class(u.CameraComponent).get_world_rotation().yaw
    import_report = json.loads((ROOT / 'Saved/BasketIntegration20261125/import_report.json').read_text(encoding='utf8'))
    assert import_report['success']
    def load(path):
        obj = u.load_asset(path)
        assert obj, path
        return obj
    meshes = {name: load(import_report['stages']['3'][name]) for name in ('body', 'cloth')}
    animations = {name: load(row['path']) for name, row in import_report['animations'].items()}
    geometry = meshes['body'].get_editor_property('body_setup').get_editor_property('agg_geom')
    shape_count = len(geometry.get_editor_property('box_elems'))
    assert shape_count == 5, 'Stage3 basket must retain its authored floor + four wall collision boxes'
    report['basket_asset_checks'] = {'body': meshes['body'].get_path_name(),
                                   'cloth': meshes['cloth'].get_path_name(),
                                   'collision_boxes': shape_count, 'animation_asset_count': len(animations)}
    def vec(v):
        return [v.x, v.y, v.z]
    def own(actor, label):
        assert actor, label
        created.append(actor)
        actor.set_actor_label(PREFIX + label)
        actor.set_folder_path('Stage3/PlacementRevision20261125')
        actor.tags = list(actor.tags) + [u.Name(OWNER)]
        return actor
    def spawn(cls, label, location, yaw=0.):
        return own(actor_subsystem.spawn_actor_from_class(cls, u.Vector(*location), u.Rotator(yaw=yaw)), label)
    def no_collision(component):
        component.set_collision_profile_name('NoCollision')
        component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    def read_hit(hit):
        if not hit:
            return None
        d = hit.to_dict()
        return {'actor': d['hit_actor'].get_actor_label() if d['hit_actor'] else None,
                'blocking': d['blocking_hit'], 'initial_overlap': d['initial_overlap'],
                'impact': vec(d['impact_point']), 'normal': vec(d['impact_normal'])}
    object_types = [getattr(u.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
    def capsule_blockers(location, ignore):
        comps = u.SystemLibrary.capsule_overlap_components(world, location, cap.get_scaled_capsule_radius(),
            cap.get_scaled_capsule_half_height(), object_types, u.PrimitiveComponent, ignore) or []
        return [c.get_path_name() for c in comps if c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN) == u.CollisionResponseType.ECR_BLOCK
                and cap.get_collision_response_to_channel(c.get_collision_object_type()) == u.CollisionResponseType.ECR_BLOCK]
    def supported(reference, ignore, above=50., below=100.):
        center = reference + u.Vector(0, 0, cap.get_scaled_capsule_half_height())
        hit = u.SystemLibrary.capsule_trace_single_by_profile(world, center + u.Vector(0,0,above), center-u.Vector(0,0,below),
            cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, u.DrawDebugTrace.NONE, False)
        if not hit:
            return None
        d = hit.to_dict()
        if not d['blocking_hit'] or d['initial_overlap'] or d['impact_normal'].z < .65 or isinstance(d['hit_actor'], u.Pawn):
            return None
        if math.hypot(d['impact_point'].x-d['location'].x, d['impact_point'].y-d['location'].y) > cap.get_scaled_capsule_radius()-.15:
            return None
        if not reference.z-below-.01 <= d['impact_point'].z <= reference.z+above+.01:
            return None
        return u.Vector(reference.x, reference.y, d['location'].z+2.)
    def sweep(start, end, ignore):
        return u.SystemLibrary.capsule_trace_single_by_profile(world, start, end, cap.get_scaled_capsule_radius(),
            cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, u.DrawDebugTrace.NONE, False)
    def basket_geometry(basket, body, cloth, anchor):
        origin = anchor.get_world_location()
        ignore = [cat, basket, body, cloth]
        start = supported(origin, ignore)
        assert start is not None, ('No hidden-origin floor', basket.get_actor_label())
        rows = []
        for index in range(8):
            angle = math.radians(camera_yaw + index*45.)
            dx, dy = math.cos(angle), math.sin(angle)
            # Actual eight-clip cloth traversal adds 24*abs(localX*localY),
            # not direction snapping. Body/cloth yaw=0 and Edge_F faces +Y.
            distance = 82. + 24.*abs(dx*dy)
            reference = origin + u.Vector(dx*distance, dy*distance, 0)
            landing = supported(reference, ignore)
            entry = supported(reference, [cat], 0., 50.)
            approach = supported(origin + u.Vector(dx*103., dy*103., 0), [cat], 0., 50.)
            transit = sweep(start, landing, ignore) if landing else None
            blockers = capsule_blockers(landing, [cat]) if landing else []
            entry_travel = sweep(approach, entry, [cat]) if approach and entry else None
            sight = u.SystemLibrary.line_trace_single(world, entry, origin, u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                False, [cat], u.DrawDebugTrace.NONE, False) if entry else None
            sight_actor = sight.to_dict()['hit_actor'] if sight else None
            row = {'screen_octant': index, 'is_cardinal_key': index % 2 == 0,
                   'direction': [dx, dy], 'distance': distance,
                   'exit_safe': bool(landing is not None and not transit and not blockers),
                   'entry_safe': bool(entry is not None and approach is not None and not entry_travel and sight_actor in (None, basket, body)),
                   'exit_landing': vec(landing) if landing else None,
                   'transit': read_hit(transit), 'restore_blockers': blockers}
            rows.append(row)
        safe_cardinal = sum(r['exit_safe'] and r['is_cardinal_key'] for r in rows)
        safe_entry = sum(r['entry_safe'] for r in rows)
        minimum_cardinal = 1 if basket.get_actor_label().endswith('ControlAnnex') else 2
        return {'actor': basket.get_actor_label(), 'hidden': vec(origin), 'camera_yaw': camera_yaw,
                'directions': rows, 'safe_cardinal_exits': safe_cardinal, 'safe_entries': safe_entry,
                'minimum_safe_cardinal_exits': minimum_cardinal,
                'passed': safe_cardinal >= minimum_cardinal and safe_entry >= 1,
                'limits': 'Geometric static-world proof only; blocked other directions remain blocked by native gameplay.'}
    try:
        candle_actors = [a for a in before if a.get_class().get_name() == 'BP_Candle_C']
        assert len(candle_actors) == 5, 'Candle count changed; re-audit'
        # Duplicate a fixed existing Stage3 candle to preserve actual presentation,
        # detection tuning, animation and collision without editing its Blueprint.
        enemy = own(actor_subsystem.duplicate_actor(labels['S3_Candle_WarehouseNorth'], world, u.Vector()), 'Candle_ExhibitionNorth')
        enemy.set_actor_location_and_rotation(u.Vector(*NEW_ENEMY), u.Rotator(yaw=ENEMY_YAW), False, True)
        enemy.set_editor_property('PatrolPoints', [])
        enemy.set_editor_property('bPatrolEnabled', False)
        enemy.set_editor_property('bPatrolLoop', False)
        basket_trios = []
        for name, position in BASKETS:
            bp_class = u.EditorAssetLibrary.load_blueprint_class('/Game/Systems/Interaction/Hiding/BP_HideBasket')
            basket = spawn(bp_class, 'Basket_' + name, position, 90.)
            body = spawn(u.StaticMeshActor, 'Basket_' + name + '_Body', position)
            cloth = spawn(u.SkeletalMeshActor, 'Basket_' + name + '_Cloth', position)
            bc = body.get_component_by_class(u.StaticMeshComponent)
            cc = cloth.get_component_by_class(u.SkeletalMeshComponent)
            bc.set_static_mesh(meshes['body'])
            bc.set_editor_property('override_materials', [])
            bc.set_collision_profile_name('BlockAll')
            bc.set_simulate_physics(False)
            body.tags = [u.Name(OWNER), u.Name('InteriorProp'), u.Name('SoundObstacle')]
            cc.set_skeletal_mesh_asset(meshes['cloth'])
            cc.set_editor_property('override_materials', [])
            no_collision(cc)
            cc.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
            cc.set_editor_property('animation_data', u.SingleAnimationPlayData(
                anim_to_play=animations['AN_Cloth_IdleEmpty'], saved_looping=False, saved_playing=False, saved_position=0., saved_play_rate=1.))
            basket.set_editor_property('ExternalBody', body)
            basket.set_editor_property('ExternalCloth', cc)
            basket.set_editor_property('ClothEnterDirections', [animations['AN_Cloth_Enter_'+d] for d in DIRS])
            basket.set_editor_property('ClothExitDirections', [animations['AN_Cloth_Exit_'+d] for d in DIRS])
            basket.set_editor_property('ClothHiddenAnimation', animations['AN_Cloth_IdleHidden'])
            basket.set_editor_property('OpenDirectionLocal', u.Vector(0,-1,0))
            for component in basket.get_components_by_class(u.MeshComponent):
                component.set_visibility(False, False)
                component.set_hidden_in_game(True, False)
                no_collision(component)
                if isinstance(component, u.StaticMeshComponent):
                    component.set_static_mesh(None)
                elif isinstance(component, u.SkeletalMeshComponent):
                    component.set_skeletal_mesh_asset(None)
                    component.set_component_tick_enabled(False)
            anchor = next(c for c in basket.get_components_by_class(u.SceneComponent) if c.get_name() == 'HiddenPoint')
            anchor.set_relative_location(u.Vector(0,0,26.25), False, False)
            basket_trios.append((basket, body, cloth, anchor))
        # Small altar decoration only; no altar structural walls, E3 or P2 edits.
        # Copy the existing calibrated/cutaway MIs and bind to the actual back wall
        # CPD group, rather than retaining the source exhibition wall's bounds.
        walls = [a for a in before if a.get_actor_label().startswith('S3_Wall_')]
        def wall_distance(actor):
            p,e = actor.get_actor_bounds(False,False)
            return max(abs(p.x-BANNER[0])-e.x,0.)**2 + max(abs(p.y-BANNER[1])-e.y,0.)**2
        nearest_wall = min(walls, key=wall_distance)
        wall_component = nearest_wall.get_component_by_class(u.StaticMeshComponent)
        wall_cpd = list(wall_component.get_editor_property('custom_primitive_data').get_editor_property('data'))
        assert len(wall_cpd) >= 24
        for suffix in ('Banner2', 'BannerHanger2'):
            source = labels['S3_Gothic_Exhibition_' + suffix]
            actor = own(actor_subsystem.duplicate_actor(source, world, u.Vector()), 'Control_' + suffix)
            actor.set_actor_location_and_rotation(u.Vector(*BANNER), u.Rotator(yaw=180.), False, True)
            component = actor.get_component_by_class(u.StaticMeshComponent)
            no_collision(component)
            component.set_default_custom_primitive_data_vector4(16, u.Vector4(*wall_cpd[16:20]))
            component.set_default_custom_primitive_data_vector4(20, u.Vector4(*wall_cpd[20:24]))
        # Reuse the calibrated wax/iron/flame slot bindings without the wall-group
        # cutaway wrapper; tiny tabletop props do not need architecture cutaway.
        source = labels['S3_Gothic_ControlRoom_Sconce19'].get_component_by_class(u.StaticMeshComponent)
        materials = {}
        for i, slot in enumerate(source.static_mesh.get_editor_property('static_materials')):
            original = slot.get_editor_property('material_interface')
            assigned = source.get_material(i)
            unwrapped = u.EditorAssetLibrary.get_metadata_tag(assigned, 'Stage3ReadabilitySource')
            materials[original.get_name().replace('_Occlusion','')] = load(unwrapped) if unwrapped else assigned
        for name, position in (('SM_S3_LightCandle', CANDLE), ('SM_S3_LightFlame', FLAME)):
            actor = spawn(u.StaticMeshActor, 'Warehouse_' + name, position)
            component = actor.get_component_by_class(u.StaticMeshComponent)
            mesh = load('/Game/Environment/Stage3/FinalGuard/Meshes/' + name)
            component.set_static_mesh(mesh)
            for i, slot in enumerate(mesh.get_editor_property('static_materials')):
                original = slot.get_editor_property('material_interface')
                component.set_material(i, materials[original.get_name().replace('_Occlusion','')])
            no_collision(component)
        u.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
        # Check each basket including the newly added enemy and the other baskets.
        floor_actors = [a for a in before if 'SoundFloor' in [str(tag) for tag in a.tags]]
        for trio in basket_trios:
            basket, body, cloth, anchor = trio
            center, extent = body.get_actor_bounds(False, False)
            overlaps = u.SystemLibrary.box_overlap_components(world, center, extent, object_types,
                u.PrimitiveComponent, [cat, basket, body, cloth] + floor_actors) or []
            body_blockers = [c.get_path_name() for c in overlaps
                if c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN) == u.CollisionResponseType.ECR_BLOCK]
            assert not body_blockers, ('Basket body overlaps existing blocking geometry', body.get_actor_label(), body_blockers)
            result = basket_geometry(*trio)
            result['body_blockers'] = body_blockers
            report['baskets'].append(result)
            assert result['passed'], ('Basket has insufficient safe approach/exit', result)
        blocking_capsule = enemy.get_editor_property('BlockingCapsule')
        blockers = u.SystemLibrary.capsule_overlap_components(world, blocking_capsule.get_world_location(),
            blocking_capsule.get_scaled_capsule_radius(), blocking_capsule.get_scaled_capsule_half_height(),
            object_types, u.PrimitiveComponent, [enemy, cat]) or []
        blockers = [c.get_path_name() for c in blockers if c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN) == u.CollisionResponseType.ECR_BLOCK]
        report['new_enemy_blockers'] = blockers
        assert not blockers, ('New candle overlaps blocking geometry', blockers)
        report['created'] = [{'actor': a.get_actor_label(), 'path': a.get_path_name(),
                              'location': vec(a.get_actor_location())} for a in created]
        assert len(created) == 17
        assert all(a.get_actor_transform().export_text() == before_transforms[a.get_path_name()] for a in before)
        assert hashlib.sha256(disk_map.read_bytes()).hexdigest() == map_hash, 'Map was saved during preparation'
        report['existing_actor_transforms_preserved'] = True
        report['map_bytes_preserved'] = True
        report['success'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        for actor in reversed(created):
            actor_subsystem.destroy_actor(actor)
        report['rolled_back_new_actors'] = True
    (OUT/'apply_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    return report


if __name__ == '__main__':
    raise RuntimeError('Root must import and call apply(); no automatic Unreal mutation')
