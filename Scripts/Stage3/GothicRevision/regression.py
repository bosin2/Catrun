"""Existing 53-check native puzzle suite plus real movement around new furniture.

Fixtures disable NPC tick/collision after observing patrols; this is not a claim
of a complete unassisted playthrough. Map and gameplay settings are never saved.
"""
import importlib.util,json,math,time
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3GothicRevision20261125/Regression'
OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('native_stage3_regression',str(ROOT/'Scripts/Stage3/verify_pie.py'))
test=importlib.util.module_from_spec(spec)
spec.loader.exec_module(test)
test.OUT=OUT
test.S['scope']=__doc__
test.S['route_checks']=[]
original_step=test.step
routes=[('LobbyLeft',(-270,250),(-270,740)),
        ('LowerStrategy',(-210,850),(-210,1510)),
        ('LowerBench',(145,1010),(145,1450)),
        ('WarehouseNorthOpening',(1000,1320),(1000,1660)),
        ('WarehouseBenchFront',(610,1320),(930,1320)),
        ('ExhibitionLeftReturn',(-900,2038),(-900,1480)),
        ('ExhibitionShieldCorner',(-900,2040),(-770,2040)),
        ('P1LeftDockBypass',(-750,2050),(-750,2350))]
presentation=json.loads((ROOT/'Saved/Stage3GothicRevision20261125/presentation_report.json').read_text(encoding='utf8'))
def check_dock(w,n):
    lookup={a.get_actor_label():a for a in test.GS.get_all_actors_of_class(w,u.Actor)}
    expected=presentation['instances'][n-1]
    presenter=lookup[expected['actor']]
    test.check('Dock%d presenter ticking'%n,presenter.is_actor_tick_enabled())
    test.check('Dock%d cosmetic latch reached closed state'%n,abs(presenter.get_editor_property('Alpha')-1)<.001)
    for key in ('Fork','Pin','ChainTerminal'):
        actor=lookup[expected['references'][key]]
        distance=(actor.get_actor_location()-u.Vector(*expected['poses'][key+'Closed'])).length()
        test.check('Dock%d %s closed pose'%(n,key),distance<.05,{'error_cm':distance,'actual':test.xyz(actor.get_actor_location())})
        test.check('Dock%d %s remains nonblocking'%(n,key),actor.static_mesh_component.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION)
    chain=lookup[expected['references']['OpenChain']].static_mesh_component
    test.check('Dock%d uses closed source chain'%n,chain.static_mesh.get_name()=='SM_S3_DockShortChain')
    test.S['dock%d_checked'%n]=True
def step(w):
    cat=test.GS.get_player_character(w,0)
    if not cat:return
    if test.S['phase']=='wait_d1' and not test.S.get('dock1_checked'):
        puzzle=test.actors(w,u.CatrunStatuePuzzle)[0]
        if puzzle.get_editor_property('Links')[0].get_editor_property('bCompleted'):check_dock(w,1)
    if test.S['phase']=='wait_d2' and not test.S.get('dock2_checked'):
        check_dock(w,2)
    if test.S['phase']=='push1' and not test.S.get('routes_complete'):
        if 'route_index' not in test.S:
            test.S['route_index']=0;test.S['route_phase']='start'
        index=test.S['route_index'];name,start,end=routes[index]
        if test.S['route_phase']=='start':
            test.move(cat,*start);test.S['route_time']=test.GS.get_time_seconds(w)
            test.S['route_phase']='walk';test.S['changed']=time.monotonic();return
        p=cat.get_actor_location();delta=u.Vector(end[0]-p.x,end[1]-p.y,0)
        if delta.length()<15:
            result={'route':name,'start':start,'end':end,'actual':test.xyz(p),
                    'seconds':test.GS.get_time_seconds(w)-test.S['route_time']}
            test.S['route_checks'].append(result)
            test.check('New furniture traversal '+name,True,result)
            test.S['route_index']+=1;test.S['route_phase']='start'
            if test.S['route_index']==len(routes):
                test.S['routes_complete']=True;test.S['changed']=time.monotonic()
            return
        test.check('Traversal '+name+' not blocked',False,test.xyz(p)) if test.GS.get_time_seconds(w)-test.S['route_time']>18 else None
        cat.add_movement_input(delta.normal(),1,False);return
    original_step(w)
test.step=step
