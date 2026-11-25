"""Final saved-map native regression plus live visibility/rug/camera contracts."""
import importlib.util,os
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
spec=importlib.util.spec_from_file_location('gothic_final_native',ROOT/'Scripts/Stage3/GothicRevision/regression.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
test=suite.test
test.OUT=ROOT/'Saved/Stage3GothicRevision20261125'/os.environ.get('CATRUN_GOTHIC_REGRESSION_PASS','RegressionFinal')
test.OUT.mkdir(parents=True,exist_ok=True)
previous=test.step
seen=set()
def verify_devices(world,phase):
    lookup={a.get_actor_label():a for a in test.GS.get_all_actors_of_class(world,u.Actor)}
    for n in (1,2,3):
        for part in ('Housing','Ring','Pin'):
            label='S3_Release%d_%s'%(n,part)
            component=lookup[label].static_mesh_component
            opaque=all(component.get_material(i).get_base_material().get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE for i in range(component.get_num_materials()))
            visible=component.get_editor_property('visible') and not component.get_editor_property('hidden_in_game')
            test.check('%s %s remains visible and opaque'%(phase,label),opaque and visible)
    for label in ('S3_D0','S3_D0_Frame','S3_D1_Frame','S3_D1_Bars','S3_D2_Frame','S3_D2_Bars','S3_FinalGate_Leaf_L','S3_FinalGate_Leaf_R'):
        component=lookup[label].get_component_by_class(u.StaticMeshComponent)
        opaque=all(component.get_material(i).get_base_material().get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE for i in range(component.get_num_materials()))
        test.check('%s %s remains opaque'%(phase,label),opaque)
def step(world):
    phase=test.S['phase']
    if phase=='observe' and 'initial' not in seen:
        seen.add('initial');verify_devices(world,'Before interaction')
        lookup={a.get_actor_label():a for a in test.GS.get_all_actors_of_class(world,u.Actor)}
        rug=lookup['S3_GothicRug_GrandGate'].static_mesh_component
        test.check('Grand rug runtime nonblocking',rug.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION and str(rug.get_collision_profile_name())=='NoCollision')
        camera=lookup['S3_FollowCamera']
        arm=camera.get_component_by_class(u.SpringArmComponent)
        view=camera.get_component_by_class(u.CameraComponent)
        test.check('Stage3 camera arm remains fixed',not arm.get_editor_property('do_collision_test'))
        test.check('Stage3 manual clip planes survive BeginPlay',not view.get_editor_property('auto_calculate_ortho_planes') and not view.get_editor_property('update_ortho_planes') and view.get_editor_property('ortho_near_clip_plane')==-2000.)
    if phase=='device_playing':
        key='pull%d'%test.S['device']
        if key not in seen:seen.add(key);verify_devices(world,'During '+key)
    if phase=='wait_d2' and 'after' not in seen:
        seen.add('after');verify_devices(world,'After all interactions')
    previous(world)
test.step=step
