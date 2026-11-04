"""Read-only current-session motion sample before the renewed repair request."""
import unreal, json, time, traceback
from datetime import datetime
from pathlib import Path
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = Path(unreal.Paths.project_saved_dir()) / 'Prototype20261104' / 'PlayabilityRepair'
out.mkdir(exist_ok=True)
output_file=out/('entry-motion-'+datetime.now().strftime('%H%M%S-%f')+'.json')
state = {'start': time.monotonic(), 'samples': [], 'entry_dirty':
         [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] +
         [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    output_file.write_text(json.dumps({k:v for k,v in state.items() if k!='handle'} | {'error':error}, indent=2), encoding='utf8')
    print('REPAIR_ENTRY_DONE', str(output_file), str(error))
def tick(dt):
    try:
        now=time.monotonic()
        if now-state.get('last',0)<.25: return
        state['last']=now
        w=ed.get_game_world()
        editor_world=ed.get_editor_world()
        row={'wall':now-state['start'],'editor_world':editor_world.get_path_name() if editor_world else None,'game_world':w.get_path_name() if w else None}
        if w:
            row.update(game=unreal.GameplayStatics.get_time_seconds(w),paused=unreal.GameplayStatics.is_game_paused(w),suspended=unreal.CatrunPuzzleSuspension.is_suspended(w))
            managers=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.SoundGridManager)
            row['managers']=[a.get_path_name() for a in managers]
            settings=managers[0].get_editor_property('Settings') if managers else None
            row['settings']={n:settings.get_editor_property(n) for n in ['CandleSweepSpeed','CandleTotalAngle','CandleConeAngle','CandleRange','ArmorDetectRadius','CatSightRadius']} if settings else None
            row['candles']=[]
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunCandle):
                body=a.get_editor_property('Body'); inst=body.get_anim_instance()
                rot=body.get_world_rotation(); at=a.get_actor_location()
                row['candles'].append({'path':a.get_path_name(),'tick':a.is_actor_tick_enabled(),'location':[at.x,at.y,at.z],
                    'body_rotation':[rot.pitch,rot.yaw,rot.roll],'tracking':a.is_tracking_cat(),
                    'anim_class':inst.get_class().get_name() if inst else None,
                    'anim_position':body.get_position() if isinstance(inst,unreal.AnimSingleNodeInstance) else None,
                    'idle':a.get_editor_property('IdleAnim').get_path_name() if a.get_editor_property('IdleAnim') else None,
                    'body_tick':body.is_component_tick_enabled(),'pause_anims':body.get_editor_property('bPauseAnims')})
        state['samples'].append(row)
        if not w or now-state['start']>=8: finish()
    except Exception: finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('REPAIR_ENTRY_ARMED', str(out))
