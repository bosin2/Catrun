"""Inert rotation-only Stage3 candidate. Root may call prepare(); NEVER saves.

For an XY plane, UE Rotator(P,Y,0) transforms its +Z normal to
(-sin(P)*cos(Y), -sin(P)*sin(Y), cos(P)). P=35,Y=-135 therefore gives
(+.4055798,+.4055798,+.8191520), exactly opposite camera forward for
gameplay rotation pitch=-55,yaw=-135. Both unchanged actors have unit scale.
"""
import math
import unreal as u

TARGET = (35., -135., 0.)
LABELS = ('S3_GateImpact_D1', 'S3_GateImpact_D2')


def vector(v):
    return [v.x, v.y, v.z]


def state(actor, card):
    material = card.get_material(0)
    return {'actor_location': vector(actor.get_actor_location()),
            'actor_rotation': [actor.get_actor_rotation().pitch, actor.get_actor_rotation().yaw, actor.get_actor_rotation().roll],
            'actor_scale': vector(actor.get_actor_scale3d()),
            'relative_location': vector(card.get_editor_property('relative_location')),
            'relative_scale': vector(card.get_editor_property('relative_scale3d')),
            'material': material.get_path_name() if material else None,
            'hidden': card.get_editor_property('hidden_in_game'),
            'collision': str(card.get_collision_enabled()),
            'cast_shadow': card.get_editor_property('cast_shadow')}


def apply(world, labels=LABELS):
    """Apply ONLY 8 card relative rotations per named presenter; no save/trigger."""
    actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    result = {'scope': 'Rotation only; no save, time/material/location/camera/depth changes',
              'target_rotator': list(TARGET), 'records': [], 'packages_saved': False}
    inverse_camera = (.4055797876726389, .40557978767263886, .8191520442889918)
    p, y = math.radians(TARGET[0]), math.radians(TARGET[1])
    normal = (-math.sin(p)*math.cos(y), -math.sin(p)*math.sin(y), math.cos(p))
    result['analytic_normal'] = normal
    result['analytic_facing_dot'] = sum(a*b for a,b in zip(normal, inverse_camera))
    assert abs(result['analytic_facing_dot'] - 1.) < 1e-9
    for label in labels:
        assert label in LABELS and label in actors, label
        actor = actors[label]
        for i in range(8):
            card = actor.get_editor_property('Dust%02d' % i)
            before = state(actor, card)
            assert max(abs(v) for v in before['actor_rotation']) < 1e-4, 'Unexpected parent rotation'
            assert max(abs(v-1.) for v in before['actor_scale']) < 1e-4, 'Unexpected parent scale'
            rot = card.get_editor_property('relative_rotation')
            previous = [rot.pitch, rot.yaw, rot.roll]
            card.set_relative_rotation(u.Rotator(pitch=TARGET[0], yaw=TARGET[1], roll=TARGET[2]), False, True)
            after = state(actor, card)
            assert before == after, ('Rotation candidate changed protected card state', label, i, before, after)
            actual = card.get_up_vector()
            facing = sum(a*b for a,b in zip(vector(actual), inverse_camera))
            assert facing > .99999, ('Actual plane normal does not face camera', label, i, vector(actual))
            result['records'].append({'actor': label, 'card': i, 'rotation_before': previous,
                                      'rotation_after': list(TARGET), 'actual_world_normal': vector(actual),
                                      'actual_facing_dot': facing, 'protected_before': before,
                                      'protected_after': after})
    assert len(result['records']) == 8*len(labels)
    return result


def prepare():
    """Editor candidate only: both D1/D2, unsaved; root decides subsequent save."""
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Editor prepare must not attach to an active PIE run'
    world = ed.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    return apply(world)

