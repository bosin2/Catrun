"""Stage3 instance-only fixed quarter camera; never changes the shared BP."""
import json
from pathlib import Path
import unreal as u
def apply():
    rows=[]
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if actor.get_actor_label()!='S3_FollowCamera':continue
        arm=actor.get_component_by_class(u.SpringArmComponent);assert arm
        before=arm.get_editor_property('do_collision_test')
        arm.set_editor_property('do_collision_test',False)
        assert not arm.get_editor_property('do_collision_test')
        view=actor.get_component_by_class(u.CameraComponent);assert view
        assert view.get_editor_property('projection_mode')==u.CameraProjectionMode.ORTHOGRAPHIC
        fields=('auto_calculate_ortho_planes','update_ortho_planes','ortho_near_clip_plane','ortho_far_clip_plane')
        clip_before={key:view.get_editor_property(key) for key in fields}
        # 9m foreground pillars can extend behind this 4.36m-high orthographic
        # camera. A negative near plane retains their complete silhouettes.
        desired={'auto_calculate_ortho_planes':False,'update_ortho_planes':False,
                 'ortho_near_clip_plane':-2000.,'ortho_far_clip_plane':10000.}
        # Editing an inherited Blueprint component reconstructs it. Reacquire
        # the live instance after each edit; the old Python object can remain
        # readable while referring to a discarded component.
        for key,value in desired.items():
            view=actor.get_component_by_class(u.CameraComponent)
            view.set_editor_property(key,value)
        view=actor.get_component_by_class(u.CameraComponent)
        assert all(view.get_editor_property(key)==value for key,value in desired.items())
        rows.append({'actor':actor.get_actor_label(),'yaw':actor.get_actor_rotation().yaw,
            'before_collision_test':before,'after_collision_test':False,
            'reason':'Keep actual gameplay camera above walls; before captures showed arm collapse to cat Z in Altar/CatBypass',
            'target_arm_length':arm.get_editor_property('target_arm_length'),
            'clip_before':clip_before,'clip_after':desired})
    assert len(rows)==1
    return rows
