"""Root-run saved Stage3 geometry and unmodified native patrol observation.

Inert import. main() requires a disposable -SaveToUserDir editor, already on
saved Stage3. No saves, AI movement commands, enemy teleports, route edits,
speed changes, capture cheats, grid rebuilds, or enemy freezing. Cat receives
one collision-checked entrance initialization only. Projection is numeric,
not GPU visibility certification. capture_main() is a SEPARATE posed render
fixture, explicitly unsuitable as evidence of physical traversal.
"""
import hashlib
import importlib.util
import json
import math
import os
import time
import traceback
from pathlib import Path

PATROLS = ('S3_Armor_LobbyPatrol', 'S3_Armor_ControlPatrol',
           'S3_Armor_GateLeft', 'S3_Armor_GateRight', 'S3_Candle_Exhibition',
           'S3_Candle_GateLeft', 'S3_Candle_GateRight')
B1 = {'UpperLeft': (110,2375,140,2550), 'UpperRight': (610,2375,640,2550),
      'LowerLeftVertical': (110,2100,140,2250), 'LowerLeftHorizontal': (140,2100,260,2130),
      'LowerRightVertical': (610,2100,640,2250), 'LowerRightHorizontal': (490,2100,610,2130)}


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def bounds(actor):
    c, e = actor.get_actor_bounds(False, False)
    return [c.x-e.x, -c.y-e.y, c.x+e.x, -c.y+e.y, c.z-e.z, c.z+e.z]


def sequence_cycle(count, loop):
    assert count >= 2
    return list(range(count)) if loop else list(range(count)) + list(range(count-2, 0, -1))


def ordered_progress(visits, count, loop):
    """Keep all cyclic phases consistent with spatially ambiguous visits.

    A repeated coordinate can represent several NON-adjacent route indices.
    Do not collapse such a visit to the first nearest index. Distinct physical
    observations still consume exactly one route slot: no skipping/making up
    invisible visits, including adjacent coincident slots.
    """
    cycle = sequence_cycle(count, loop)
    candidates = [{v} if isinstance(v,int) else set(v) for v in visits]
    possible = [start for start, point in enumerate(cycle) if not candidates or point in candidates[0]]
    possible = [start for start in possible
                if all(cycle[(start+i) % len(cycle)] in options for i, options in enumerate(candidates))]
    return {'valid_order': bool(possible), 'completed_cycles': max(0, len(visits)-1)//len(cycle),
            'required_visits': 2*len(cycle)+1, 'possible_start_phases': possible,
            'resolved_visit_candidates': [sorted({cycle[(start+i) % len(cycle)] for start in possible})
                                          for i in range(len(candidates))]}


def main():
    import unreal as u
    global RUN
    RUN = RuntimeQA(u)
    RUN.start()
    return RUN.report


class RuntimeQA:
    def __init__(self, u):
        self.u, self.gs, self.sl = u, u.GameplayStatics, u.SystemLibrary
        self.ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        self.le = u.get_editor_subsystem(u.LevelEditorSubsystem)
        self.root = Path(u.Paths.project_dir()).resolve()
        suffix = os.environ.get('CATRUN_GATE_HALL_QA_PASS', '01')
        assert suffix.replace('_', '').isalnum()
        self.out = self.root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQA'+suffix+'.json')
        assert not self.out.exists(), 'Preserve previous evidence: '+str(self.out)
        self.map = self.root/'Content/Maps/Stage3.umap'
        self.report = {'success': False, 'execution_complete': False, 'scope': __doc__,
                       'phase': 'created', 'checks': [], 'patrols': {}, 'fixed_enemies': {},
                       'map_sha256_before': self.sha(), 'save_count': 0,
                       'enemy_state_mutations': 0, 'cat_initializations': [],
                       'limitations': ['Two natural patrol cycles in quiet scene; not a combat or manual full-play certificate.',
                                       'Waypoint visits are spatial observations, not access to private native PatrolIndex.',
                                       'Numeric orthographic cap projection is not GPU occlusion verification.']}
        self.started = time.monotonic()
        self.handle = None
        self.world = None
        self.in_tick = False
        self.last_sample = -1.
        self.last_persist = 0.
        self.error = None

    def sha(self):
        return hashlib.sha256(self.map.read_bytes()).hexdigest()

    def persist(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf8')
        self.last_persist = time.monotonic()

    def check(self, name, passed, detail=None):
        self.report['checks'].append(dict(name=name, passed=bool(passed), detail=detail))
        self.persist()
        assert passed, name+': '+str(detail)

    def one(self, label):
        found = self.labels.get(label, [])
        assert len(found) == 1, (label, len(found))
        return found[0]

    def enemy_config(self, actor):
        points = list(actor.get_editor_property('PatrolPoints'))
        result = {'class': actor.get_class().get_path_name(),
                  'points': [{'name': p.get_name(), 'xyz': xyz(p.get_actor_location())} if p else None for p in points],
                  'loop': bool(actor.get_editor_property('bPatrolLoop')),
                  'tick': actor.is_actor_tick_enabled(), 'collision': actor.get_actor_enable_collision()}
        keys = ('bPatrolEnabled','PatrolSpeed','PatrolPauseSeconds') if isinstance(actor,self.u.CatrunCandle) else ('WalkSpeed','bIgnoreFootstepSounds')
        result.update({key: actor.get_editor_property(key) for key in keys})
        return result

    def start(self):
        assert '-SaveToUserDir' in self.sl.get_command_line(), 'Disposable editor required'
        assert self.ed.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
        assert not self.ed.get_game_world()
        self.editor_actors = list(self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors())
        self.editor_transforms = {a.get_path_name(): a.get_actor_transform().export_text() for a in self.editor_actors}
        self.labels = {}
        for a in self.editor_actors:
            self.labels.setdefault(a.get_actor_label(), []).append(a)
        self.report['phase'] = 'static_geometry'
        try:
            self.geometry()
            self.authored = {a.get_actor_label(): self.enemy_config(a) for a in self.editor_actors
                             if isinstance(a,(self.u.CatrunArmor,self.u.CatrunCandle))}
            self.check('All seven required natural patrol actors exist', set(PATROLS) <= self.authored.keys())
            for label,expected in {'S3_Armor_GateLeft':[[-770,-4450,100],[-280,-4450,100]],
                                   'S3_Armor_GateRight':[[280,-4450,100],[-220,-4450,100]]}.items():
                actual=[p['xyz'] for p in self.authored[label]['points'] if p]
                self.check(label+' actual referenced route matches gate-end contract',len(actual)==2
                           and not self.authored[label]['loop']
                           and all(max(abs(a-b) for a,b in zip(p,q))<.1 for p,q in zip(actual,expected)),actual)
            self.report['authored_enemy_settings'] = self.authored
            self.report['phase'] = 'startup'
            self.handle = self.u.register_slate_post_tick_callback(self.tick)
            self.le.editor_request_begin_play()
        except Exception:
            self.finish(traceback.format_exc())

    def geometry(self):
        floors = [bounds(a) for a in self.editor_actors if 'SoundFloor' in map(str,a.tags)]
        missing = [(x,y) for x in range(-975,500,50) for y in range(2925,4600,50)
                   if not any(r[0]-.1 <= x <= r[2]+.1 and r[1]-.1 <= y <= r[3]+.1 for r in floors)]
        self.check('Actual GateHall floor covers 1500 by 1700 cm', not missing,
                   {'canonical_bounds':[-1000,2900,500,4600], 'missing_sample_centers':missing})
        north = [bounds(self.one('S3_Wall_%04d'%i)) for i in range(36,40)]
        self.check('North wall exterior is canonical4600', all(abs(r[3]-4600)<.1 for r in north), north)
        for side, x0, x1 in [('L',-1000,-970),('R',470,500)]:
            actual = [bounds(self.one('S3_Wall_GateExt_%s_%d'%(side,i))) for i in range(3)]
            expected = [[x0,4000+200*i,x1,4200+200*i] for i in range(3)]
            self.check('Extended '+side+' boundary continuous', all(max(abs(a-b) for a,b in zip(r[:4],e))<.1
                         for r,e in zip(actual,expected)), actual)
        snapshot = json.loads((self.root/'Saved/Stage3ApprovalAudit20261125/QA/before/snapshot.json').read_text())
        baseline = {a['label']: a for a in snapshot['actors'].values()}
        plan = json.loads((self.root/'Saved/Stage3GateHallRevision20261125/plan.json').read_text())
        source_for = {op['label']:op['source_label'] for op in plan['copies']}
        groups = {}
        for label, actors in self.labels.items():
            if label.startswith('S3_GrandPillar_'):
                stem, part = label.rsplit('_',1)
                assert len(actors)==1
                groups.setdefault(stem,{})[part]=actors[0]
        self.check('Ten distinct pillar assemblies',len(groups)==10,sorted(groups))
        expected_xy = {(x,y) for x in (-720,220) for y in (3150,3450,3725,4025,4325)}
        actual_xy = set()
        self.cap_bounds = []
        continuation_count = 0
        for stem, parts in groups.items():
            base = bounds(parts['Base']); cap = bounds(parts['Capital'])
            actual_xy.add((round((base[0]+base[2])/2),round((base[1]+base[3])/2)))
            self.cap_bounds.append({'group':stem,'canonical_bounds':cap})
            self.check(stem+' cap ends at3450',abs(cap[5]-3450)<.1,cap)
            extensions = sorted([bounds(a) for name,a in parts.items() if name.startswith('Continuation')],key=lambda r:r[4])
            continuation_count += len(extensions)
            self.check(stem+' five uninterrupted high modules', len(extensions)==5 and abs(extensions[0][4]-840)<.1
                       and abs(extensions[-1][5]-cap[4])<.1
                       and all(abs(a[5]-b[4])<.1 for a,b in zip(extensions,extensions[1:])),extensions)
            group_bounds = [bounds(a) for a in parts.values()]
            lo=[min(r[0] for r in group_bounds),-max(r[3] for r in group_bounds),min(r[4] for r in group_bounds)]
            hi=[max(r[2] for r in group_bounds),-min(r[1] for r in group_bounds),max(r[5] for r in group_bounds)]
            expected_data=[(a+b)/2 for a,b in zip(lo,hi)]+[1.]+[(b-a)/2 for a,b in zip(lo,hi)]+[1.]
            for part, actor in parts.items():
                comp = actor.get_component_by_class(self.u.StaticMeshComponent)
                data=list(comp.get_editor_property('custom_primitive_data').get_editor_property('data'))
                self.check(actor.get_actor_label()+' shares actual full-stack cutaway bounds',len(data)>=24
                           and max(abs(a-b) for a,b in zip(data[16:24],expected_data))<.15,data[16:24])
                collision, shadow = str(comp.get_collision_enabled()), bool(comp.get_editor_property('cast_shadow'))
                if part.startswith('Continuation') or part=='Capital':
                    self.check(actor.get_actor_label()+' high section nonblocking/no shadow', 'NO_COLLISION' in collision and not shadow)
                else:
                    src = baseline[source_for.get(actor.get_actor_label(),actor.get_actor_label())]
                    old = next(iter(src['components'].values()))
                    self.check(actor.get_actor_label()+' baseline collision/shadow retained',
                               collision==old['collision']['enabled'] and shadow==old['presentation']['cast_shadow'],
                               {'collision':collision,'cast_shadow':shadow})
        self.check('Pillars occupy exact five existing-spacing rows per side',actual_xy==expected_xy,sorted(actual_xy))
        self.check('Exactly fifty continuation parts',continuation_count==50,continuation_count)
        self.report['pillar_cap_bounds'] = self.cap_bounds
        corners = json.loads((self.root/'Saved/Stage3GateHallRevision20261125/corner_join_audit.json').read_text())
        body_count = trim_count = 0
        for i,row in enumerate(corners['body_joins']+corners['trim_only']):
            if 'body_patch_canonical_bounds' in row:
                actor = self.one('S3_Wall_CornerJoin_%02d'%i); r=bounds(actor)
                self.check(actor.get_actor_label()+' actual body return',max(abs(a-b) for a,b in zip(r,row['body_patch_canonical_bounds']))<.1,r)
                for label in row['walls']:
                    other=bounds(self.one(label)); overlap=[min(r[j+2],other[j+2])-max(r[j],other[j]) for j in range(2)]
                    self.check(actor.get_actor_label()+' face joins '+label,min(overlap)>=-.1 and max(overlap)>1,overlap)
                body_count+=1
            for j,patch in enumerate(row['trim_patches']):
                actor=self.one('S3_Gothic_WallCornerJoin_%02d_%d'%(i,j)); r=bounds(actor)
                comp=actor.get_component_by_class(self.u.StaticMeshComponent)
                self.check(actor.get_actor_label()+' trim span/nonblocking',max(abs(a-b) for a,b in zip(r,patch['canonical_bounds']))<.1
                           and 'NO_COLLISION' in str(comp.get_collision_enabled()),r)
                trim_count+=1
        self.check('Nine corner bodies and sixty trim returns',body_count==9 and trim_count==60,[body_count,trim_count])
        altar = {}
        for name,expected in B1.items():
            r=bounds(self.one('S3_Wall_Altar_'+name)); altar[name]=r
            self.check('B1 '+name+' wall measured',max(abs(a-b) for a,b in zip(r[:4],expected))<.1,r)
        openings=[altar['UpperLeft'][1]-altar['LowerLeftVertical'][3],
                  altar['UpperRight'][1]-altar['LowerRightVertical'][3],
                  altar['LowerRightHorizontal'][0]-altar['LowerLeftHorizontal'][2]]
        self.check('B1 openings 125/125/230cm',all(abs(a-b)<.1 for a,b in zip(openings,[125,125,230])),openings)

    def setup(self):
        actors=list(self.gs.get_all_actors_of_class(self.world,self.u.Actor))
        self.live={a.get_actor_label():a for a in actors if isinstance(a,(self.u.CatrunArmor,self.u.CatrunCandle))}
        for label,a in self.live.items():
            self.check(label+' live authored route/settings retained',self.enemy_config(a)==self.authored[label])
        cap=self.cat.get_component_by_class(self.u.CapsuleComponent)
        radius,half=cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height()
        hit=self.sl.capsule_trace_single_by_profile(self.world,self.u.Vector(150,-110,100),self.u.Vector(150,-110,-50),
                 radius,half,'Pawn',False,[self.cat],self.u.DrawDebugTrace.NONE,False)
        assert hit,'No supported entrance staging'
        d=hit.to_dict(); assert d['blocking_hit'] and not d['initial_overlap'] and d['impact_normal'].z>.65
        destination=d['location']+self.u.Vector(0,0,2.2)
        overlap=self.sl.capsule_trace_single_by_profile(self.world,destination,destination+self.u.Vector(0,0,.1),
                 radius,half,'Pawn',False,[self.cat],self.u.DrawDebugTrace.NONE,False)
        self.check('One cat entrance initialization is collision clear',not overlap,xyz(destination))
        self.cat.get_component_by_class(self.u.CharacterMovementComponent).stop_movement_immediately()
        self.cat.consume_movement_input_vector()
        original=xyz(self.cat.get_actor_location())
        self.cat.set_actor_location(destination,False,True)
        self.report['cat_initializations'].append({'from':original,'to':xyz(destination)})
        self.cat_origin=xyz(destination)
        for label,a in self.live.items():
            config=self.authored[label]
            if label in PATROLS:
                points=[p['xyz'] for p in config['points'] if p]
                assert len(points)>=2 and len(points)==len(config['points'])
                self.report['patrols'][label]={'points':points,'loop':config['loop'],'visit_radius_cm':55. if isinstance(a,self.u.CatrunArmor) else 12.,
                    'visits':[],'samples':[],'travel_cm':0.,'max_observed_speed_cm_s':0.,'status':'observing'}
            elif not config['points'] and not config.get('bPatrolEnabled',False):
                self.report['fixed_enemies'][label]={'initial':xyz(a.get_actor_location()),'max_displacement_cm':0.,'settings_preserved':True}
        self.observe_started=self.gs.get_time_seconds(self.world)
        self.report['phase']='observe'
        self.persist()

    def projection(self):
        pc=self.gs.get_player_controller(self.world,0)
        manager=self.gs.get_player_camera_manager(pc,0)
        rotation=manager.get_camera_rotation(); camera=xyz(manager.get_camera_location()); cat=xyz(self.cat.get_actor_location())
        follow=[a for a in self.gs.get_all_actors_of_class(self.world,self.u.Actor) if a.get_actor_label()=='S3_FollowCamera']
        assert len(follow)==1
        component=follow[0].get_component_by_class(self.u.CameraComponent)
        width=float(component.get_editor_property('ortho_width'))
        aspect=float(component.get_editor_property('aspect_ratio'))
        near=float(component.get_editor_property('ortho_near_clip_plane'))
        self.check('Stage3 expanded near plane survives BeginPlay',abs(near+4000)<.01
                   and component.get_editor_property('ortho_far_clip_plane')==10000.
                   and not component.get_editor_property('auto_calculate_ortho_planes')
                   and not component.get_editor_property('update_ortho_planes'),near)
        self.check('Active follow camera has actual900cm orthographic16:9 projection',
                   'ORTHOGRAPHIC' in str(component.get_editor_property('projection_mode'))
                   and abs(width-900)<.01 and abs(aspect-16/9)<.0001
                   and distance(camera,xyz(component.get_world_location()))<.1,
                   {'width_cm':width,'aspect':aspect})
        self.check('Actual possessed camera remains pitch-55 yaw-135',abs(rotation.pitch+55)<.05 and abs(rotation.yaw+135)<.05,
                   [rotation.pitch,rotation.yaw,rotation.roll])
        pitch,yaw=map(math.radians,(rotation.pitch,rotation.yaw))
        forward=[math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch)]
        up=[-math.sin(pitch)*math.cos(yaw),-math.sin(pitch)*math.sin(yaw),math.cos(pitch)]
        offset=[a-b for a,b in zip(camera,cat)]
        source=json.loads((self.root/'Saved/Stage3GateHallRevision20261125/projection.json').read_text())
        samples=[]
        for row in self.cap_bounds:
            x0,y0,x1,y1,z0,z1=row['canonical_bounds']
            for pose in source['extreme_cat_poses']:
                p=pose['cat'];p=[p[0],p[1],cat[2]]
                for x in (x0,x1):
                    for y in (-y0,-y1):
                        screen_y=sum(up[i]*(q-p[i]-offset[i]) for i,q in enumerate((x,y,z1)))
                        samples.append({'group':row['group'],'cat':p,'cap_corner':[x,y,z1],
                                        'screen_top_margin_cm':screen_y-width/aspect/2,
                                        'camera_depth_cm':sum(forward[i]*(q-p[i]-offset[i]) for i,q in enumerate((x,y,z1)))})
        self.report['projection']={'method':'CPU affine orthographic projection, fixed900cm/16:9 camera contract; not GPU',
                                   'camera_offset_cm':offset,'pairs':len(samples),'worst':min(samples,key=lambda s:s['screen_top_margin_cm'])}
        self.check('All ten cap four-corners outside view at eight extreme poses',len(samples)==320
                   and min(s['screen_top_margin_cm'] for s in samples)>0,self.report['projection'])
        worst=min(samples,key=lambda s:s['camera_depth_cm'])
        self.report['projection']['near_plane']=near
        self.report['projection']['minimum_depth_case']=worst
        self.check('Near plane retains all pillar stack AABBs with50cm margin',worst['camera_depth_cm']>=near+50,worst)

    def sample(self, game):
        if game-self.last_sample<.1:return
        self.last_sample=game
        self.check_quiet_cat=distance(xyz(self.cat.get_actor_location()),self.cat_origin)<10
        assert self.check_quiet_cat,'Cat moved from quiet staging; patrol observation contaminated'
        for label,row in self.report['patrols'].items():
            a=self.live[label]; p=xyz(a.get_actor_location())
            assert a.is_actor_tick_enabled() and a.get_actor_enable_collision(),label+' disabled'
            samples=row['samples']
            if samples:
                step=distance(p,samples[-1]['position']); dt=game-samples[-1]['game']
                row['travel_cm']+=step
                row['max_observed_speed_cm_s']=max(row['max_observed_speed_cm_s'],step/max(dt,.0001))
                assert step/max(dt,.0001)<1200,label+' discontinuous position/reset'
            samples.append({'game':game,'position':p,'velocity':xyz(a.get_velocity())})
            nearest=min(range(len(row['points'])),key=lambda i:distance(p,row['points'][i]))
            candidates=[i for i,q in enumerate(row['points']) if distance(q,row['points'][nearest])<.1]
            if distance(p,row['points'][nearest])<=row['visit_radius_cm'] and (not row['visits'] or row['visits'][-1]['candidates']!=candidates):
                row['visits'].append({'candidates':candidates,'game':game,'distance_cm':distance(p,row['points'][nearest])})
            progress=ordered_progress([v['candidates'] for v in row['visits']],len(row['points']),row['loop'])
            row['progress']=progress
            assert progress['valid_order'],label+' wrong observed route order'
            if progress['completed_cycles']>=2 and row['travel_cm']>100:
                row['status']='passed_two_natural_cycles'
        for label,row in self.report['fixed_enemies'].items():
            a=self.live[label]
            row['max_displacement_cm']=max(row['max_displacement_cm'],distance(xyz(a.get_actor_location()),row['initial']))
            row['settings_preserved']=self.enemy_config(a)==self.authored[label]
            assert row['settings_preserved'],label+' fixed enemy settings changed'
        if time.monotonic()-self.last_persist>3:self.persist()

    def finish(self,error=None):
        if self.report['phase'] in ('shutdown','complete','failed'):return
        self.error=error;self.report['error']=error;self.report['phase']='shutdown';self.shutdown=time.monotonic()
        self.persist()
        if self.ed.get_game_world():self.le.editor_request_end_play()
        elif self.handle is None:self.finalize()

    def finalize(self):
        actors=self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors()
        self.report['map_sha256_after']=self.sha()
        self.report['map_bytes_preserved']=self.report['map_sha256_before']==self.report['map_sha256_after']
        self.report['editor_transforms_preserved']=self.editor_transforms=={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
        self.report['execution_complete']=self.error is None
        self.report['success']=self.error is None and self.report['map_bytes_preserved'] and self.report['editor_transforms_preserved']
        self.report['phase']='complete' if self.report['success'] else 'failed'
        self.persist()
        if self.handle:self.u.unregister_slate_post_tick_callback(self.handle)
        if os.environ.get('CATRUN_GATE_HALL_QA_QUIT')=='1':
            self.sl.execute_console_command(self.ed.get_editor_world(),'QUIT_EDITOR')

    def tick(self,_dt):
        if self.in_tick:return
        self.in_tick=True
        try:
            if self.report['phase']=='shutdown':
                if not self.ed.get_game_world() and time.monotonic()-self.shutdown>.5:self.finalize()
                return
            assert time.monotonic()-self.started<600,'Overall wall-clock timeout'
            self.world=self.ed.get_game_world()
            if not self.world:return
            self.cat=self.gs.get_player_character(self.world,0)
            if not self.cat:return
            game=self.gs.get_time_seconds(self.world)
            if self.report['phase']=='startup':
                if game>=3:self.setup()
                return
            self.sample(game)
            if game-self.observe_started>5 and 'projection' not in self.report:self.projection()
            if all(r['status']=='passed_two_natural_cycles' for r in self.report['patrols'].values()) and 'projection' in self.report:
                for label,a in self.live.items():self.check(label+' authored settings unchanged after observation',self.enemy_config(a)==self.authored[label])
                self.finish()
            elif game-self.observe_started>240:
                failed={k:v['progress'] for k,v in self.report['patrols'].items() if v['status']!='passed_two_natural_cycles'}
                raise AssertionError('Natural patrol timeout; incomplete, not passed: '+str(failed))
        except Exception:self.finish(traceback.format_exc())
        finally:self.in_tick=False


def capture_main():
    """Separate root-run render fixture: twenty near-pillar cat poses + eight extremes."""
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    suffix=os.environ.get('CATRUN_GATE_HALL_CAPTURE_PASS','01')
    assert suffix.replace('_','').isalnum()
    out=root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQACapture'+suffix)
    assert not out.exists(),'Preserve previous capture evidence'
    os.environ['CATRUN_GOTHIC_CAPTURE']='before'
    os.environ['CATRUN_GOTHIC_LIT_ONLY']='1'
    os.environ.pop('CATRUN_GOTHIC_VIEWS',None)
    os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC',None)
    spec=importlib.util.spec_from_file_location('s3_gatehall_render_fixture',root/'Scripts/Stage3/GothicRevision/capture.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=out;out.mkdir(parents=True)
    module.VIEWS=[]
    for side,x in [('Left',-720),('Right',220)]:
        for row,y in enumerate((3150,3450,3725,4025,4325)):
            for face,sign in [('Behind',-1),('InFront',1)]:
                module.VIEWS.append(('%s%d_%s'%(side,row,face),(x+sign*125,-y+sign*125,26.2)))
    projection=json.loads((root/'Saved/Stage3GateHallRevision20261125/projection.json').read_text())
    # Mathematical extrema sit on inner wall faces; render poses inset by the
    # cat capsule so these illustrative fixtures do not embed it in stone.
    for i,p in enumerate(projection['extreme_cat_poses']):
        x0,y0,x1,y1=projection['regions_world_xy'][p['region']]
        x,y,z=p['cat']
        module.VIEWS.append(('Extreme%d'%i,(x+26 if x==x0 else x-26,y+26 if y==y0 else y-26,z)))
    module.S['fixture']='Posed rendering only: inherited capture freezes NPCs and repositions cat per view; NOT natural traversal. Actual GPU images require root visual review.'
    return module


if __name__=='__main__':
    main()
