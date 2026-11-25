"""Saved Stage3 camera X-side reversal: actual possessed-camera check and capture."""
import importlib.util,os
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
os.environ['CATRUN_GOTHIC_CAPTURE']='after'
os.environ['CATRUN_GOTHIC_LIT_ONLY']='1'
os.environ.pop('CATRUN_GOTHIC_VIEWS',None);os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC',None)
spec=importlib.util.spec_from_file_location('stage3_x_camera',ROOT/'Scripts/Stage3/GothicRevision/capture.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
c.OUT=ROOT/'Saved/Stage3CameraXReverse20261125/Visual';c.OUT.mkdir(parents=True,exist_ok=True)
c.VIEWS=[('Entrance',(150,-110,26.2)),('GateHall',(-250,-3400,26.2))]
previous=c.tick
def tick(dt):
    w=c.ED.get_game_world()
    if w and not c.S.get('camera_x_verified') and c.GS.get_time_seconds(w)>3:
        yaw=c.GS.get_player_camera_manager(w,0).get_camera_rotation().yaw
        if abs(yaw+135)>.1:c.finish('Wrong saved gameplay camera yaw: '+str(yaw));return
        c.S['camera_x_verified']=True;c.S['actual_gameplay_yaw']=yaw
    previous(dt)
u.unregister_slate_post_tick_callback(c.S['handle'])
c.S['handle']=u.register_slate_post_tick_callback(tick)
