"""Only changed views: camera near clipping and warehouse basket clearance."""
import importlib.util
import os
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
os.environ.setdefault('CATRUN_STAGE3_AFTER_CAPTURE_PASS', 'After02')
spec = importlib.util.spec_from_file_location('stage3_followup_views', root / 'Scripts/Stage3/IntegrationRevision20261125/capture_after.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
capture.c.VIEWS = [
    ('GateExtreme', (-945, -4545, 26.2)),
    ('GateMiddle', (-250, -3400, 26.2)),
    ('Warehouse', (605, -1215, 26.2)),
]

previous_tick = capture.c.tick


def tick(dt):
    c = capture.c
    if c.S['phase'] == 'shutdown' and not c.ED.get_game_world() and not c.S.get('final_readback'):
        spec = importlib.util.spec_from_file_location('stage3_final_readback', root / 'Scripts/Stage3/GothicRevision/verify.py')
        qa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qa)
        qa.OUT = c.OUT / 'QA'
        qa.snapshot('after')
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        lookup = {a.get_actor_label(): a for a in actors}
        camera = lookup['S3_FollowCamera'].get_component_by_class(u.CameraComponent)
        minimap, = [a for a in actors if a.get_class().get_name() == 'CatrunMinimapPresenter']
        center, size = minimap.get_editor_property('MapCenter'), minimap.get_editor_property('MapSize')
        c.S['final_readback'] = {
            'camera_near_cm': camera.get_editor_property('ortho_near_clip_plane'),
            'camera_far_cm': camera.get_editor_property('ortho_far_clip_plane'),
            'ortho_width_cm': camera.get_editor_property('ortho_width'),
            'minimap_texture': minimap.get_editor_property('BackgroundTexture').get_path_name(),
            'minimap_center': [center.x, center.y],
            'minimap_size': [size.x, size.y],
            'minimap_yaw': minimap.get_editor_property('CaptureYawDegrees'),
            'map_sha256': qa.digest(root / 'Content/Maps/Stage3.umap'),
        }
        c.persist()
    previous_tick(dt)


u.unregister_slate_post_tick_callback(capture.c.S['handle'])
capture.c.S['handle'] = u.register_slate_post_tick_callback(tick)
