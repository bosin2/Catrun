"""Disposable GPU comparison of unchanged original iron and corrected iron."""
import json
import math
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3MaterialCorrection20261125/QA'
report={'rows':[],'scope':'Original vs corrected iron, identical UV plane and capture; no asset saves.'}
assert u.SystemLibrary.is_unattended()
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
ea=u.get_editor_subsystem(u.EditorActorSubsystem)
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
actors=[]
try:
    plane=ea.spawn_actor_from_class(u.StaticMeshActor,u.Vector(0,0,10000),transient=True);actors.append(plane)
    plane.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane.Plane'))
    camera=ea.spawn_actor_from_class(u.SceneCapture2D,u.Vector(0,0,10100),u.Rotator(pitch=-90),transient=True);actors.append(camera)
    c=camera.get_component_by_class(u.SceneCaptureComponent2D)
    for name,value in [('capture_every_frame',False),('capture_on_movement',False),
                       ('projection_type',u.CameraProjectionMode.ORTHOGRAPHIC),('ortho_width',100.0),
                       ('capture_source',u.SceneCaptureSource.SCS_BASE_COLOR),
                       ('primitive_render_mode',u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)]:
        c.set_editor_property(name,value)
    c.clear_show_only_components();c.show_only_component(plane.static_mesh_component)
    for resolution in (256,1024):
        target=u.RenderingLibrary.create_render_target2d(world,resolution,resolution,u.TextureRenderTargetFormat.RTF_RGBA16F,u.LinearColor(0,0,0,0),False)
        c.set_editor_property('texture_target',target)
        for kind,path in [('original','/Game/Environment/Stage3/FinalGuard/Materials/M_S3_iron.M_S3_iron'),
                          ('corrected','/Game/Environment/Stage3/ColorCorrection_20261125/Instances/MI_CC_BlackIron_S3_iron_f0f5dfad.MI_CC_BlackIron_S3_iron_f0f5dfad')]:
            plane.static_mesh_component.set_material(0,u.load_asset(path))
            assert u.CatrunAuthoringLibrary.finish_asset_compilation()
            c.capture_scene()
            pixels=u.RenderingLibrary.read_render_target_raw_pixel_area(world,target,0,0,resolution,resolution,False)
            assert len(pixels)==resolution*resolution
            sums=[0.,0.,0.];squares=[0.,0.,0.];unique=[set(),set(),set()]
            for p in pixels:
                for i,x in enumerate((p.r,p.g,p.b)):
                    sums[i]+=x;squares[i]+=x*x;unique[i].add(x)
            mean=[v/len(pixels) for v in sums]
            std=[math.sqrt(max(0.,s/len(pixels)-m*m)) for s,m in zip(squares,mean)]
            row={'kind':kind,'material':path,'resolution':resolution,'mean_linear':mean,'std_linear':std,'unique_per_channel':[len(x) for x in unique]}
            report['rows'].append(row)
            print('IRON_DETAIL_GPU',row)
            (OUT/'iron_detail_gpu.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        u.RenderingLibrary.release_render_target2d(target)
finally:
    for actor in reversed(actors):ea.destroy_actor(actor)
    (OUT/'iron_detail_gpu.json').write_text(json.dumps(report,indent=2),encoding='utf8')
