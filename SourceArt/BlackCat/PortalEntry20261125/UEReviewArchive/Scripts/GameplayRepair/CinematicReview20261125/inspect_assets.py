"""Read saved Stage2 geometry; optionally apply the targeted camera-only repair."""
from pathlib import Path
import datetime
import json
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/GameplayRepair'))
import repair_cinematic_readability_20261124 as repair
import stage2_arrival_revision as arrival

output = ROOT / 'Saved/CinematicReview20261125' / ('Inspection-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
output.mkdir(parents=True)
report = {'success': False}
try:
    assert not repair.dirty()
    if '-cinematicapply' in u.SystemLibrary.get_command_line().lower():
        report['apply'] = repair.apply()
        report['noop'] = repair.apply()
        assert report['apply']['completed'] and not report['noop']['saved']
    assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage2')
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    geometry = {}
    for actor in actors:
        if actor.get_actor_label() in arrival.LABELS.values() or actor.get_actor_label() == 'S2_Prop_Plate_C_Frame':
            origin, extent = actor.get_actor_bounds(False)
            geometry[actor.get_actor_label()] = {'origin': [origin.x, origin.y, origin.z], 'extent': [extent.x, extent.y, extent.z]}
    report['geometry'] = geometry
    report['success'] = not repair.dirty()
finally:
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('CINEMATIC_INSPECTION', str(output / 'report.json'), report['success'])
