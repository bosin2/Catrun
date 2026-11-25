"""Read-only real possessed camera poses for the gate pillar revision."""
import importlib.util
import os
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
os.environ['CATRUN_GOTHIC_CAPTURE'] = 'before'
os.environ['CATRUN_GOTHIC_LIT_ONLY'] = '1'
os.environ.pop('CATRUN_GOTHIC_VIEWS', None)
os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC', None)
spec = importlib.util.spec_from_file_location('gate_pillar_capture', ROOT / 'Scripts/Stage3/GothicRevision/capture.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.OUT = ROOT / 'Saved/Stage3IntegrationRevision20261125/GateBefore'
c.OUT.mkdir(parents=True, exist_ok=True)
c.VIEWS = [('GateEntrance', (-250,-3030,26.2)), ('GateMiddle', (-250,-3400,26.2)),
           ('GateNorthWest', (-870,-3820,26.2)), ('GateNorthEast', (370,-3820,26.2))]
previous = c.tick

def inspect_components(world):
    result = []
    for actor in c.GS.get_all_actors_of_class(world,u.Actor):
        for camera in actor.get_components_by_class(u.CameraComponent):
            row = {'actor':actor.get_actor_label(), 'component':camera.get_name()}
            for key in ('projection_mode','ortho_width','aspect_ratio','constrain_aspect_ratio',
                        'ortho_near_clip_plane','ortho_far_clip_plane','auto_calculate_ortho_planes','auto_plane_shift'):
                try:
                    value=camera.get_editor_property(key)
                    row[key]=value if isinstance(value,(float,int,bool,str)) else str(value)
                except Exception as error:
                    row[key]={'unavailable':str(error)}
            row['position']=c.vec(camera.get_world_location())
            rot=camera.get_world_rotation()
            row['rotation']=[rot.pitch,rot.yaw,rot.roll]
            result.append(row)
    return result

def tick(dt):
    world=c.ED.get_game_world()
    if world and not c.S.get('camera_components') and c.GS.get_time_seconds(world)>3:
        c.S['camera_components']=inspect_components(world)
    previous(dt)

u.unregister_slate_post_tick_callback(c.S['handle'])
c.S['handle']=u.register_slate_post_tick_callback(tick)
