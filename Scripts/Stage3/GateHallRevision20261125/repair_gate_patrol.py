"""Inert four-reference repair; root calls apply(), validates, then saves.

Only the four objects currently referenced by the two Gate armors may move.
No actor-label fallback, enemies moved, grid rebuild, source edits, or save.
Preflight uses real capsule sweeps and read-only serialized grid connectivity.
Native A* is C++-only and must be verified by runtime_qa.py natural patrols.
"""
import collections
import hashlib
import json
import math
import os
import time
import traceback
from pathlib import Path

CONTRACT = {
    'S3_Armor_GateLeft': {'names':['CatrunPatrolPoint_6','CatrunPatrolPoint_7'],
        'before':[[-590.,-3810.,0.],[-790.,-4000.,0.]],
        'after':[[-770.,-4450.,100.],[-280.,-4450.,100.]]},
    'S3_Armor_GateRight': {'names':['CatrunPatrolPoint_8','CatrunPatrolPoint_9'],
        'before':[[90.,-3810.,0.],[290.,-4000.,0.]],
        'after':[[280.,-4450.,100.],[-220.,-4450.,100.]]}}


def xyz(v):return [float(v.x),float(v.y),float(v.z)]


def encode(value):
    if value is None or isinstance(value,(bool,int,float,str)):return value
    if isinstance(value,(list,tuple)):return [encode(v) for v in value]
    if hasattr(value,'x') and hasattr(value,'y') and hasattr(value,'z'):return xyz(value)
    if hasattr(value,'get_path_name'):return value.get_path_name()
    return str(value)


def trace_record(hit):
    if not hit:return {'hit':False}
    d=hit.to_dict()
    return {'hit':True,**{k:encode(d.get(k)) for k in ('blocking_hit','initial_overlap','location',
             'impact_point','impact_normal','distance','hit_actor','hit_component')}}


def physics_diagnostic(u,world,actors,probe_xy,radius,half,ignored):
    """Read actual collision queries/shapes, not registration guessed from flags."""
    result={'probes':[], 'direct_IsPhysicsStateCreated':'C++ only, not UFUNCTION; no Python state flag claimed'}
    mesh_api=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    for name,xy in probe_xy:
        x,y=xy;row={'name':name,'xy':[x,y],'radius':radius,'half_height':half,'covering_floors':[]}
        for actor in actors:
            if not actor.get_actor_label().startswith('S3_Floor'):continue
            c,e=actor.get_actor_bounds(False,False)
            if abs(c.x-x)>e.x+.1 or abs(c.y-y)>e.y+.1:continue
            comp=actor.get_component_by_class(u.StaticMeshComponent);mesh=comp.static_mesh
            detail={'actor':actor.get_actor_label(),'bounds_center':xyz(c),'bounds_extent':xyz(e),
                    'actor_collision':actor.get_actor_enable_collision(),'collision':str(comp.get_collision_enabled()),
                    'profile':str(comp.get_collision_profile_name()),'pawn_response':str(comp.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)),
                    'mesh':mesh.get_path_name() if mesh else None}
            probes={
                'simple_shape_count':lambda:mesh_api.get_simple_collision_count(mesh),
                'convex_shape_count':lambda:mesh_api.get_convex_collision_count(mesh),
                'closest_collision_point':lambda:comp.get_closest_point_on_collision(u.Vector(x,y,100)),
                'body_setup':lambda:mesh.get_editor_property('body_setup').get_path_name(),
                'collision_trace_flag':lambda:mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')}
            for key,query in probes.items():
                try:detail[key]=encode(query())
                except Exception as error:detail[key]={'unavailable':str(error)}
            row['covering_floors'].append(detail)
        start,end=u.Vector(x,y,half+100),u.Vector(x,y,half-100)
        row['capsule_start']=xyz(start);row['capsule_end']=xyz(end)
        row['pawn_capsule_simple']=trace_record(u.SystemLibrary.capsule_trace_single_by_profile(world,start,end,radius,half,
            'Pawn',False,ignored,u.DrawDebugTrace.NONE,False))
        for profile in ('Pawn','BlockAll'):
            for complex_trace in (False,True):
                key='%s_line_%s'%(profile,'complex' if complex_trace else 'simple')
                row[key]=trace_record(u.SystemLibrary.line_trace_single_by_profile(world,u.Vector(x,y,100),u.Vector(x,y,-100),
                    profile,complex_trace,ignored,u.DrawDebugTrace.NONE,False))
        result['probes'].append(row)
    result['support_ready']=all(p['pawn_capsule_simple'].get('blocking_hit',False)
                               and not p['pawn_capsule_simple'].get('initial_overlap',True)
                               and p['pawn_capsule_simple']['impact_normal'][2]>.65 for p in result['probes'])
    return result


def diagnose():
    """Read-only probe entry point, writes no file and changes no component."""
    import unreal as u
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);world=ed.get_editor_world()
    assert world.get_path_name()=='/Game/Maps/Stage3.Stage3' and not ed.get_game_world()
    actors=list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    armor=next(a for a in actors if a.get_actor_label()=='S3_Armor_GateLeft')
    cap=armor.get_component_by_class(u.CapsuleComponent)
    probes=[(label+'_'+str(i),p[:2]) for label,c in CONTRACT.items() for i,p in enumerate(c['after'])]
    probes += [('original_entrance_control',[150,-110]),('original_hall_floor_control',[-250,-3400])]
    ignored=[a for a in actors if isinstance(a,(u.Pawn,u.CatrunCandle))]
    return physics_diagnostic(u,world,actors,probes,cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height(),ignored)


def wait_for_physics(on_ready,on_failure,timeout_seconds=20.):
    """Optional root writer barrier: yield real editor frames; never sleep.

    Callback only runs when original and new-floor strict capsule support
    probes pass. This does not force/recreate physics or relax the tests.
    Root owns serial continuation and closing the writer on failure.
    """
    import unreal as u
    global READINESS
    root=Path(u.Paths.project_dir()).resolve()
    suffix=os.environ.get('CATRUN_GATE_PATROL_REPAIR_PASS','01');assert suffix.replace('_','').isalnum()
    output=root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQAPhysicsReadiness'+suffix+'.json')
    assert not output.exists()
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    READINESS={'success':False,'started':time.monotonic(),'frames':0,'samples':[],'last_probe':0.}
    before=time.monotonic()
    u.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    READINESS['asset_compilation_barrier_seconds']=time.monotonic()-before
    def persist():
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({k:v for k,v in READINESS.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
    def tick(_dt):
        try:
            READINESS['frames']+=1;elapsed=time.monotonic()-READINESS['started']
            if elapsed-READINESS['last_probe']<.5:return
            READINESS['last_probe']=elapsed
            result=diagnose();READINESS['samples'].append({'elapsed':elapsed,'frames':READINESS['frames'],'diagnostic':result})
            if result['support_ready'] and READINESS['frames']>=3:
                READINESS['success']=True;u.unregister_slate_post_tick_callback(READINESS['handle']);persist();on_ready();return
            assert elapsed<timeout_seconds,'Strict support still absent after editor frames; inspect physics diagnostic'
            persist()
        except Exception:
            READINESS['error']=traceback.format_exc()
            u.unregister_slate_post_tick_callback(READINESS['handle']);persist();on_failure(READINESS)
    READINESS['handle']=u.register_slate_post_tick_callback(tick)
    persist()
    return READINESS


def grid_connectivity(grid,start,goal,radius):
    """Baked four-neighbor reachability only. Not a native A* invocation."""
    width,height=int(grid['Width']),int(grid['Height']);size=grid['CellSize'];origin=grid['Origin']
    assert width>0 and height>0 and size>0
    assert all(len(grid[k])==width*height for k in ('Walkable','EdgeMask','WallDistance'))
    def allowed(i):return bool(grid['Walkable'][i]) and grid['WallDistance'][i]>=radius
    def nearest(p):
        rings=math.ceil(radius/size)+3;x=math.floor((p[0]-origin[0])/size);y=math.floor((p[1]-origin[1])/size)
        choices=[j*width+i for j in range(max(0,y-rings),min(height,y+rings+1))
                 for i in range(max(0,x-rings),min(width,x+rings+1)) if allowed(j*width+i)]
        assert choices,'No clearance-valid baked cell near '+str(p)
        def d(i):return (origin[0]+(i%width+.5)*size-p[0])**2+(origin[1]+(i//width+.5)*size-p[1])**2
        return min(choices,key=d)
    src,dst=nearest(start),nearest(goal);queue=collections.deque([src]);previous={src:None}
    while queue and dst not in previous:
        here=queue.popleft();x,y=here%width,here//width
        for direction,(dx,dy) in enumerate(((1,0),(-1,0),(0,1),(0,-1))):
            xx,yy=x+dx,y+dy
            if not 0<=xx<width or not 0<=yy<height:continue
            nxt=yy*width+xx
            if nxt not in previous and int(grid['EdgeMask'][here])&(1<<direction) and allowed(nxt):
                previous[nxt]=here;queue.append(nxt)
    path=[];cursor=dst if dst in previous else None
    while cursor is not None:path.append(cursor);cursor=previous[cursor]
    path.reverse()
    return {'connected':dst in previous,'source_cell':src,'goal_cell':dst,'path_cells':path,
            'radius_cm':radius,'native_astar_executed':False,
            'limitation':'Serialized WallDistance/edges only; runtime PuzzleClearance and door-lane filters require natural native patrol QA.'}


def apply():
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    suffix=os.environ.get('CATRUN_GATE_PATROL_REPAIR_PASS','01');assert suffix.replace('_','').isalnum()
    output=root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQAPatrolRepair'+suffix+'.json')
    assert not output.exists(),'Preserve earlier repair evidence'
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);world=ed.get_editor_world()
    assert world.get_path_name()=='/Game/Maps/Stage3.Stage3' and not ed.get_game_world()
    actors=list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    before={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
    labels={}
    for a in actors:labels.setdefault(a.get_actor_label(),[]).append(a)
    def one(label):
        rows=labels.get(label,[]);assert len(rows)==1,(label,len(rows));return rows[0]
    map_path=root/'Content/Maps/Stage3.umap';sha=hashlib.sha256(map_path.read_bytes()).hexdigest()
    result={'success':False,'save_count':0,'map_sha_before':sha,'actual_references':[],
            'endpoint_sweeps':[],'lane_sweeps':[],'baked_grid_connectivity':[],
            'native_astar_verified':False,'native_astar_pending':'RuntimeQA02 GateLeft/Right two natural cycles on unchanged native AI',
            'scope':__doc__,'dynamic_enemy_collisions':'Other armors/candles excluded from static capsule preflight; natural simultaneous patrol QA remains required.'}
    originals=[]
    try:
        result['physics_before_compilation_barrier']=diagnose()
        before_barrier=time.monotonic()
        u.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        result['compilation_barrier_seconds']=time.monotonic()-before_barrier
        result['physics_after_compilation_barrier']=diagnose()
        grid=one('S3_SoundGrid');data=json.loads(grid.call_method('ExportBakedGridSnapshot'))
        result['grid_sha256']=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        ignored=[a for a in actors if isinstance(a,(u.Pawn,u.CatrunCandle))]
        points_seen=set();operations=[]
        for label,contract in CONTRACT.items():
            armor=one(label);points=list(armor.get_editor_property('PatrolPoints'))
            assert len(points)==2 and not armor.get_editor_property('bPatrolLoop'),label
            assert all(points) and [p.get_name() for p in points]==contract['names'],label
            cap=armor.get_component_by_class(u.CapsuleComponent);assert cap
            radius,half=cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height()
            supported=[]
            for index,(point,old,new) in enumerate(zip(points,contract['before'],contract['after'])):
                assert isinstance(point,u.CatrunPatrolPoint),point.get_path_name()
                assert point.get_path_name() not in points_seen,'Shared patrol reference'
                points_seen.add(point.get_path_name())
                actual=xyz(point.get_actor_location())
                result['actual_references'].append({'armor':label,'slot':index,'path':point.get_path_name(),'before':actual,'after':new})
                assert max(abs(a-b) for a,b in zip(actual,old))<.1,('Unexpected source coordinate; do not overwrite',label,index,actual)
                hit=u.SystemLibrary.capsule_trace_single_by_profile(world,u.Vector(new[0],new[1],half+100),
                    u.Vector(new[0],new[1],half-100),radius,half,'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
                result.setdefault('endpoint_support_queries',[]).append({'armor':label,'slot':index,'target':new,
                    'radius':radius,'half_height':half,'result':trace_record(hit)})
                assert hit,'Missing endpoint support '+label
                h=hit.to_dict();assert h['blocking_hit'] and not h['initial_overlap'] and h['impact_normal'].z>.65,(label,index)
                center=h['location']+u.Vector(0,0,2.2)
                overlap=u.SystemLibrary.capsule_trace_single_by_profile(world,center,center+u.Vector(0,0,.1),radius,half,
                    'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
                row={'armor':label,'slot':index,'supported_capsule_center':xyz(center),'radius_cm':radius,'half_height_cm':half,
                     'clear':not bool(overlap),'blocker':overlap.to_dict()['hit_actor'].get_actor_label() if overlap and overlap.to_dict()['hit_actor'] else None}
                result['endpoint_sweeps'].append(row);assert row['clear'],row
                supported.append(center);operations.append((point,u.Vector(*new)))
            for start,end in ((supported[0],supported[1]),(supported[1],supported[0])):
                hit=u.SystemLibrary.capsule_trace_single_by_profile(world,start,end,radius,half,'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
                row={'armor':label,'from':xyz(start),'to':xyz(end),'clear':not bool(hit),
                     'blocker':hit.to_dict()['hit_actor'].get_actor_label() if hit and hit.to_dict()['hit_actor'] else None}
                result['lane_sweeps'].append(row);assert row['clear'],row
                connectivity=grid_connectivity(data,xyz(start),xyz(end),radius)
                connectivity['armor']=label;result['baked_grid_connectivity'].append(connectivity)
                assert connectivity['connected'],connectivity
        assert len(points_seen)==4
        # All preflight completes before the first mutation.
        for point,target in operations:
            originals.append((point,point.get_actor_transform()))
            point.set_actor_location(target,False,True)
            assert (point.get_actor_location()-target).length()<.01
        after={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
        changed={path for path in before if before[path]!=after[path]}
        assert changed==points_seen,changed
        result['changed_actor_paths']=sorted(changed)
        result['grid_unchanged']=json.loads(grid.call_method('ExportBakedGridSnapshot'))==data
        assert result['grid_unchanged']
        result['success']=True
    except Exception:
        result['error']=traceback.format_exc()
        for actor,transform in reversed(originals):actor.set_actor_transform(transform,False,True)
        result['rolled_back_point_transforms']=bool(originals)
    finally:
        result['map_sha_after']=hashlib.sha256(map_path.read_bytes()).hexdigest()
        result['map_disk_unchanged']=result['map_sha_after']==sha
        result['success']=result['success'] and result['map_disk_unchanged']
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    assert result['success'],'Gate reference repair preflight failed: '+str(output)
    return result
