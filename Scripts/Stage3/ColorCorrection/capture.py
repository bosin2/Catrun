"""Compare Stage3 using its real possessed player camera in isolated PIE.

Transient fixture: fixed cat positions, stopped NPC ticks and no capture. No
package is saved. Material/lighting changes are performed by separate scripts.
"""
import json, os, time, traceback
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
PHASE=os.environ.get('CATRUN_STAGE3_COLOR_CAPTURE','before')
assert PHASE in ('before','materials','after','readability')
OUT=ROOT/'Saved/Stage3MaterialCorrection20261125'/PHASE
OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
GS=u.GameplayStatics
VIEWS=[('Entrance',(150,110,26.2)),('Lobby',(100,350,26.2)),
       ('Exhibition',(-650,1800,26.2)),('Warehouse',(850,1100,26.2)),
       ('Altar',(450,2250,26.2)),('GateHall',(-200,3400,26.2))]
if PHASE == 'readability':
    VIEWS = [('GateHallShade',(-200,3800,26.2)),
             ('GateHallUpper',(-200,4050,26.2)),('LobbyClear',(100,580,26.2))]
S={'phase':'startup','index':0,'started':time.monotonic(),'views':[],
   'scope':__doc__,'capture_phase':PHASE,'command_line':u.SystemLibrary.get_command_line()}

def vec(v):return [float(v.x),float(v.y),float(v.z)]
def persist():
    (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')

def finish(error=None):
    S['success']=error is None;S['error']=error;S['phase']='shutdown';S['changed']=time.monotonic();persist()
    w=ED.get_game_world()
    if w:GS.set_game_paused(w,False);LE.editor_request_end_play()

def tick(dt):
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>.5:
                u.unregister_slate_post_tick_callback(S['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        assert time.monotonic()-S['started']<240,'Capture timeout'
        w=ED.get_game_world()
        if not w:return
        cat=GS.get_player_character(w,0)
        if not cat:return
        if S['phase']=='startup':
            if GS.get_time_seconds(w)<3:return
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            for a in list(GS.get_all_actors_of_class(w,u.CatrunArmor))+list(GS.get_all_actors_of_class(w,u.CatrunCandle)):
                a.set_actor_tick_enabled(False)
            S['phase']='position'
        if S['phase']=='position':
            name,position=VIEWS[S['index']]
            GS.set_game_paused(w,False)
            cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
            cat.set_actor_location(u.Vector(*position),False,True)
            cat.set_actor_rotation(u.Rotator(yaw=90),True)
            S['game_at']=GS.get_time_seconds(w);S['phase']='settle';return
        if S['phase']=='settle':
            if GS.get_time_seconds(w)-S['game_at']<2:return
            name,position=VIEWS[S['index']]
            camera=GS.get_player_camera_manager(w,0)
            rotation=camera.get_camera_rotation()
            assert abs(rotation.yaw-45)<.05,('Unexpected camera yaw',str(rotation))
            GS.set_game_paused(w,True)
            row={'name':name,'requested_cat':position,'cat':vec(cat.get_actor_location()),
                 'camera':vec(camera.get_camera_location()),
                 'rotation':[rotation.pitch,rotation.yaw,rotation.roll],
                 'world':w.get_path_name(),'game_seconds':GS.get_time_seconds(w)}
            S['views'].append(row);persist()
            u.SystemLibrary.execute_console_command(w,'HighResShot 1280x720 filename="'+str(OUT/(name+'.png'))+'"')
            S['changed']=time.monotonic();S['phase']='capture';return
        if S['phase']=='capture' and time.monotonic()-S['changed']>1:
            name,_=VIEWS[S['index']]
            p=OUT/(name+'.png');assert p.exists() and p.stat().st_size>2048,name
            S['index']+=1
            if S['index']==len(VIEWS):finish()
            else:S['phase']='position'
    except Exception:finish(traceback.format_exc())

assert '-SaveToUserDir' in S['command_line']
S['handle']=u.register_slate_post_tick_callback(tick)
try:
    assert LE.load_level('/Game/Maps/Stage3')
    # New material shaders must be ready before any screenshot. The native
    # commandlet helper intentionally refuses normal editor processes; this
    # engine console command calls the same asset compilation manager here.
    u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')
    S['compilation_wait_completed'] = True
    S['started'] = time.monotonic()
    print('STAGE3_CAPTURE_ASSET_COMPILATION_READY')
    LE.editor_request_begin_play()
except Exception:finish(traceback.format_exc())
