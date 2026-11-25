"""Move only the existing Warehouse basket trio; root invokes apply() and saves.

Import is inert. No map/package save, shared asset/material edits or interaction
settings changes. Preserve the existing regression routes. Physical preflight
uses actual capsule dimensions and response-equivalent registered profiles.
Root must rebuild SoundGrid with build_grid() and run the unchanged full game
regression plus all sixteen native basket input cases after saving.
"""
import hashlib
import json
import math
import os
import traceback
from pathlib import Path

OLD = (605., -1345., 0.)
TARGET = (605., -1410., 0.)
LABEL = 'S3_Placement_Basket_Warehouse'
ROUTES = (
    ('WarehouseBenchFront', (610., -1320.), (930., -1320.)),
    ('WarehouseNorthOpening', (1000., -1320.), (1000., -1660.)),
)


def apply():
    import unreal as u
    root = Path(u.Paths.project_dir()).resolve()
    suffix = os.environ.get('CATRUN_STAGE3_WAREHOUSE_RELOCATE_PASS', '01')
    assert suffix.replace('_', '').isalnum()
    out = root / 'Saved/Stage3PlacementRevision20261125' / ('WarehouseRelocate' + suffix + '.json')
    assert not out.exists(), 'Keep prior relocation evidence; use a fresh pass'
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3' and not ed.get_game_world()
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    by_label = {a.get_actor_label(): a for a in actors}
    trio = [by_label[LABEL + suffix] for suffix in ('', '_Body', '_Cloth')]
    basket, body, cloth_actor = trio
    body_component = body.get_component_by_class(u.StaticMeshComponent)
    cloth = cloth_actor.get_component_by_class(u.SkeletalMeshComponent)
    assert basket.get_editor_property('ExternalBody') == body
    assert basket.get_editor_property('ExternalCloth') == cloth
    assert all((a.get_actor_location()-u.Vector(*OLD)).length() < .05 for a in trio), 'Unexpected existing basket location'
    cat = by_label['S3_Player']
    armor = by_label['S3_Armor_ControlPatrol']
    grid = by_label['S3_SoundGrid']
    floor_z = grid.get_floor_z()
    action = cat.get_component_by_class(u.CatrunBasketInteractionComponent)
    before = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
    original = {a: a.get_actor_transform() for a in trio}
    other_baskets = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors
                     if a.get_actor_label().startswith('S3_Placement_Basket_') and a not in trio}
    mesh_paths = [body_component.static_mesh.get_path_name(), cloth.get_skinned_asset().get_path_name()]
    material_paths = [[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]
                      for c in (body_component, cloth)]
    map_path = root / 'Content/Maps/Stage3.umap'
    map_hash = hashlib.sha256(map_path.read_bytes()).hexdigest()
    r = {'success': False, 'packages_saved': False, 'old_world_cm': OLD, 'target_world_cm': TARGET,
         'preserved_regression_routes': ROUTES, 'checks': [], 'before': {}, 'after': {},
         'requires_root': ['SoundGrid.build_grid() after relocation, before root save.',
                           'Unchanged WarehouseBenchFront and WarehouseNorthOpening native walk regression.',
                           'Full native basket RuntimeQA04: all four Warehouse WASD cases plus other twelve cases; do not change input/interaction ranges.'],
         'scope': 'Existing Warehouse trio only. Read-only static physical checks are not native interaction/playthrough proof.'}
    moved = False
    def vec(v):
        return [v.x, v.y, v.z]
    def check(name, passed, detail=None):
        r['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        assert passed, (name, detail)
    def bounds(actor):
        c, e = actor.get_actor_bounds(False, False)
        return {'min': vec(c-e), 'max': vec(c+e), 'transform': actor.get_actor_transform().export_text()}
    def hit_data(hit):
        if not hit:
            return None
        d = hit.to_dict()
        return {'actor': d['hit_actor'].get_actor_label() if d['hit_actor'] else None,
                'blocking': d['blocking_hit'], 'initial_overlap': d['initial_overlap'],
                'impact': vec(d['impact_point']), 'location': vec(d['location']), 'normal': vec(d['impact_normal'])}
    query_profiles = {}
    def shape(actor):
        c = actor.get_component_by_class(u.CapsuleComponent)
        return c, c.get_scaled_capsule_radius(), c.get_scaled_capsule_half_height()
    def profile(actor):
        if actor in query_profiles:
            return query_profiles[actor]
        cap, _, _ = shape(actor)
        name = str(cap.get_collision_profile_name())
        row = {'actual': name, 'object_type': str(cap.get_collision_object_type())}
        if name in ('Custom', '', 'None', 'NoCollision'):
            template = u.get_default_object(u.Character).get_editor_property('CapsuleComponent')
            channels = {c.get_collision_object_type() for a in actors for c in a.get_components_by_class(u.PrimitiveComponent)}
            actual = {str(c): str(cap.get_collision_response_to_channel(c)) for c in channels}
            expected = {str(c): str(template.get_collision_response_to_channel(c)) for c in channels}
            row.update(actual_responses=actual, template_responses=expected)
            check('Custom profile response equivalence', actual == expected and cap.get_collision_object_type() == template.get_collision_object_type(), row)
            name = str(template.get_collision_profile_name())
        check('Registered query profile exists', name not in ('Custom', '', 'None', 'NoCollision'), name)
        row['query_profile'] = name
        r.setdefault('query_profiles', {})[actor.get_actor_label()] = row
        query_profiles[actor] = name
        return name
    def sweep(actor, start, end, ignore):
        _, radius, half = shape(actor)
        return u.SystemLibrary.capsule_trace_single_by_profile(world, start, end, radius, half,
                   profile(actor), False, ignore, u.DrawDebugTrace.NONE, False)
    def support(actor, reference, ignore, above, below, detail, ground_only=True):
        _, radius, half = shape(actor)
        center = reference + u.Vector(0, 0, half)
        hit = sweep(actor, center+u.Vector(0,0,above), center-u.Vector(0,0,below), ignore)
        detail.update(probe_up=above, probe_down=below, hit=hit_data(hit))
        if not hit:
            return None
        d = hit.to_dict()
        if (not d['blocking_hit'] or d['initial_overlap'] or d['impact_normal'].z < .65
                or isinstance(d['hit_actor'], u.Pawn)
                or math.hypot(d['impact_point'].x-d['location'].x,d['impact_point'].y-d['location'].y) > max(0.,radius-.15)
                or not center.z-below-.01 <= d['location'].z <= center.z+above+.01
                or ground_only and abs(d['impact_point'].z-floor_z)>2.):
            return None
        return u.Vector(reference.x, reference.y, d['location'].z+2.)
    def route_probes():
        rows = []
        for name, a, b in ROUTES:
            for pawn in (cat, armor):
                _, radius, half = shape(pawn)
                z = floor_z+half+2.2
                start, end = u.Vector(*a,z), u.Vector(*b,z)
                forward, backward = sweep(pawn,start,end,[pawn]), sweep(pawn,end,start,[pawn])
                floors=[]
                for i in range(5):
                    xy = (a[0]+(b[0]-a[0])*i/4., a[1]+(b[1]-a[1])*i/4.)
                    detail={};point=support(pawn,u.Vector(*xy,floor_z),[pawn],50.,100.,detail)
                    floors.append({'xy':xy,'supported':point is not None,'detail':detail})
                rows.append({'route':name,'pawn':pawn.get_actor_label(),'radius_cm':radius,'half_height_cm':half,
                             'start':vec(start),'end':vec(end),'forward':hit_data(forward),'backward':hit_data(backward),
                             'floor_samples':floors,'clear_both_directions':not forward and not backward and all(x['supported'] for x in floors)})
        return rows
    try:
        r['before']={a.get_actor_label():bounds(a) for a in trio}
        r['before_route_capsules']=route_probes()
        r['material_and_cpd_checks']=[]
        for c in (body_component,cloth):
            data=list(c.get_editor_property('custom_primitive_data').get_editor_property('data'))
            sources=[u.EditorAssetLibrary.get_metadata_tag(c.get_material(i),'Stage3ReadabilitySource') for i in range(c.get_num_materials())]
            # These are original shared basket materials, outside occlusion.py's
            # architecture/attached-decor selection. No static bounds binding is
            # expected; fail before moving if a future cutaway wrapper appears.
            check('Basket has no unhandled cutaway bounds binding', not any(sources) and not any(abs(x)>.001 for x in data[16:24]),
                  {'component':c.get_path_name(),'readability_sources':sources,'cpd':data})
            r['material_and_cpd_checks'].append({'component':c.get_path_name(),'cpd':data,'readability_sources':sources,
                'decision':'No GroupCenter/GroupExtent binding; no CPD/MPC update or global occlusion rebuild required.'})
        delta=u.Vector(*TARGET)-u.Vector(*OLD)
        moved=True
        for a in trio:
            a.set_actor_location(a.get_actor_location()+delta,False,True)
        u.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        r['after']={a.get_actor_label():bounds(a) for a in trio}
        r['after_route_capsules']=route_probes()
        for row in r['after_route_capsules']:
            check(row['route']+' '+row['pawn']+' actual capsule clear both directions',row['clear_both_directions'],row)
        floor_actors=[a for a in actors if 'SoundFloor' in map(str,a.tags)]
        center,extent=body.get_actor_bounds(False,False)
        types=[getattr(u.ObjectTypeQuery,'OBJECT_TYPE_QUERY'+str(i)) for i in range(1,7)]
        overlaps=u.SystemLibrary.box_overlap_components(world,center,extent,types,u.PrimitiveComponent,trio+floor_actors) or []
        blockers=[c.get_path_name() for c in overlaps if c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_BLOCK]
        check('Moved basket outer footprint does not overlap furniture/walls/pawns',not blockers,blockers)
        # Preserve native settings; query the same eight directions at the
        # unchanged camera yaw. Native interaction remains the later authority.
        camera=by_label['S3_FollowCamera'].get_component_by_class(u.CameraComponent)
        yaw=camera.get_world_rotation().yaw
        origin=next(c for c in basket.get_components_by_class(u.SceneComponent) if c.get_name()=='HiddenPoint').get_world_location()
        entry_distance=float(action.get_editor_property('EntryDistance'))
        exit_distance=float(action.get_editor_property('ExitDistance'))
        interaction_range=float(action.get_editor_property('InteractionRange'))
        check('Native obstacle channel remains Visibility',action.get_editor_property('ObstacleChannel')==u.CollisionChannel.ECC_VISIBILITY)
        front=cloth.get_socket_location('Edge_F')-cloth.get_world_location();front_yaw=math.atan2(front.y,front.x)
        check('Eight entry/exit clips preserved',len(basket.get_editor_property('ClothEnterDirections'))==8 and len(basket.get_editor_property('ClothExitDirections'))==8)
        hidden_detail={};hidden=support(cat,origin,[cat,basket,body],50.,100.,hidden_detail)
        check('Hidden-origin ground support',hidden is not None,hidden_detail)
        r['native_settings_read_only']={'entry_distance':entry_distance,'exit_distance':exit_distance,'interaction_range_3d':interaction_range,'camera_yaw':yaw}
        r['directions']=[]
        for i in range(8):
            angle=math.radians(yaw+i*45.);dx,dy=math.cos(angle),math.sin(angle)
            extra=24.*abs(math.cos(angle-front_yaw)*math.sin(angle-front_yaw))
            row={'octant':i,'camera_key':{0:'W',2:'D',4:'S',6:'A'}.get(i),'direction':[dx,dy],'entry_support':{},'approach_support':{},'exit_support':{}}
            entry=support(cat,origin+u.Vector(dx*(entry_distance+extra),dy*(entry_distance+extra),0),[cat],0.,50.,row['entry_support'])
            approach=support(cat,origin+u.Vector(dx*103,dy*103,0),[cat],0.,50.,row['approach_support'])
            exit_pos=support(cat,origin+u.Vector(dx*(exit_distance+extra),dy*(exit_distance+extra),0),[cat,basket,body],50.,100.,row['exit_support'])
            entry_hits=[]
            if entry is not None and approach is not None:
                entry_hits=[sweep(cat,approach,entry,[cat]),sweep(cat,entry,entry,[cat]),
                            sweep(cat,entry,u.Vector(origin.x,origin.y,entry.z),[cat,basket,body]),
                            u.SystemLibrary.line_trace_single(world,entry,origin,u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[cat,basket,body],u.DrawDebugTrace.NONE,False)]
            row['entry_safe']=bool(entry is not None and approach is not None and (approach-origin).length()<interaction_range and not any(entry_hits))
            row['entry_hits']=[hit_data(x) for x in entry_hits]
            row['exit_transit']=hit_data(sweep(cat,hidden,exit_pos,[cat,basket,body])) if exit_pos is not None else None
            row['exit_restore']=hit_data(sweep(cat,exit_pos,exit_pos,[cat])) if exit_pos is not None else None
            row['ground_exit_safe']=bool(exit_pos is not None and not row['exit_transit'] and not row['exit_restore'])
            row['entry_point']=vec(entry) if entry is not None else None
            row['approach']=vec(approach) if approach is not None else None
            row['exit_landing']=vec(exit_pos) if exit_pos is not None else None
            r['directions'].append(row)
        check('At least one valid ground entry direction',any(x['entry_safe'] for x in r['directions']))
        check('At least two unchanged camera WASD ground exits',sum(x['ground_exit_safe'] and x['camera_key'] is not None for x in r['directions'])>=2,r['directions'])
        check('Basket links and shared mesh paths preserved',basket.get_editor_property('ExternalBody')==body and basket.get_editor_property('ExternalCloth')==cloth and mesh_paths==[body_component.static_mesh.get_path_name(),cloth.get_skinned_asset().get_path_name()])
        check('Material slots preserved',material_paths==[[c.get_material(i).get_path_name() for i in range(c.get_num_materials())] for c in (body_component,cloth)])
        check('Other three baskets untouched',all(a.get_actor_transform().export_text()==other_baskets[a.get_path_name()] for a in actors if a.get_path_name() in other_baskets))
        check('All other actor transforms untouched',all(a.get_actor_transform().export_text()==before[a.get_path_name()] for a in actors if a not in trio))
        check('Map bytes remain unsaved',hashlib.sha256(map_path.read_bytes()).hexdigest()==map_hash)
        r['success']=True
    except Exception:
        r['error']=traceback.format_exc()
        if moved:
            for actor,transform in original.items():actor.set_actor_transform(transform,False,True)
            r['rolled_back_trio']=True
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf8')
    return r


if __name__=='__main__':
    raise RuntimeError('Import and call apply() from the root writer; no automatic Unreal operation.')
