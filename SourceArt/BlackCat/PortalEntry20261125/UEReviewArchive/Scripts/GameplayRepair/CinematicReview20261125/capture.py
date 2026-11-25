"""Continuous PIE backbuffer capture, using the existing portal integration probe.

Run in an isolated normal editor with -RenderOffscreen -UseFixedTimeStep -FPS=30
-SaveToUserDir -UserDir=<isolated directory>. No content or map packages are saved.
The fixture enters the real exit trigger; it does not invoke cinematic completion.
"""
from pathlib import Path
import datetime
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/GameplayRepair'))
command = u.SystemLibrary.get_command_line().lower()
assert '-renderoffscreen' in command
assert '-savetouserdir' in command and '-userdir=' in command
assert '-usefixedtimestep' in command and '-fps=30' in command
RUN = ROOT / 'Saved/CinematicReview20261125' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
RUN.mkdir(parents=True, exist_ok=False)
(ROOT / 'Saved/CinematicReview20261125/latest.txt').write_text(str(RUN), encoding='utf-8')

source = (ROOT / 'Scripts/GameplayRepair/verify_stage2_arrival_runtime.py').read_text(encoding='utf-8')


def replace_once(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


replace_once("OUT=Path(u.Paths.project_saved_dir()).resolve()/'StageRevision20261123/ArrivalRuntime'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')", 'OUT=RUN')
replace_once('OUT.mkdir(parents=True,exist_ok=False)', '# Output already created by the wrapper.')
replace_once("    u.SystemLibrary.execute_console_command(world,f'Shot filename=\"{location}\"',pc)",
             "    assert u.CatrunAuthoringLibrary.capture_game_viewport(world,location), location")
replace_once("    entry={'shot':stem,'world':world.get_path_name()", 
             "    entry={'capture_method':'PIE viewport direct readback','shot':stem,'world':world.get_path_name()")
replace_once("capture=stage.endswith('Stage2') and phase in ('portal','arrival','one-shot')", "capture=phase in ('portal','arrival','one-shot')")
replace_once("if now-STATE['start']>480:", "if now-STATE['start']>1800:")
replace_once("'ear_tip_R','paw_f_l','paw_f_r')", "'ear_tip_R','ear_L','ear_R','neck','chest','scapula_L','scapula_R','paw_f_l','paw_f_r','paw_h_l','paw_h_r','thigh_L','thigh_R','hock_L','hock_R','tail_01','tail_07')")
replace_once("                    if departure and departure.get_current_time().time.frame_number.value>=departure.get_sequence().get_playback_end()-12:\n                        viewport_frame(world,pc,cat,'departure-end')", """                    if departure and image:
                        at=departure.get_current_time().time
                        image['frame']=round(at.frame_number.value+at.sub_frame)
                        image['sequence']='departure'
                        image['visual']=cat_image_state(cat)
                        image['cat_root']=xyz(cat.get_actor_location())
                        image['viewport_size']=list(pc.get_viewport_size())
                        image['visual']['screen_bones']={}
                        for name,point in image['visual']['bones'].items():
                            screen=pc.project_world_location_to_screen(u.Vector(*point),True)
                            image['visual']['screen_bones'][name]=[screen.x,screen.y] if screen else None
                        mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
                        image['visual']['ear_rotations']={}
                        for name in ('ear_L','ear_R','head'):
                            rot=mesh.get_socket_rotation(name)
                            image['visual']['ear_rotations'][name]=[rot.pitch,rot.yaw,rot.roll]
                        image['sequence_end']=departure.get_sequence().get_playback_end()
                        ripple=next((b for b in departure.get_sequence().get_bindings() if b.get_name()=='PawContactRipple'),None)
                        if ripple:
                            objects=departure.get_bound_objects(departure.get_sequence().get_binding_id(ripple))
                            image['ripple']=[{'location':xyz(obj.get_actor_location()),'collision':obj.get_actor_enable_collision()} for obj in objects]""")
replace_once("                    image['frame']=f", """                    at=player.get_current_time().time
                    image['frame']=round(at.frame_number.value+at.sub_frame)
                    image['sequence']='arrival'
                    visual_binding=next(b for b in player.get_sequence().get_bindings() if b.get_name()=='CosmeticCat')
                    visuals=player.get_bound_objects(player.get_sequence().get_binding_id(visual_binding))
                    if visuals:
                        image['visual']=cat_image_state(visuals[0])""")
replace_once("                STATE['move_end']=xyz(cat.get_actor_location())", """                STATE['move_end']=xyz(cat.get_actor_location())
                if '-cinematicfullregression' not in command:
                    finish()
                    return""")

exec(compile(source, str(ROOT / 'Scripts/GameplayRepair/verify_stage2_arrival_runtime.py'), 'exec'), globals())
