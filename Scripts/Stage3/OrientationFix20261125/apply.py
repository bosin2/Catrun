"""One-time actual-map Y reflection with native interactive assemblies rebuilt rigidly.

Canonical plan +X=right,+Y=up becomes Unreal +X=right,-Y=up when viewed
from north (yaw -90). This changes the saved map, never flips a screenshot.
Root is the only live-editor writer. Run only after probe.py.
"""
import json,sys,re,importlib,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3OrientationFix20261125'
OWNER='Stage3ReferenceOrientationYMinus20261125'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
assert not ED.get_game_world()
assert (OUT/'probe.json').exists() and not (OUT/'applied.json').exists()
actors=list(ACT.get_all_level_actors());lookup={a.get_actor_label():a for a in actors}
assert all(a.get_actor_label().startswith('S3_') for a in actors)
assert not any(OWNER in map(str,a.tags) for a in actors),'Already transformed'
before={a.get_actor_label():a.get_actor_transform() for a in actors}
bounds={a.get_actor_label():a.get_actor_bounds(False,False) for a in actors}
def flip(v):return u.Vector(v.x,-v.y,v.z)
def vec(v):return [v.x,v.y,v.z]
def reflect_rotation(q):return u.Quat(-q.x,q.y,-q.z,q.w)
def depth(a):
    n=0;p=a.get_attach_parent_actor()
    while p:n+=1;p=p.get_attach_parent_actor()
    return n
def release_number(label):
    m=re.match(r'S3_Release([123])_',label) or re.match(r'S3_GothicConnections_E([123])_',label)
    return int(m.group(1)) if m else None
R={'success':False,'coordinate_transform':'(x,y,z) -> (x,-y,z)','actors':[],'geometry_bounds_checks':[]}
try:
    for a in sorted(actors,key=depth):
        label=a.get_actor_label();t=before[label];p=t.translation;q=t.rotation;s=t.scale3d
        n=release_number(label)
        if n:
            h=before['S3_Release%d_Housing'%n].translation
            delta=p-h
            target=flip(h)+u.Vector(-delta.x,-delta.y,delta.z)
            rotation=(u.Rotator(yaw=180).quaternion()*q).rotator()
            scale=s
            mode='positive-handed rigid release assembly'
        else:
            target=flip(p);rotation=reflect_rotation(q).rotator();scale=s
            if isinstance(a,u.StaticMeshActor):scale=u.Vector(s.x,-s.y,s.z)
            mode='exact static reflection' if isinstance(a,u.StaticMeshActor) else 'positive-handed actor pose'
        # Native lock withdrawal uses rotation-only local Z (= world X).
        # Keep lock assembly chirality; its form is symmetric across local Y.
        if label.startswith(('S3_Lock','S3_GothicVisual_Lock')):
            scale=s;rotation=reflect_rotation(q).rotator();mode='native lock pose'
        a.set_actor_transform(u.Transform(location=target,rotation=rotation,scale=scale),False,True)
        R['actors'].append({'label':label,'mode':mode,'before':t.export_text(),'after':a.get_actor_transform().export_text()})
    for a in actors:
        label=a.get_actor_label()
        if label.startswith('S3_GothicPresentation_Dock'):
            for key in ('ForkOpen','ForkClosed','PinOpen','PinLowered','PinClosed','ChainTerminalOpen','ChainTerminalClosed'):
                a.set_editor_property(key,flip(a.get_editor_property(key)))
        if isinstance(a,u.CatrunCandle):
            points=a.get_editor_property('PatrolRelativePoints')
            a.set_editor_property('PatrolRelativePoints',[flip(p) for p in points])
    # SocketAxis selects an unsigned cardinal axis in native InitializePuzzle
    # (abs X vs abs Y). Keep the saved links verbatim; reflection preserves Y axis.
    puzzle=lookup['S3_StatuePuzzles']
    reveal=puzzle.get_editor_property('Reveal')
    reveal.set_editor_property('GateCameraOffset',flip(reveal.get_editor_property('GateCameraOffset')))
    exit_actor=lookup['S3_FinalExit']
    exit_actor.set_editor_property('InteriorDirectionLocal',flip(exit_actor.get_editor_property('InteriorDirectionLocal')))
    # Check exact architectural footprints before changing any shading or saving.
    for a in actors:
        label=a.get_actor_label()
        if not label.startswith(('S3_Floor_','S3_Wall_','S3_D0_Frame','S3_D1_Frame','S3_D2_Frame','S3_H')):continue
        if not isinstance(a,u.StaticMeshActor):continue
        oldc,olde=bounds[label];c,e=a.get_actor_bounds(False,False)
        error=max((c-flip(oldc)).length(),(e-olde).length())
        assert error<.05,(label,error)
        R['geometry_bounds_checks'].append({'label':label,'error_cm':error})
    assert abs(lookup['S3_FollowCamera'].get_actor_rotation().yaw+45)<.001
    assert lookup['S3_Player'].get_actor_scale3d().y>0
    assert all(lookup['S3_Release%d_Housing'%i].get_actor_scale3d().y>0 for i in (1,2,3))
    sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
    import floor_recess,occlusion,camera
    for m in (floor_recess,occlusion,camera):importlib.reload(m)
    R['floor_recess']=floor_recess.apply()
    R['cutaway']=occlusion.apply()
    R['camera']=camera.apply()
    grid=lookup['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
    R['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
    R['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in actors if isinstance(a,u.StaticMeshActor)]
    lookup['S3_Objectives'].tags=list(lookup['S3_Objectives'].tags)+[u.Name(OWNER)]
    assert LE.save_current_level()
    R['success']=True
    (OUT/'applied.json').write_text(json.dumps(R,indent=2),encoding='utf8')
    print('STAGE3_ORIENTATION_SAVED',len(actors),len(R['geometry_bounds_checks']))
except Exception:
    R['error']=traceback.format_exc();(OUT/'attempt_error.json').write_text(json.dumps(R,indent=2),encoding='utf8');raise
