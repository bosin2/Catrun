"""Read-only Gothic revision invariants; import then snapshot('before'/'after').

Root owns execution and must already have saved Stage3 loaded, outside PIE.
No actor changes, asset saves, selection changes, or level loads occur here.
CPython may run compare() after both snapshots exist.
"""
import hashlib
import json
import math
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Saved/Stage3GothicRevision20261125/QA'
WAREHOUSE={'S3_Cabinet1','S3_Cabinet2','S3_Shield1','S3_Shield2',
           'S3_ArmorRack1','S3_ArmorRack2','S3_SupplyBox'}
APPROVED_NEW_FURNITURE={'S3_Gothic_'+name for name in ('LobbyBench','LobbyCabinet',
    'LowerStrategy','LowerBench','ExhibitionShield','WarehouseMaintenance')}
PUZZLE_FIELDS=('PuzzleId','Statue','Plate','Gate','ContactHalfExtent','SocketAxis',
               'GateFloorOffset','bExternalGateUnlocked')
OBJECTIVE_FIELDS=('Puzzle','LockedPuzzleId','FinalLeafLeft','FinalLeafRight',
                  'InteractionRange','ReleaseAnimation','MouthOffsets')
ROUTE_FIELDS=('PatrolPoints','bPatrolEnabled','bPatrolLoop')


def digest(file):
    h=hashlib.sha256()
    with Path(file).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')


def snapshot(phase):
    import unreal as u
    assert phase in ('before','after')
    folder=OUT/phase
    assert not (folder/'snapshot.json').exists(),'Refusing to overwrite existing baseline/evidence'
    folder.mkdir(parents=True,exist_ok=True)
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name()=='/Game/Maps/Stage3.Stage3',world.get_path_name()
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(),'Snapshot must not run in PIE'
    def path(obj):return obj.get_path_name() if obj else None
    def vec(v):return [v.x,v.y,v.z]
    def encode(v):
        if isinstance(v,u.Object):return path(v)
        if v is None or isinstance(v,(bool,int,float,str)):return v
        if hasattr(v,'export_text'):return v.export_text()
        try:return [encode(x) for x in v]
        except TypeError:return str(v)
    def props(obj,names):
        result={}
        for name in names:
            try:result[name]=encode(obj.get_editor_property(name))
            except Exception:pass
        return result
    def bounds(actor,only_collision=False):
        center,extent=actor.get_actor_bounds(only_collision,False)
        return {'center':vec(center),'extent':vec(extent)}
    rows={};puzzles={};objectives={};critical=set()
    actors=u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    for a in actors:
        if isinstance(a,u.CatrunStatuePuzzle):
            links=[]
            for link in a.get_editor_property('Links'):
                row=props(link,PUZZLE_FIELDS);links.append(row)
                critical.update(row[k] for k in ('Statue','Plate','Gate'))
            puzzles[path(a)]={'links':links,'settings':props(a,('Settings',))}
            critical.add(path(a))
        if isinstance(a,u.CatrunStage3Objectives):
            devices=[]
            for device in a.get_editor_property('Devices'):
                row=props(device,('Housing','Ring','Pin','LockBolt','ChainLinks'));devices.append(row)
                critical.update(row[k] for k in ('Housing','Ring','Pin','LockBolt') if row.get(k))
                critical.update(row.get('ChainLinks',[]))
            objectives[path(a)]={'devices':devices,'properties':props(a,OBJECTIVE_FIELDS)}
            critical.update([path(a)]+[objectives[path(a)]['properties'].get(k) for k in ('FinalLeafLeft','FinalLeafRight')])
    channel_names=('ECC_WORLD_STATIC','ECC_WORLD_DYNAMIC','ECC_PAWN','ECC_VISIBILITY','ECC_CAMERA','ECC_PHYSICS_BODY')
    for a in actors:
        label=a.get_actor_label()
        structural=bool(re.match(r'S3_(Wall_|Floor_|ExitLanding|[HD][0-3]_)',label))
        gameplay=not isinstance(a,(u.StaticMeshActor,u.Light,u.PostProcessVolume,u.SkyLight))
        if structural or gameplay or label in WAREHOUSE:critical.add(path(a))
        row={'label':label,'class':path(a.get_class()),'transform':a.get_actor_transform().export_text(),
             'parent':path(a.get_attach_parent_actor()),'all_component_bounds':bounds(a),
             'colliding_bounds':bounds(a,True),'components':{},'route':props(a,ROUTE_FIELDS),
             'structural':structural,'warehouse':label in WAREHOUSE,'gameplay':gameplay}
        for c in a.get_components_by_class(u.SceneComponent):
            component={'class':path(c.get_class()),'transform':c.get_world_transform().export_text(),
                       'relative_transform':c.get_relative_transform().export_text(),
                       'parent':path(c.get_attach_parent())}
            if isinstance(c,u.PrimitiveComponent):
                component['collision']={'enabled':str(c.get_collision_enabled()),
                    'profile':str(c.get_collision_profile_name()),'object_type':str(c.get_collision_object_type()),
                    'responses':{n:str(c.get_collision_response_to_channel(getattr(u.CollisionChannel,n))) for n in channel_names},
                    'shape':props(c,('capsule_radius','capsule_half_height','box_extent','sphere_radius','generate_overlap_events'))}
                component['presentation']=props(c,('visible','hidden_in_game','cast_shadow'))
            if isinstance(c,u.StaticMeshComponent):component['mesh']=path(c.static_mesh)
            if isinstance(c,u.SkeletalMeshComponent):
                component['mesh']=path(c.get_skinned_asset())
                component['animation']=props(c,('anim_class','animation_mode'))
            if isinstance(c,u.MeshComponent):component['materials']=[path(c.get_material(i)) for i in range(c.get_num_materials())]
            row['components'][c.get_name()]=component
        rows[path(a)]=row
    critical.discard(None)
    hashes={}
    for relative in ('Content/Environment/Stage1','Content/Environment/Stage2','Content/Environment/Shared',
                     'Content/Characters','Source','Config'):
        for file in (ROOT/relative).rglob('*'):
            if file.is_file():hashes[file.relative_to(ROOT).as_posix()]=digest(file)
    for name in ('Stage1','Stage2','Tutorial'):
        file=ROOT/('Content/Maps/'+name+'.umap')
        if file.exists():hashes[file.relative_to(ROOT).as_posix()]=digest(file)
    task=u.AssetExportTask();task.object=world;task.exporter=u.LevelExporterT3D()
    task.filename=str(folder/'world.t3d');task.automated=True;task.prompt=False;task.selected=False;task.replace_identical=False
    assert u.Exporter.run_asset_export_task(task)
    data={'phase':phase,'world':path(world),'actors':rows,'critical':sorted(critical),
          'puzzles':puzzles,'objectives':objectives,'protected_sha256':hashes,
          'bounds_semantics':'get_actor_bounds(False, False) exactly calls GetComponentsBoundingBox(true, false); hidden/noncolliding own components included, separate attached actors excluded',
          'saved_map_sha256':digest(ROOT/'Content/Maps/Stage3.umap')}
    write(folder/'snapshot.json',data)
    print('GOTHIC_SNAPSHOT_OK',phase,len(rows),len(critical),len(hashes))
    return data


def compare():
    before=json.loads((OUT/'before/snapshot.json').read_text(encoding='utf8'))
    after=json.loads((OUT/'after/snapshot.json').read_text(encoding='utf8'))
    checks=[]
    def check(name,passed,detail=None):checks.append({'name':name,'passed':bool(passed),'detail':detail})
    check('Puzzle links/settings identical',before['puzzles']==after['puzzles'])
    check('Three objectives, interaction offsets, chain references and exit leaves identical',before['objectives']==after['objectives'])
    check('Exactly two puzzle links and three releases retained',sum(len(p['links']) for p in after['puzzles'].values())==2 and sum(len(o['devices']) for o in after['objectives'].values())==3)
    missing=[p for p in before['critical'] if p not in after['actors']]
    check('All critical original actor identities retained',not missing,missing)
    bounds_errors=[];transform_errors=[];collision_errors=[];route_errors=[]
    puzzle_bound_actors={link[k] for puzzle in before['puzzles'].values() for link in puzzle['links'] for k in ('Statue','Plate','Gate')}
    for path,b in before['actors'].items():
        a=after['actors'].get(path)
        if a is None:
            # Removing a decorative NoCollision actor is allowed. Collision-bearing
            # originals must remain as hidden proxies unless explicitly re-audited.
            if any('NO_COLLISION' not in c.get('collision',{}).get('enabled','NO_COLLISION') for c in b['components'].values()):
                collision_errors.append([b['label'],'original collision actor removed'])
            continue
        if path in before['critical']:
            for key in ('transform','class','parent'):
                if b[key]!=a[key]:transform_errors.append([b['label'],key,b[key],a[key]])
            if b['route']!=a['route']:route_errors.append([b['label'],b['route'],a['route']])
        if path in puzzle_bound_actors or b['warehouse']:
            if not bounds_near(b['all_component_bounds'],a['all_component_bounds']):
                bounds_errors.append([b['label'],'all-component native gameplay bounds',b['all_component_bounds'],a['all_component_bounds']])
        for name,bc in b['components'].items():
            collision=bc.get('collision')
            if not collision or 'NO_COLLISION' in collision['enabled']:continue
            ac=a['components'].get(name)
            if ac is None:
                collision_errors.append([b['label'],name,'original collision component removed']);continue
            for key in ('collision','transform','mesh'):
                if bc.get(key)!=ac.get(key):collision_errors.append([b['label'],name,key,bc.get(key),ac.get(key)])
    check('Original critical/structural/warehouse transforms unchanged',not transform_errors,transform_errors)
    check('Puzzle statue/plate/gate and warehouse bounds contract exact within 0.01cm',not bounds_errors,bounds_errors)
    check('All original collider transforms, meshes and responses preserved',not collision_errors,collision_errors)
    check('Enemy patrol routing unchanged',not route_errors,route_errors)
    warehouse=[r for r in after['actors'].values() if r['warehouse']]
    check('Seven original warehouse blockers retained',len(warehouse)==7,[r['label'] for r in warehouse])
    new={p:a for p,a in after['actors'].items() if p not in before['actors']}
    blockers=[];approved_blockers=[]
    for path,a in new.items():
        for name,c in a['components'].items():
            collision=c.get('collision')
            if collision and 'NO_COLLISION' not in collision['enabled']:
                record=[a['label'],name,collision,a['colliding_bounds']]
                (approved_blockers if a['label'] in APPROVED_NEW_FURNITURE else blockers).append(record)
    check('New colliders restricted to explicitly authorized furniture; decorative actors nonblocking',not blockers,blockers)
    drift=[p for p,h in before['protected_sha256'].items() if after['protected_sha256'].get(p)!=h]
    check('Stage1/2 shared originals, original characters, Source and Config hashes unchanged',not drift,drift)
    result={'success':all(c['passed'] for c in checks),'checks':checks,'new_visual_actors':len(new),
            'new_furniture_colliders_requiring_runtime_clearance':approved_blockers,
            'before_actors':len(before['actors']),'after_actors':len(after['actors']),
            'scope':'No package writes. New visuals/materials/lights and removal of noncolliding decorations allowed. Real player routes, objective sequence and visual attachment motion require separate PIE regression.'}
    write(OUT/'comparison.json',result)
    return result


def bounds_near(a,b,tolerance=.01):
    return all(abs(x-y)<=tolerance for key in ('center','extent') for x,y in zip(a[key],b[key]))


if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[-1]=='compare':print(json.dumps(compare(),indent=2))
    else:raise RuntimeError("Import and call snapshot('before') or snapshot('after') from a coordinated Stage3 editor process")
