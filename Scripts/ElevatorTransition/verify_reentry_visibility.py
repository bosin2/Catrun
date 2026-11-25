"""Apply the final Stage3 cutaway and check actual walking reentry/exit.

Use run_runtime.ps1 -Script verify_reentry_visibility.py; isolated save only.
"""
import json, runpy, time, traceback
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/ElevatorTransition/Runtime'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
GS=u.GameplayStatics
S={'phase':'startup','started':time.monotonic(),'checks':[],'success':False}

def persist():
    (OUT/'reentry_visibility_final.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},indent=2),encoding='utf8')

def check(name,passed):
    S['checks'].append({'name':name,'passed':bool(passed)})
    persist()
    assert passed,name

def phase(name):
    S.update(phase=name,changed=time.monotonic())
    persist()

def shot(world,name):
    u.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')

def finish(error=None):
    S.update(success=error is None,error=error)
    phase('shutdown')
    if ED.get_game_world():LE.editor_request_end_play()

def tick(dt):
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>1:
                u.unregister_slate_post_tick_callback(S['handle'])
                if S['success']:u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        assert time.monotonic()-S['started']<120,'Reentry test timeout'
        world=ED.get_game_world()
        if not world:return
        cat=GS.get_player_character(world,0)
        pc=GS.get_player_controller(world,0)
        directors=GS.get_all_actors_of_class(world,u.CatrunElevatorTransition)
        if not cat or not pc or not directors:return
        d=directors[0]
        if S['phase']=='startup':
            if GS.get_time_seconds(world)<4 or pc.is_move_input_ignored():return
            cat.set_actor_location(u.Vector(150,-110,26.2),False,True)
            phase('walk_in')
        elif S['phase']=='walk_in':
            if cat.get_actor_location().y<155:
                cat.add_movement_input(u.Vector(0,1,0),.3,False)
                return
            cat.character_movement.stop_movement_immediately()
            phase('loaded')
        elif S['phase']=='loaded':
            if time.monotonic()-S['changed']<2:return
            check('real_walk_enters_supported_cabin',d.cabin_weight.has_supported_rider(cat) and cat.character_movement.is_moving_on_ground())
            check('roof_and_camera_side_structure_hides',len(d.cabin_occluders)==4 and all(a.get_editor_property('hidden') for a in d.cabin_occluders))
            check('hidden_panels_keep_blocking_collision',all(a.get_actor_enable_collision() and str(a.static_mesh_component.get_collision_profile_name())=='BlockAll' for a in d.cabin_occluders))
            check('visible_cat_and_floor',not cat.get_editor_property('hidden') and cat.mesh.is_visible() and all(not a.get_editor_property('hidden') for a in d.cabin_weight.support_actors))
            check('gameplay_carries_supported_cat',abs(cat.get_actor_location().z-26.2-d.cabin_weight.get_current_offset())<.7)
            shot(world,'17_ReentryVisibleCat')
            S['loaded_cat']=list(cat.get_actor_location().to_tuple())
            phase('capture')
        elif S['phase']=='capture':
            if time.monotonic()-S['changed']>.3:phase('walk_out')
        elif S['phase']=='walk_out':
            if cat.get_actor_location().y>-110:
                cat.add_movement_input(u.Vector(0,-1,0),.3,False)
                return
            cat.character_movement.stop_movement_immediately()
            phase('empty')
        elif S['phase']=='empty':
            if time.monotonic()-S['changed']<1.5:return
            check('leaving_restores_complete_cabin',all(not a.get_editor_property('hidden') for a in d.cabin_occluders))
            check('persistent_floor_stays_collidable',all(a.get_actor_enable_collision() and not a.get_editor_property('hidden') for a in d.cabin_weight.support_actors))
            check('no_interaction_or_input_lock',d.get_transition_state().name=='FINISHED' and not pc.is_move_input_ignored())
            shot(world,'18_ReentryRestoredCabin')
            phase('final_capture')
        elif S['phase']=='final_capture':
            if time.monotonic()-S['changed']>.3:finish()
    except Exception:finish(traceback.format_exc())

assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
runpy.run_path(str(ROOT/'Scripts/ElevatorTransition/author_revision2.py'),run_name='__main__')
assert LE.load_level('/Game/Maps/Stage3')
u.SystemLibrary.execute_console_command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
S['started']=time.monotonic()
S['handle']=u.register_slate_post_tick_callback(tick)
LE.editor_request_begin_play()
