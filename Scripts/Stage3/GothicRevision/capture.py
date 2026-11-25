"""All-zone real possessed player-camera evidence in disposable PIE only."""
import json, os, time, traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
PHASE=os.environ.get('CATRUN_GOTHIC_CAPTURE','before')
assert PHASE in ('before','after')
OUT=ROOT/'Saved/Stage3GothicRevision20261125'/os.environ.get('CATRUN_GOTHIC_CAPTURE_PASS',PHASE)
OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
GS=u.GameplayStatics
VIEWS=[('Entrance',(150,110,26.2)),('Lobby',(-100,600,26.2)),
       ('LowerHall',(0,1120,26.2)),('Exhibition',(-650,1880,26.2)),
       ('Warehouse',(850,1090,26.2)),('CentralCorridor',(400,1650,26.2)),
       ('CatBypass',(850,1870,26.2)),('AltarAnnex',(225,1875,26.2)),('Altar',(450,2250,26.2)),
       ('UpperCorridor',(-200,2700,26.2)),('GateHall',(-200,3450,26.2)),
       ('GateHallExit',(-200,3800,26.2)),('Weight1',(-660,2150,26.2))]
if os.environ.get('CATRUN_GOTHIC_VIEWS'):
    names=os.environ['CATRUN_GOTHIC_VIEWS'].split(',')
    assert set(names)<=set(name for name,_ in VIEWS)
    VIEWS=[row for row in VIEWS if row[0] in names]
MODES=['Lit'] if PHASE=='before' or os.environ.get('CATRUN_GOTHIC_LIT_ONLY')=='1' else ['Lit','BaseColor','DetailLighting']
MODE_COMMANDS={'Lit':'Lit','BaseColor':'VisualizeBuffer','DetailLighting':'Lit_DetailLighting'}
if os.environ.get('CATRUN_GOTHIC_DIAGNOSTIC')=='1':
    MODES=['Lit','NoShadows','Roughness','Metallic','WorldNormal']
    MODE_COMMANDS.update({'NoShadows':'Lit','Roughness':'VisualizeBuffer','Metallic':'VisualizeBuffer','WorldNormal':'VisualizeBuffer'})
S={'phase':'startup','index':0,'mode':0,'started':time.monotonic(),'views':[],
   'compilation_barriers':[], 'mode_commands':MODE_COMMANDS,
   'readiness_policy':'After 3 PIE game seconds: FinishAll, 10 wall seconds and 60 Slate callbacks warmup, FinishAll; after each view/mode renders: FinishAll then 2 seconds and 30 callbacks',
   'fixture':'Actual player camera; fixed cat poses, NPC tick stopped after 3 game seconds; no package saved',
   'command_line':u.SystemLibrary.get_command_line()}
def vec(v):return [v.x,v.y,v.z]
def persist():
    (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},indent=2),encoding='utf8')
def command(w,txt):u.SystemLibrary.execute_console_command(w,txt)
def compile_barrier(w,reason):
    # This synchronous engine command includes FShaderCompilingManager, whose
    # FinishAllCompilation blocks shader jobs AND processes pending shader maps.
    # Calling before PIE cannot cover permutations first requested by PIE views.
    started=time.monotonic()
    command(w,'Editor.AsyncAssetCompilationFinishAll')
    S['compilation_barriers'].append({'reason':reason,'game_seconds':GS.get_time_seconds(w),
        'wall_seconds':time.monotonic()-started,'returned':True})
    print('GOTHIC_CAPTURE_COMPILATION_BARRIER',reason)
    persist()
def finish(error=None):
    S['success']=error is None; S['error']=error; S['phase']='shutdown';S['changed']=time.monotonic();persist()
    w=ED.get_game_world()
    if w:GS.set_game_paused(w,False);LE.editor_request_end_play()
def tick(_dt):
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>1:
                u.unregister_slate_post_tick_callback(S['handle']);command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        assert time.monotonic()-S['started']<900,'Capture timeout'
        w=ED.get_game_world()
        if not w:return
        cat=GS.get_player_character(w,0)
        if not cat:return
        if S['phase']=='startup':
            if GS.get_time_seconds(w)<3:return
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            for a in list(GS.get_all_actors_of_class(w,u.CatrunArmor))+list(GS.get_all_actors_of_class(w,u.CatrunCandle)):
                a.set_actor_tick_enabled(False)
            pc=GS.get_player_controller(w,0)
            assert pc,'Missing possessed player controller'
            if not pc.get_editor_property('cheat_manager'):command(w,'EnableCheats')
            S['viewmode_cheat_manager_present']=bool(pc.get_editor_property('cheat_manager'))
            assert S['viewmode_cheat_manager_present'],'VIEWMODE silently ignored without CheatManager'
            compile_barrier(w,'PIE first-render after 3 game seconds')
            S['changed']=time.monotonic();S['warmup_ticks']=0;S['phase']='warmup';return
        if S['phase']=='warmup':
            S['warmup_ticks']+=1
            if time.monotonic()-S['changed']<10 or S['warmup_ticks']<60:return
            S['initial_warmup_wall_seconds']=time.monotonic()-S['changed']
            compile_barrier(w,'PIE rendered warmup complete')
            S['phase']='position'
        if S['phase']=='position':
            GS.set_game_paused(w,False)
            cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
            cat.set_actor_location(u.Vector(*VIEWS[S['index']][1]),False,True)
            cat.set_actor_rotation(u.Rotator(yaw=90),True)
            S['game_at']=GS.get_time_seconds(w);S['phase']='settle';return
        if S['phase']=='settle':
            if GS.get_time_seconds(w)-S['game_at']<3:return
            compile_barrier(w,VIEWS[S['index']][0]+' positioned view')
            GS.set_game_paused(w,True);S['mode']=0;S['phase']='mode'
        if S['phase']=='mode':
            mode=MODES[S['mode']]
            if os.environ.get('CATRUN_GOTHIC_DIAGNOSTIC')=='1':
                command(w,'ShowFlag.DynamicShadows '+('0' if mode=='NoShadows' else '1'))
            if mode in ('BaseColor','Roughness','Metallic','WorldNormal'):
                command(w,'viewmode '+MODE_COMMANDS[mode]);command(w,'r.BufferVisualizationTarget '+mode)
            else:
                command(w,'r.BufferVisualizationTarget None')
                command(w,'viewmode '+MODE_COMMANDS[mode])
            # Query emits actual current view mode to the process log. The JSON
            # command records are requests, not a substitute for log/image QA.
            command(w,'viewmode')
            S['changed']=time.monotonic();S['mode_ticks']=0;S['phase']='mode_render';return
        if S['phase']=='mode_render':
            S['mode_ticks']+=1
            if time.monotonic()-S['changed']<1.2 or S['mode_ticks']<30:return
            compile_barrier(w,VIEWS[S['index']][0]+' '+MODES[S['mode']]+' first rendered')
            S['changed']=time.monotonic();S['mode_ticks']=0;S['phase']='mode_settle';return
        if S['phase']=='mode_settle':
            S['mode_ticks']+=1
            if time.monotonic()-S['changed']<2 or S['mode_ticks']<30:return
            name=VIEWS[S['index']][0];mode=MODES[S['mode']]
            camera=GS.get_player_camera_manager(w,0);r=camera.get_camera_rotation()
            S['views'].append({'name':name,'mode':mode,'cat':vec(cat.get_actor_location()),
                'camera':vec(camera.get_camera_location()),'rotation':[r.pitch,r.yaw,r.roll],
                'mode_command':MODE_COMMANDS[mode], 'post_compilation_settle_seconds':time.monotonic()-S['changed'],
                'post_compilation_slate_callbacks':S['mode_ticks']})
            command(w,'HighResShot 1280x720 filename="'+str(OUT/(name+'_'+mode+'.png'))+'"')
            S['changed']=time.monotonic();S['phase']='capture';persist();return
        if S['phase']=='capture' and time.monotonic()-S['changed']>1.2:
            name=VIEWS[S['index']][0]+'_'+MODES[S['mode']]+'.png'
            assert (OUT/name).exists() and (OUT/name).stat().st_size>2048,name
            S['mode']+=1
            if S['mode']<len(MODES):S['phase']='mode'
            else:
                S['index']+=1
                if S['index']==len(VIEWS):finish()
                else:S['phase']='position'
    except Exception:finish(traceback.format_exc())
assert '-SaveToUserDir' in S['command_line']
assert LE.load_level('/Game/Maps/Stage3')
command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
S['started']=time.monotonic();S['handle']=u.register_slate_post_tick_callback(tick)
try:LE.editor_request_begin_play()
except Exception:finish(traceback.format_exc())
