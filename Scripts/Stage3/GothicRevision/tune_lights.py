"""Apply review02's four selective GateHall light adjustments to an existing map.

Inert on import. Root writer calls apply(); this never spawns, destroys, saves,
changes materials, exposure, ambient, fixture placement or gameplay actors.
The matching future-build defaults live in dressing.py.
"""
import unreal as u

OWNER = 'Stage3GothicDressing20261125'
TARGETS = {
    'S3_Gothic_GateHall_SconceLight26': {
        'location': (-865., 3670., 272.), 'candela': 65., 'kelvin': 4200.},
    'S3_Gothic_GateHall_SconceLight27': {
        'location': (465., 3670., 272.), 'candela': 65., 'kelvin': 4200.},
    'S3_Gothic_GateHall_CandelabrumLight1': {
        'location': (-590., 3880., 133.), 'candela': 22., 'kelvin': 3900.},
    'S3_Gothic_GateHall_CandelabrumLight2': {
        'location': (190., 3880., 133.), 'candela': 22., 'kelvin': 3900.},
}


def apply():
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not editor.get_game_world(), 'End PIE before selective light tuning'
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    bindings = []
    # Complete preflight before mutating any light. Position checks catch shifted
    # indices if a later dressing revision reorders its fixture declarations.
    for label, target in TARGETS.items():
        matches = [actor for actor in actors if actor.get_actor_label() == label]
        assert len(matches) == 1, (label, len(matches))
        actor = matches[0]
        assert OWNER in map(str, actor.tags), ('Unowned light', label)
        comp = actor.get_component_by_class(u.PointLightComponent)
        assert comp and comp.get_editor_property('intensity_units') == u.LightUnits.CANDELAS, label
        loc = actor.get_actor_location()
        assert max(abs(a - b) for a, b in zip((loc.x, loc.y, loc.z), target['location'])) < .1, ('Unexpected source position', label)
        assert abs(comp.get_editor_property('temperature') - target['kelvin']) < .1, ('Unexpected temperature', label)
        bindings.append((label, actor, comp, float(comp.get_editor_property('intensity')),
                         actor.get_actor_transform().export_text()))
    report = {'success': False, 'basis': 'review02 GateHallExit foreground-pillar hotspots',
              'changes': [], 'map_saved': False,
              'preserved': 'all other lights, exposure, ambient, physical fixtures and gameplay',
              'visual_qa': 'pending actual player camera after camera correction'}
    try:
        for label, actor, comp, previous, transform in bindings:
            desired = TARGETS[label]['candela']
            comp.set_intensity(desired)
            assert abs(comp.get_editor_property('intensity') - desired) < 1.e-5
            assert actor.get_actor_transform().export_text() == transform
            report['changes'].append({'label': label, 'before_candela': previous,
                                      'after_candela': desired})
    except Exception:
        for label, actor, comp, previous, transform in bindings:
            comp.set_intensity(previous)
        raise
    report['success'] = True
    return report
