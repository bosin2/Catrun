"""API-stage near A threshold, then observe actual keyboard-driven native Tick.

No TryPushStatue/UpdatePlates call, no AI/director Tick or collision disabling.
"""
import json,time,traceback
from pathlib import Path
import unreal
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task5/PhysicalStatue01'
OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'observations.json').exists()
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
def v(x): return [x.x,x.y,x.z]
def setup():
    w=ed.get_game_world(); assert w and w.get_name().endswith('Stage2')
    cat=unreal.GameplayStatics.get_player_pawn(w,0); pc=unreal.GameplayStatics.get_player_controller(w,0)
    assert not pc.is_move_input_ignored()
    d=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle)[0]
    l=d.get_editor_property('Links')[0]; statue=l.get_editor_property('Statue'); plate=l.get_editor_property('Plate').get_actor_location()
    pos=unreal.Vector(plate.x,plate.y+29.05,statue.get_actor_location().z)
    statue.set_actor_location(pos,False,True)
    target=pos+unreal.Vector(0,83,0);target.z=26.25
    cap=cat.get_component_by_class(unreal.CapsuleComponent)
    hit=unreal.SystemLibrary.capsule_trace_single_by_profile(w,target,target+unreal.Vector(0,0,.1),cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height(),'Pawn',False,[cat],unreal.DrawDebugTrace.NONE,False)
    assert not hit, str(hit.to_dict()) if hit else ''
    cat.set_actor_location(target,False,True)
    return {'start':time.monotonic(),'scope':'API checkpoint at 79.958 percent; OS movement keys then normal native Tick, no push API','before':v(pos),'cat_start':v(target),'ratio':d.get_seating_overlap(0),'samples':[],'shots':[],'camera_rotation':str(pc.player_camera_manager.get_camera_rotation())}
state=setup()
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    data={k:v for k,v in state.items() if k!='handle'}; data['error']=error
    (OUT/'observations.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print('PHYSICAL_STATUE_DONE',error)
def tick(dt):
    try:
        t=time.monotonic()-state['start'];w=ed.get_game_world();assert w
        cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0)
        d=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle)[0]
        l=d.get_editor_property('Links')[0];r=d.get_editor_property('Reveal');phase=r.get_editor_property('Phase').name
        row={'t':t,'dt':dt,'cat':v(cat.get_actor_location()),'input':v(cat.get_last_movement_input_vector()),'statue':v(l.get_editor_property('Statue').get_actor_location()),'ratio':d.get_seating_overlap(0),'pressed':l.get_editor_property('bPressed'),'complete':l.get_editor_property('bCompleted'),'gate_offset':l.get_editor_property('GateOffset'),'phase':phase,'move_ignored':pc.is_move_input_ignored(),'view':pc.get_view_target().get_name()}
        if t-state.get('last',-1)>.02:state['samples'].append(row);state['last']=t
        if phase not in state['shots'] and (phase!='INACTIVE' or row['complete']):
            state['shots'].append(phase);unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(phase+'.png')).replace('\\','/')+'"')
        if row['complete'] and phase=='INACTIVE':
            assert not row['move_ignored'] and row['gate_offset']<=-279
            assert any(sum(abs(x) for x in s['input'])>.01 for s in state['samples']), 'No physical input observed'
            assert 'TO_GATE' in state['shots'] and 'OPENING' in state['shots']
            finish();return
        if t>65: finish('Timeout waiting for OS push or completion')
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('PHYSICAL_STATUE_ARMED',json.dumps({k:v for k,v in state.items() if k not in ('handle','samples')}))
