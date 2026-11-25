"""Saved Stage3 placement QA: real F/WASD basket inputs and native Annex travel.

Inert import; root calls main() in an isolated editor already on saved Stage3.
No level load, actor spawn, package save, forced basket state, or mid-case pawn
teleport. Each independent case permits one collision-checked initial staging.
NPCs run first for observation, then unrelated NPC tick/collision is temporarily
disabled for deterministic geometry tests. Thus this is not full combat QA.
Native armor uses its existing PatrolPoints and SoundGrid A*/CharacterMovement.
The six actual S3_Wall_Altar_* actors, baskets and saved collision stay intact.
"""
import hashlib
import json
import math
import os
import time
import traceback
from pathlib import Path

KEYS = ('W', 'A', 'S', 'D')
DIRS = ('F', 'FR', 'R', 'BR', 'B', 'BL', 'L', 'FL')
ZONES = ('Lobby', 'Exhibition', 'Warehouse', 'ControlAnnex')
ORIGINAL_CANDLES = ('S3_Candle_Exhibition', 'S3_Candle_WarehouseNorth',
                    'S3_Candle_WarehouseSouth', 'S3_Candle_GateLeft', 'S3_Candle_GateRight')
NEW_CANDLE = 'S3_Placement_Candle_ExhibitionNorth'
CAT_ROUTE = ((-200., -2220.), (-200., -2045.), (50., -2045.), (50., -2220.),
             (50., -2045.), (-200., -2045.), (-200., -2220.))
ARMOR_ENDPOINTS = (CAT_ROUTE[0], CAT_ROUTE[3])


def main():
    import unreal as u
    global RUN
    RUN = RuntimeQA(u)
    RUN.start()
    return RUN.report


class RuntimeQA:
    def __init__(self, u):
        self.u = u
        self.gs, self.sl = u.GameplayStatics, u.SystemLibrary
        self.ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        self.le = u.get_editor_subsystem(u.LevelEditorSubsystem)
        self.root = Path(u.Paths.project_dir()).resolve()
        suffix = os.environ.get('CATRUN_STAGE3_PLACEMENT_QA_PASS', '03')
        assert suffix.replace('_', '').isalnum()
        self.out = self.root / 'Saved/Stage3PlacementRevision20261125' / ('RuntimeQA' + suffix + '.json')
        assert not self.out.exists(), 'Preserve prior runtime evidence: ' + str(self.out)
        self.map_path = self.root / 'Content/Maps/Stage3.umap'
        self.map_hash = hashlib.sha256(self.map_path.read_bytes()).hexdigest()
        self.report = {'scope': __doc__, 'success': False, 'execution_complete': False,
                       'packages_saved': False, 'phase': 'created', 'checks': [],
                       'basket_cases': [], 'initial_stagings': [], 'enemy_samples': [],
                       'cat_route': {'waypoints': CAT_ROUTE, 'visits': [], 'samples': []},
                       'armor_route': {'endpoints': ARMOR_ENDPOINTS, 'visits': [], 'samples': []},
                       'limitations': ['Unrelated NPCs frozen during isolated basket and corridor cases; live combat difficulty is not certified.',
                                       'Enemy observation proves tick enabled, active animation and collision; no injected native Tick counter.',
                                       'Armor native path may complete its in-flight leg before measured endpoint visits begin.']}
        self.started = time.monotonic()
        self.world = self.cat = self.action = self.pc = None
        self.npc_restore = []
        self.patrol_restore = []
        self.armor = None
        self.capture_setting = None
        self.held = set()
        self.handle = None
        self.release_f = None
        self.in_tick = False
        self.pending_error = None
        self.trace_profiles = {}

    @staticmethod
    def v(p):
        return [float(p.x), float(p.y), float(p.z)]

    def persist(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(json.dumps(self.report, indent=2, ensure_ascii=False), encoding='utf8')

    def check(self, name, passed, detail=None):
        self.report['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        self.persist()
        assert passed, name + ': ' + str(detail)

    def phase(self, name):
        self.report['phase'] = name
        self.changed = time.monotonic()
        self.persist()

    def start(self):
        assert '-SaveToUserDir' in self.sl.get_command_line(), 'Run only in isolated editor process'
        world = self.ed.get_editor_world()
        assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3'
        assert not self.ed.get_game_world(), 'Start before PIE'
        actors = self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors()
        self.editor_transforms = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
        self.original_candle_authored = {a.get_actor_label(): {
            'class': a.get_class().get_path_name(),
            'patrol_enabled': bool(a.get_editor_property('bPatrolEnabled')),
            'patrol_points': [p.get_actor_label() for p in a.get_editor_property('PatrolPoints')],
            'mesh': a.get_editor_property('Body').get_skinned_asset().get_path_name()}
            for a in actors if a.get_actor_label() in ORIGINAL_CANDLES}
        self.check('Saved original five candle identities exist', len(self.original_candle_authored) == 5)
        self.handle = self.u.register_slate_post_tick_callback(self.tick)
        self.phase('startup')
        try:
            self.le.editor_request_begin_play()
        except Exception:
            self.finish(traceback.format_exc())

    def key(self, name, down):
        self.sl.execute_console_command(self.world, 'Catrun.Basket.TestKey ' + name + (' down' if down else ' up'))
        if down:
            self.held.add(name)
        else:
            self.held.discard(name)

    def release(self):
        if self.world:
            for k in KEYS + ('F',):
                self.key(k, False)
        self.release_f = None

    def interact(self):
        self.key('F', True)
        self.release_f = time.monotonic() + .08

    def bp(self):
        return str(self.action.get_editor_property('BasketPhase')).split('.')[-1].split(':')[0]

    def axes(self):
        yaw = self.gs.get_player_camera_manager(self.pc, 0).get_camera_rotation().yaw
        r = math.radians(yaw)
        return yaw, {'W': (math.cos(r), math.sin(r)), 'S': (-math.cos(r), -math.sin(r)),
                     'D': (-math.sin(r), math.cos(r)), 'A': (math.sin(r), -math.cos(r))}

    def cloth(self):
        return self.basket.get_editor_property('ExternalCloth')

    def animation(self, mesh):
        anim = mesh.get_anim_instance()
        return anim.get_animation_asset().get_name() if isinstance(anim, self.u.AnimSingleNodeInstance) and anim.get_animation_asset() else None

    def clip(self, direction, kind):
        cloth = self.cloth()
        origin = cloth.get_world_location()
        f, r = cloth.get_socket_location('Edge_F') - origin, cloth.get_socket_location('Edge_R') - origin
        angle = math.atan2(f.x*direction.y - f.y*direction.x, f.x*direction.x + f.y*direction.y)
        if f.x*r.y - f.y*r.x < 0:
            angle = -angle
        return 'AN_Cloth_' + kind + '_' + DIRS[int(math.floor(math.degrees(angle)/45.+.5)) % 8]

    def sample_animation(self):
        cloth = self.cloth()
        return {'game': self.gs.get_time_seconds(self.world), 'position': self.v(self.cat.get_actor_location()),
                'cat_time': self.mesh.get_position(), 'cloth_time': cloth.get_position(),
                'cat_animation': self.animation(self.mesh), 'cloth_animation': self.animation(cloth),
                'cloth_tick': cloth.is_component_tick_enabled()}

    def shape(self, actor):
        cap = actor.get_component_by_class(self.u.CapsuleComponent)
        assert cap
        return cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()

    def trace_profile(self, actor):
        """Read-only profile resolution; never alter a live capsule or CDO.

        Native TestEntry supplies the capsule's object type AND response table.
        Kismet's profile sweep cannot express an unregistered Custom name. Use
        the registered native Character CDO profile only after proving identical
        responses for every object type present in this actual runtime world.
        No fixture spawns collision geometry; native can_enter/F is still the
        authority after staging. An unrepresentable custom table fails closed.
        """
        path = actor.get_path_name()
        if path in self.trace_profiles:
            return self.trace_profiles[path]
        cap = actor.get_component_by_class(self.u.CapsuleComponent)
        actual_name = str(cap.get_collision_profile_name())
        object_type = cap.get_collision_object_type()
        rotation = cap.get_world_rotation()
        assert abs(rotation.pitch) < .01 and abs(rotation.roll) < .01, 'Capsule sweep requires upright native capsule'
        channels = {c.get_collision_object_type() for a in self.gs.get_all_actors_of_class(self.world, self.u.Actor)
                    for c in a.get_components_by_class(self.u.PrimitiveComponent)}
        channels.add(object_type)
        row = {'actual_profile': actual_name, 'native_object_type': str(object_type),
               'responses_for_world_object_types': {str(c): str(cap.get_collision_response_to_channel(c)) for c in channels}}
        if actual_name not in ('Custom', 'None', '', 'NoCollision'):
            selected = actual_name
            row['selection'] = 'Actual registered capsule profile'
        else:
            template_actor = self.u.get_default_object(self.u.Character)
            template = template_actor.get_editor_property('CapsuleComponent')
            assert template, 'Native Character CDO capsule unavailable'
            selected = str(template.get_collision_profile_name())
            row['template_profile'] = selected
            row['template_object_type'] = str(template.get_collision_object_type())
            row['template_responses_for_world_object_types'] = {
                str(c): str(template.get_collision_response_to_channel(c)) for c in channels}
            equivalent = (object_type == template.get_collision_object_type()
                and row['responses_for_world_object_types'] == row['template_responses_for_world_object_types']
                and selected not in ('Custom', 'None', '', 'NoCollision'))
            self.report.setdefault('collision_query_profiles', {})[actor.get_actor_label()] = row
            self.check('Custom capsule responses exactly match registered query template in actual world', equivalent, row)
            row['selection'] = 'CDO registered profile only after matching actual object type and all present-world responses'
        row['query_profile'] = selected
        self.report.setdefault('collision_query_profiles', {})[actor.get_actor_label()] = row
        self.trace_profiles[path] = selected
        self.persist()
        return selected

    def supported(self, reference, actor, ignore, above=50., below=100., floor_z=None, detail=None, skin=2.2):
        radius, half = self.shape(actor)
        center = reference + self.u.Vector(0, 0, half)
        hit = self.sl.capsule_trace_single_by_profile(self.world, center+self.u.Vector(0,0,above),
            center-self.u.Vector(0,0,below), radius, half, self.trace_profile(actor), False, ignore, self.u.DrawDebugTrace.NONE, False)
        if detail is not None:
            detail.update(probe_up_cm=above, probe_down_cm=below, required_floor_z=floor_z)
        if not hit:
            if detail is not None:
                detail['rejected'] = 'No blocking support'
            return None
        d = hit.to_dict()
        if detail is not None:
            detail.update(support_actor=d['hit_actor'].get_actor_label() if d['hit_actor'] else None,
                          impact_z=d['impact_point'].z, initial_overlap=d['initial_overlap'])
        if not d['blocking_hit'] or d['initial_overlap'] or d['impact_normal'].z < .65 or isinstance(d['hit_actor'], self.u.Pawn):
            if detail is not None:
                detail['rejected'] = 'Invalid blocking support, overlap, slope or pawn'
            return None
        # Match native CatrunGround::FindSupport's support-radius and trace-span
        # rejection. Basket fixtures additionally require the actual map floor,
        # not a raised crate/bench that happens to have a walkable top.
        if (math.hypot(d['impact_point'].x-d['location'].x, d['impact_point'].y-d['location'].y) > max(0., radius-.15)
                or not center.z-below-.01 <= d['location'].z <= center.z+above+.01):
            if detail is not None:
                detail['rejected'] = 'Edge support or outside sweep span'
            return None
        if floor_z is not None and abs(d['impact_point'].z-floor_z) > 2.:
            if detail is not None:
                detail['rejected'] = 'Raised furniture or different floor height'
            return None
        return self.u.Vector(reference.x, reference.y, d['location'].z + skin)

    def sweep(self, start, end, actor, ignore):
        radius, half = self.shape(actor)
        return self.sl.capsule_trace_single_by_profile(self.world, start, end, radius, half,
                    self.trace_profile(actor), False, ignore, self.u.DrawDebugTrace.NONE, False)

    def stage(self, actor, position, case):
        self.check(case + ' initial staging capsule clear', not self.sweep(position, position, actor, [actor]), self.v(position))
        movement = actor.get_component_by_class(self.u.CharacterMovementComponent)
        movement.stop_movement_immediately()
        actor.consume_movement_input_vector()
        before = self.v(actor.get_actor_location())
        actor.set_actor_location(position, False, True)
        self.report['initial_stagings'].append({'case': case, 'actor': actor.get_actor_label(), 'from': before,
                                               'to': self.v(position), 'once_per_independent_case': True})
        self.persist()

    def observe_enemies(self):
        rows = []
        for enemy in self.candles:
            body, cap = enemy.get_editor_property('Body'), enemy.get_editor_property('BlockingCapsule')
            rows.append({'label': enemy.get_actor_label(), 'position': self.v(enemy.get_actor_location()),
                         'actor_tick': enemy.is_actor_tick_enabled(), 'body_tick': body.is_component_tick_enabled(),
                         'actor_collision': enemy.get_actor_enable_collision(), 'capsule_collision': str(cap.get_collision_enabled()),
                         'pawn_response': str(cap.get_collision_response_to_channel(self.u.CollisionChannel.ECC_PAWN)),
                         'animation': self.animation(body), 'animation_position': body.get_position()})
        self.report['enemy_samples'].append({'time': self.gs.get_time_seconds(self.world), 'actors': rows})

    def setup(self):
        self.actors = {a.get_actor_label(): a for a in self.gs.get_all_actors_of_class(self.world, self.u.Actor)}
        self.mesh = self.cat.get_component_by_class(self.u.SkeletalMeshComponent)
        self.original_cat_pos = self.cat.get_actor_location()
        self.candles = list(self.gs.get_all_actors_of_class(self.world, self.u.CatrunCandle))
        self.armors = list(self.gs.get_all_actors_of_class(self.world, self.u.CatrunArmor))
        names = {a.get_actor_label() for a in self.candles}
        self.check('Six candles = original five plus ExhibitionNorth', names == set(ORIGINAL_CANDLES) | {NEW_CANDLE}, sorted(names))
        self.check('Six original armors preserved', len(self.armors) == 6, [a.get_actor_label() for a in self.armors])
        self.check('Actual six B1 altar walls present', len([n for n in self.actors if n.startswith('S3_Wall_Altar_')]) == 6)
        for label, authored in self.original_candle_authored.items():
            a = self.actors[label]
            actual = {'class': a.get_class().get_path_name(), 'patrol_enabled': bool(a.get_editor_property('bPatrolEnabled')),
                      'patrol_points': [p.get_actor_label() for p in a.get_editor_property('PatrolPoints')],
                      'mesh': a.get_editor_property('Body').get_skinned_asset().get_path_name()}
            self.check(label + ' authored identity/patrol/mesh preserved in PIE', actual == authored, actual)
        self.baskets = {z: self.actors['S3_Placement_Basket_' + z] for z in ZONES}
        self.check('Four functional basket actors', len(self.gs.get_all_actors_of_class(self.world, self.u.CatrunHideBasket)) == 4)
        self.report['basket_locations'] = {z: self.v(a.get_actor_location()) for z, a in self.baskets.items()}
        self.observe_enemies()
        self.phase('observe_enemies')

    def isolate(self):
        self.observe_enemies()
        first = {r['label']: r for r in self.report['enemy_samples'][0]['actors']}
        for r in self.report['enemy_samples'][-1]['actors']:
            self.check(r['label'] + ' active tick/collision', r['actor_tick'] and r['body_tick'] and r['actor_collision']
                       and 'NO_COLLISION' not in r['capsule_collision'] and 'BLOCK' in r['pawn_response'], r)
            self.check(r['label'] + ' real animation advanced', r['animation'] is not None and
                       abs(r['animation_position']-first[r['label']]['animation_position']) > .001, r)
        for actor in self.candles + self.armors:
            self.npc_restore.append((actor, actor.is_actor_tick_enabled(), actor.get_actor_enable_collision()))
            actor.set_actor_tick_enabled(False)
            actor.set_actor_enable_collision(False)
        self.capture_setting = self.u.CatrunUserSettings.is_no_armor_capture_enabled()
        self.u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        self.queue = [(zone, key) for zone in ZONES for key in KEYS]
        self.case_index = 0
        self.begin_basket()

    def begin_basket(self):
        if self.case_index == len(self.queue):
            self.begin_cat()
            return
        zone, key = self.queue[self.case_index]
        self.release()
        self.check('Basket case begins OUTSIDE', self.bp() == 'OUTSIDE')
        self.basket = self.baskets[zone]
        self.case = {'basket': zone, 'key': key, 'entry_samples': [], 'exit_samples': [], 'fallbacks': []}
        self.report['basket_cases'].append(self.case)
        self.trace_profiles.clear()  # Re-read actual response tables per independent case.
        origin = self.basket.get_hidden_location()
        body = self.basket.get_editor_property('ExternalBody')
        floor_z = float(self.actors['S3_SoundGrid'].get_floor_z())
        interaction_range = float(self.action.get_editor_property('InteractionRange'))
        entry_distance = float(self.action.get_editor_property('EntryDistance'))
        self.check('Basket query uses native Visibility obstacle channel',
                   self.action.get_editor_property('ObstacleChannel') == self.u.CollisionChannel.ECC_VISIBILITY)
        self.case['query_profile'] = self.trace_profile(self.cat)
        self.check('Placed basket retains eight directional entry clips',
                   len(self.basket.get_editor_property('ClothEnterDirections')) == 8)
        # IdleEmpty leaves the imported Edge_F reference direction unchanged.
        front = self.cloth().get_socket_location('Edge_F') - self.cloth().get_world_location()
        front_yaw = math.atan2(front.y, front.x)
        self.case['native_entry_contract'] = {'interaction_range_3d_cm': interaction_range,
            'entry_distance_cm': entry_distance, 'floor_z': floor_z, 'probe_up_cm': 0., 'probe_down_cm': 50.,
            'source': 'CatrunBasketInteractionComponent::FindEntryCandidate/TestEntry; CatrunGround::FindSupport',
            'note': 'Read-only candidate filtering; actual can_enter_nearby_basket and F remain mandatory after the sole staging.'}
        yaw, _ = self.axes()
        candidates = []
        selected = None
        for i in range(8):
            r = math.radians(yaw + i*45.)
            dx, dy = math.cos(r), math.sin(r)
            distance = entry_distance + 24.*abs(math.cos(r-front_yaw)*math.sin(r-front_yaw))
            row = {'octant': i, 'approach_support': {}, 'entry_support': {}, 'rejections': []}
            approach = self.supported(origin+self.u.Vector(dx*103.,dy*103.,0), self.cat, [self.cat],
                                      above=0., below=50., floor_z=floor_z, detail=row['approach_support'])
            entry = self.supported(origin+self.u.Vector(dx*distance,dy*distance,0), self.cat, [self.cat],
                                   above=0., below=50., floor_z=floor_z, detail=row['entry_support'], skin=2.)
            if approach is None:
                row['rejections'].append('No ground-only approach support')
            if entry is None:
                row['rejections'].append('Native entry point has no ground-only support')
            if approach is not None:
                row['distance_to_hidden_3d_cm'] = (approach-origin).length()
                if row['distance_to_hidden_3d_cm'] >= interaction_range:
                    row['rejections'].append('Outside native 3D interaction range')
                if self.sweep(approach, approach, self.cat, [self.cat]):
                    row['rejections'].append('Approach capsule overlaps blocker')
            if entry is not None:
                if not origin.z-50.-.01 <= row['entry_support']['impact_z'] <= origin.z+.01:
                    row['rejections'].append('Entry support violates native height interval')
                if self.sweep(entry, entry, self.cat, [self.cat]):
                    row['rejections'].append('Entry capsule overlaps blocker')
                # Native TestEntry ignores the shell only during the deliberate
                # jump. Furniture/walls must block its entire inner transit.
                inner = self.u.Vector(origin.x, origin.y, entry.z)
                if self.sweep(entry, inner, self.cat, [self.cat, self.basket, body]):
                    row['rejections'].append('Inner transit capsule blocked')
                sight = self.sl.line_trace_single(self.world, entry, origin, self.u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                            False, [self.cat, self.basket, body], self.u.DrawDebugTrace.NONE, False)
                if sight:
                    row['rejections'].append('Native entry visibility blocked')
            if approach is not None and entry is not None and self.sweep(approach, entry, self.cat, [self.cat]):
                row['rejections'].append('Approach-to-entry capsule blocked')
            safe = not row['rejections']
            row.update(safe=safe, approach=self.v(approach) if approach else None, entry=self.v(entry) if entry else None)
            candidates.append(row)
            if safe and selected is None:
                selected = approach
                self.case['selected_approach_octant'] = i
        self.case['read_only_approach_queries'] = candidates
        self.check(zone + ' safe approach before sole staging', selected is not None, candidates)
        self.stage(self.cat, selected, zone + '_' + key)
        self.phase('basket_settle')

    def select(self, key, fallback=False):
        self.case['selected_key'] = key
        self.case['select_is_fallback'] = fallback
        self.case['camera_yaw'], axes = self.axes()
        self.case['expected_direction'] = [*axes[key], 0.]
        self.key(key, True)
        self.phase('select_exit')

    def fallback(self):
        remaining = [k for k in KEYS if k not in self.case['fallbacks']]
        self.check('A camera-relative single key can safely exit', bool(remaining), self.case['fallbacks'])
        k = remaining[0]
        self.case['fallbacks'].append(k)
        self.select(k, True)

    def begin_cat(self):
        self.release()
        reference = self.u.Vector(*CAT_ROUTE[0], 0.)
        p = self.supported(reference, self.cat, [self.cat])
        self.check('Annex cat initial floor support', p is not None)
        self.stage(self.cat, p, 'AnnexCatRoundTrip')
        self.cat_index = 1
        self.report['cat_route']['visits'].append({'index': 0, 'position': self.v(p)})
        self.phase('cat_route')

    def walk_cat(self):
        row = self.report['cat_route']
        p = self.cat.get_actor_location()
        target = CAT_ROUTE[self.cat_index]
        dx, dy = target[0]-p.x, target[1]-p.y
        now = self.gs.get_time_seconds(self.world)
        if not row['samples'] or now-row['samples'][-1]['time'] >= .05:
            row['samples'].append({'time': now, 'position': self.v(p), 'keys': sorted(self.held),
                                   'target': self.cat_index, 'collision': self.cat.get_actor_enable_collision()})
        assert self.cat.get_actor_enable_collision() and self.bp() == 'OUTSIDE'
        if math.hypot(dx, dy) <= 12.:
            self.release()
            row['visits'].append({'index': self.cat_index, 'position': self.v(p), 'time': now})
            self.cat_index += 1
            self.persist()
            if self.cat_index == len(CAT_ROUTE):
                self.check('Actual-key cat Annex round trip completed', len(row['visits']) == 7)
                self.begin_armor()
                return
            return
        _, axes = self.axes()
        desired = {k for k, v in axes.items() if dx*v[0]+dy*v[1] > 6.}
        for key in KEYS:
            if (key in desired) != (key in self.held):
                self.key(key, key in desired)

    def begin_armor(self):
        self.release()
        self.armor = self.actors['S3_Armor_ControlPatrol']
        points = list(self.armor.get_editor_property('PatrolPoints'))
        self.check('Native ControlPatrol retains four targets', len(points) == 4)
        self.old_loop = self.armor.get_editor_property('bPatrolLoop')
        # This independent fixture stages the cat once far from armor so noise
        # or a contact cannot replace the native patrol with a chase.
        self.stage(self.cat, self.original_cat_pos, 'AnnexArmorFixtureCatDistant')
        for actor, xy in zip(points, ARMOR_ENDPOINTS*2):
            self.patrol_restore.append((actor, actor.get_actor_transform(), actor.get_editor_property('PauseSeconds')))
            p = actor.get_actor_location()
            actor.set_actor_location(self.u.Vector(*xy, p.z), False, True)
            actor.set_editor_property('PauseSeconds', 0.)
        self.armor.set_editor_property('bPatrolLoop', True)
        p = self.supported(self.u.Vector(*ARMOR_ENDPOINTS[0], 0.), self.armor, [self.armor])
        self.check('Annex armor initial floor support', p is not None)
        self.stage(self.armor, p, 'AnnexArmorRoundTrip')
        self.armor.set_actor_tick_enabled(True)
        self.armor.set_actor_enable_collision(True)
        self.report['armor_route']['system'] = 'Existing native SoundGrid four-way A* and CharacterMovement'
        self.report['armor_route']['capsule_radius_cm'] = self.shape(self.armor)[0]
        self.phase('armor_route')

    def walk_armor(self):
        row = self.report['armor_route']
        p = self.armor.get_actor_location()
        t = self.gs.get_time_seconds(self.world)
        distances = [math.hypot(p.x-a[0], p.y-a[1]) for a in ARMOR_ENDPOINTS]
        endpoint = min(range(2), key=lambda i: distances[i])
        if not row['samples'] or t-row['samples'][-1]['time'] >= .05:
            row['samples'].append({'time': t, 'position': self.v(p), 'velocity': self.v(self.armor.get_velocity()),
                                   'action': str(self.armor.get_action()), 'collision': self.armor.get_actor_enable_collision()})
        assert self.armor.get_actor_enable_collision()
        if distances[endpoint] <= 30. and (row['visits'] or endpoint == 1):
            if not row['visits'] or row['visits'][-1]['endpoint'] != endpoint:
                row['visits'].append({'endpoint': endpoint, 'time': t, 'position': self.v(p), 'distance_cm': distances[endpoint]})
                self.persist()
                if len(row['visits']) == 3:
                    self.check('Native armor Annex round trip B-A-B completed', [v['endpoint'] for v in row['visits']] == [1,0,1])
                    # Each measured leg must actually traverse both arms of the
                    # elbow at Y>-2100, rather than count proximity through walls.
                    for a, b in zip(row['visits'], row['visits'][1:]):
                        samples = [s for s in row['samples'] if a['time'] <= s['time'] <= b['time']]
                        self.check('Native armor leg traversed Annex elbow', any(s['position'][1] > -2100. for s in samples),
                                   {'from': a['endpoint'], 'to': b['endpoint'], 'sample_count': len(samples)})
                    self.finish()

    def step(self):
        p, elapsed = self.report['phase'], time.monotonic()-self.changed
        if p == 'startup':
            if self.gs.get_time_seconds(self.world) > .5 and not self.pc.is_move_input_ignored():
                self.setup()
        elif p == 'observe_enemies' and elapsed > 1.1:
            self.isolate()
        elif p == 'basket_settle' and elapsed > .35:
            available = self.action.can_enter_nearby_basket()
            settled = self.cat.get_actor_location()
            self.case['settled_native_entry'] = {'available': available, 'position': self.v(settled),
                'distance_to_hidden_3d_cm': (settled-self.basket.get_hidden_location()).length(),
                'movement_mode': str(self.cat.get_component_by_class(self.u.CharacterMovementComponent).movement_mode),
                'busy': bool(self.action.get_editor_property('Busy')), 'phase': self.bp()}
            self.check('Native nearby basket entry available', available, self.case)
            self.case['expected_entry_clip'] = self.clip(self.cat.get_actor_location()-self.basket.get_hidden_location(), 'Enter')
            self.interact()
            self.phase('entering')
        elif p == 'entering':
            bp = self.bp()
            if bp == 'OUTSIDE':
                assert elapsed < .7, 'F input failed to enter'
            elif bp == 'ENTERING':
                sample = self.sample_animation()
                assert self.action.get_editor_property('ActiveBasket') == self.basket
                assert sample['cloth_animation'] == self.case['expected_entry_clip']
                assert abs(sample['cat_time']-sample['cloth_time']) < .08 and sample['cloth_tick']
                self.case['entry_samples'].append(sample)
            else:
                assert bp == 'HIDDEN' and self.action.get_editor_property('IsHidden') and not self.action.get_editor_property('Busy')
                assert self.basket.get_editor_property('Occupied') and not self.mesh.is_visible()
                assert not self.cloth().is_component_tick_enabled()
                assert len(self.case['entry_samples']) >= 3, 'Actual entry animation must have observable samples'
                self.select(self.case['key'])
        elif p == 'select_exit' and elapsed > .15:
            direction = self.action.get_editor_property('ExitWorldDirection')
            assert (direction-self.u.Vector(*self.case['expected_direction'])).length() < .002, 'Exit direction differs from camera input'
            can_exit = bool(self.action.get_editor_property('CanExit'))
            self.key(self.case['selected_key'], False)
            self.case.setdefault('direction_results', []).append({'key': self.case['selected_key'], 'direction': self.v(direction), 'can_exit': can_exit})
            if not can_exit and self.case['select_is_fallback']:
                self.fallback()
            else:
                self.case['landing'] = self.v(self.action.get_editor_property('ExitWorldLocation'))
                self.case['expected_exit_clip'] = self.clip(direction, 'Exit')
                self.interact()
                self.phase('exiting' if can_exit else 'blocked_confirm')
        elif p == 'blocked_confirm' and elapsed > .25:
            self.check('Blocked F preserves actual hidden/occupied state', self.bp() == 'HIDDEN'
                       and not self.action.get_editor_property('Busy') and self.basket.get_editor_property('Occupied'))
            self.case['blocked_confirmation_preserved_hidden'] = True
            self.fallback()
        elif p == 'exiting':
            bp = self.bp()
            if bp == 'HIDDEN':
                if self.case['exit_samples'] or (elapsed > .15 and not self.action.get_editor_property('CanExit')):
                    assert not self.action.get_editor_property('Busy') and self.action.get_editor_property('IsHidden')
                    assert self.basket.get_editor_property('Occupied') and not self.cat.get_actor_enable_collision()
                    assert not self.mesh.is_visible() and not self.cloth().is_component_tick_enabled()
                    failures = self.case.setdefault('native_landing_recheck_returns', [])
                    failures.append({'landing': self.case['landing'], 'samples': self.case['exit_samples']})
                    assert len(failures) < 5, 'Repeated native landing recheck failures; no forced recovery'
                    self.case['exit_samples'] = []
                    self.case['fallbacks'] = []
                    self.fallback()
                else:
                    assert elapsed < .7, 'Safe confirmed F exit failed to begin'
            elif bp == 'EXITING':
                sample = self.sample_animation()
                assert sample['cloth_animation'] == self.case['expected_exit_clip']
                assert abs(sample['cat_time']-sample['cloth_time']) < .08 and sample['cloth_tick']
                self.case['exit_samples'].append(sample)
            else:
                assert bp == 'OUTSIDE' and not self.action.get_editor_property('Busy') and not self.action.get_editor_property('IsHidden')
                assert not self.basket.get_editor_property('Occupied') and self.mesh.is_visible() and self.cat.get_actor_enable_collision()
                assert not self.cloth().is_component_tick_enabled()
                assert (self.cat.get_actor_location()-self.u.Vector(*self.case['landing'])).length() < 3.
                assert len(self.case['exit_samples']) >= 3
                self.case['passed'] = True
                self.case_index += 1
                self.begin_basket()
        elif p == 'cat_route':
            self.walk_cat()
        elif p == 'armor_route':
            self.walk_armor()

    def finish(self, error=None):
        if self.report['phase'] == 'shutdown':
            return
        self.pending_error = error
        cleanup_errors = []
        try:
            self.release()
        except Exception:
            cleanup_errors.append(traceback.format_exc())
        for actor, transform, pause in self.patrol_restore:
            try:
                actor.set_actor_transform(transform, False, True)
                actor.set_editor_property('PauseSeconds', pause)
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        if self.armor is not None:
            try:
                self.armor.set_editor_property('bPatrolLoop', self.old_loop)
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        for actor, tick, collision in self.npc_restore:
            try:
                actor.set_actor_tick_enabled(tick)
                actor.set_actor_enable_collision(collision)
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        if self.capture_setting is not None:
            self.u.CatrunUserSettings.set_no_armor_capture_enabled(self.capture_setting)
        self.report['cleanup_errors'] = cleanup_errors
        patrol_restored = all(actor.get_actor_transform().export_text() == transform.export_text()
                              and actor.get_editor_property('PauseSeconds') == pause
                              for actor, transform, pause in self.patrol_restore)
        npc_restored = all(actor.is_actor_tick_enabled() == tick and actor.get_actor_enable_collision() == collision
                           for actor, tick, collision in self.npc_restore)
        loop_restored = self.armor is None or self.armor.get_editor_property('bPatrolLoop') == self.old_loop
        self.report['runtime_fixture_restored'] = not cleanup_errors and patrol_restored and npc_restored and loop_restored
        self.report['error'] = error
        self.phase('shutdown')
        if self.ed.get_game_world():
            self.le.editor_request_end_play()

    def finalize(self):
        actors = self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors()
        actual = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
        self.report['editor_actor_transforms_preserved'] = actual == self.editor_transforms
        self.report['map_bytes_preserved'] = hashlib.sha256(self.map_path.read_bytes()).hexdigest() == self.map_hash
        self.report['execution_complete'] = self.pending_error is None
        self.report['success'] = (self.pending_error is None and self.report['runtime_fixture_restored']
            and self.report['editor_actor_transforms_preserved'] and self.report['map_bytes_preserved']
            and len(self.report['basket_cases']) == 16 and all(c.get('passed') for c in self.report['basket_cases'])
            and all(c['passed'] for c in self.report['checks']))
        self.report['phase'] = 'complete'
        self.persist()
        self.u.unregister_slate_post_tick_callback(self.handle)
        if os.environ.get('CATRUN_STAGE3_PLACEMENT_QA_QUIT') == '1':
            assert '-SaveToUserDir' in self.sl.get_command_line()
            self.sl.execute_console_command(self.ed.get_editor_world(), 'QUIT_EDITOR')

    def tick(self, _delta):
        if self.in_tick:
            return
        self.in_tick = True
        try:
            if self.report['phase'] == 'shutdown':
                if not self.ed.get_game_world() and time.monotonic()-self.changed > .5:
                    self.finalize()
                return
            assert time.monotonic()-self.started < 900., 'Overall runtime QA timeout'
            phase_limit = 180. if self.report['phase'] in ('cat_route', 'armor_route') else 35.
            assert time.monotonic()-self.changed < phase_limit, 'Runtime phase timeout: ' + self.report['phase']
            self.world = self.ed.get_game_world()
            if not self.world:
                return
            self.pc = self.gs.get_player_controller(self.world, 0)
            self.cat = self.gs.get_player_character(self.world, 0)
            if not self.pc or not self.cat:
                return
            self.action = self.cat.get_component_by_class(self.u.CatrunBasketInteractionComponent)
            assert self.action
            if self.release_f is not None and time.monotonic() >= self.release_f:
                self.key('F', False)
                self.release_f = None
            self.step()
        except Exception:
            self.finish(traceback.format_exc())
        finally:
            self.in_tick = False


if __name__ == '__main__':
    main()
