"""Sweep the actual runtime cat capsule through the preserved hole and past armor."""
import unreal,time,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Prototype20261104/CanonicalMaps/TutorialPass'
out.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Tutorial')
state={'start':time.monotonic(),'phase':'intro','sweeps':[],'scope':'Runtime cat capsule swept via SetActorLocation, not keyboard locomotion'}
def vec(v):return [v.x,v.y,v.z]
def finish(error=None):
    state['error']=error
    (out/'observations.json').write_text(json.dumps({k:v for k,v in state.items() if k!='handle'},indent=2),encoding='utf8')
    unreal.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play()
def tick(delta):
    try:
        now=time.monotonic();w=editor.get_game_world()
        if now-state['start']>25:finish('timeout');return
        if not w:return
        if state['phase']=='intro' and now-state['start']>2:
            assert unreal.CatrunLevelFlowLibrary.restart_current_stage(w);state['phase']='retry';state['at']=now
        elif state['phase']=='retry' and now-state['at']>4:
            cat=unreal.GameplayStatics.get_player_pawn(w,0)
            for name,a,b in [('cat_hole',(-275,420,26),(-275,510,26)),('corridor_past_armor',(-170,730,26),(-170,885,26))]:
                cat.set_actor_location(unreal.Vector(*a),False,True)
                hit=cat.set_actor_location(unreal.Vector(*b),True,False)
                end=vec(cat.get_actor_location());state['sweeps'].append({'name':name,'start':a,'requested':b,'actual':end,'hit':str(hit)})
                assert sum((end[i]-b[i])**2 for i in range(3))<.01,state['sweeps'][-1]
            cat.set_actor_location(unreal.Vector(-170,805,26),False,True)
            state['phase']='render';state['at']=now
        elif state['phase']=='render' and now-state['at']>2:
            unreal.SystemLibrary.execute_console_command(w,'Shot showui filename="'+str(out/'armor-pass.png').replace('\\','/')+'"');state['phase']='finish';state['at']=now
        elif state['phase']=='finish' and now-state['at']>1:finish()
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play()
