"""Cold-load checks against the saved map and collision geometry, no map edits."""
import json, traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve(); OUT=ROOT/'Saved/Stage3Integration20261125'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem); LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
GS=u.GameplayStatics; SL=u.SystemLibrary
R={'checks':[],'scope':'Cold saved assets and physical collision traces; no claim of manual playthrough.'}
def check(name,passed,detail=None):
    R['checks'].append({'name':name,'passed':bool(passed),'detail':detail})
def trace(start,end,radius,half,ignored=()):
    return SL.capsule_trace_single_by_profile(ED.get_editor_world(),u.Vector(*start),u.Vector(*end),radius,half,
        'Pawn',False,list(ignored),u.DrawDebugTrace.NONE,True)
def main():
    assert LE.load_level('/Game/Maps/Stage3')
    world=ED.get_editor_world(); actors=GS.get_all_actors_of_class(world,u.Actor)
    named={a.get_actor_label():a for a in actors}
    for cls,count in [(u.CatrunArmor,6),(u.CatrunCandle,5),(u.CatrunStatuePuzzle,1),(u.CatrunStage3Objectives,1),(u.CatrunDoor,1),(u.CatrunStageExit,1),(u.CatrunNoBellZone,3)]:
        got=len(GS.get_all_actors_of_class(world,cls));check(cls.__name__,got==count,got)
    director=named['S3_Objectives']; devices=director.get_editor_property('Devices')
    check('Three connected releases',len(devices)==3 and all(d.get_editor_property('Housing') and d.get_editor_property('Ring') and d.get_editor_property('LockBolt') for d in devices))
    puzzle=named['S3_StatuePuzzles'];links=puzzle.get_editor_property('Links')
    check('Two connected statue gates',len(links)==2 and all(l.get_editor_property('Statue') and l.get_editor_property('Plate') and l.get_editor_property('Gate') for l in links))
    check('P2 external lock starts closed',not links[1].get_editor_property('bExternalGateUnlocked'))
    grid=named['S3_SoundGrid'];check('Saved perception grid',grid.has_grid())
    check('Minimap authored',len(GS.get_all_actors_of_class(world,u.CatrunMinimapPresenter))==1)
    missing=[]
    for a in GS.get_all_actors_of_class(world,u.StaticMeshActor):
        c=a.static_mesh_component
        if not c.static_mesh:missing.append(a.get_actor_label()+':mesh')
        for i in range(c.get_num_materials()):
            m=c.get_material(i)
            if not m or 'DefaultMaterial' in m.get_name() or 'WorldGrid' in m.get_name():missing.append(a.get_actor_label()+':material')
    check('No missing/default static materials',not missing,missing)
    for name,x,y in [('H1',250,500),('H2',600,1800),('H3',1100,1800)]:
        cat=trace((x,y-55,26.2),(x,y+55,26.2),20,26)
        armor=trace((x,y-60,100),(x,y+60,100),35,100)
        check(name+' cat capsule passes',not cat,str(cat) if cat else None)
        check(name+' armor capsule blocked',bool(armor))
    for name,x,y in [('D1',100,1800),('D2',-200,2350)]:
        hit=trace((x,y-70,26),(x,y+70,26),20,24)
        check(name+' closed gate blocks',bool(hit))
        gate=named['S3_'+name+'_Bars']
        hit=trace((x,y-70,26),(x,y+70,26),20,24,[gate])
        check(name+' empty frame admits cat',not hit,str(hit) if hit else None)
    floor=SL.line_trace_single_by_profile(world,u.Vector(150,110,200),u.Vector(150,110,-50),'Pawn',False,[],u.DrawDebugTrace.NONE,True)
    check('Player start has floor',bool(floor))
    npcs=list(GS.get_all_actors_of_class(world,u.CatrunArmor))+list(GS.get_all_actors_of_class(world,u.CatrunCandle))
    for npc in npcs:
        c=npc.get_component_by_class(u.CapsuleComponent);v=c.get_world_location()+u.Vector(0,0,.25)
        hit=SL.capsule_trace_single_by_profile(world,v,v+u.Vector(0,0,.01),c.get_scaled_capsule_radius(),c.get_scaled_capsule_half_height(),'Pawn',False,npcs,u.DrawDebugTrace.NONE,True)
        check(npc.get_actor_label()+' supported spawn clearance',not hit,{k:str(v) for k,v in hit.to_dict().items()} if hit else None)
    # Swept statue footprint along the two authored straight push lanes.
    ignored=[l.get_editor_property('Statue') for l in links]+list(GS.get_all_actors_of_class(world,u.Pawn))
    for i,l in enumerate(links):
        a=l.get_editor_property('Statue').get_actor_location();b=l.get_editor_property('Plate').get_actor_location()
        hit=SL.box_trace_single_by_profile(world,a+u.Vector(0,0,78),u.Vector(b.x,b.y,78),u.Vector(59,59,73),u.Rotator(),'Pawn',False,ignored,u.DrawDebugTrace.NONE,True)
        check('Statue'+str(i+1)+' clear push lane',not hit,{k:str(v) for k,v in hit.to_dict().items()} if hit else None)
    R['actor_count']=len(actors); R['success']=all(c['passed'] for c in R['checks'])
    if not R['success']:raise AssertionError([c['name'] for c in R['checks'] if not c['passed']])
    print('STAGE3_COLD_QA_OK',len(R['checks']))
try:main()
except Exception:R['error']=traceback.format_exc();R['success']=False;raise
finally:(OUT/'cold_qa.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf8')
