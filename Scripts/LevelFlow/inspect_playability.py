import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report = {}
for name in ('SoundTest_Tutorial', 'SoundTest_Stage2'):
    assert levels.load_level('/Game/Maps/' + name)
    rows = []
    for a in actors.get_all_level_actors():
        label = a.get_actor_label()
        cls = a.get_class().get_name()
        if name == 'SoundTest_Stage2' and not any(s in label + cls for s in ('Statue', 'Plate', 'Gate', 'PlayerStart', 'Armor', 'Candle', 'Basket')):
            continue
        p = a.get_actor_location()
        origin, extent = a.get_actor_bounds(False)
        row = {'label': label, 'class': cls, 'location': [p.x, p.y, p.z],
               'extent': [extent.x, extent.y, extent.z], 'tags': [str(t) for t in a.tags]}
        if isinstance(a, unreal.CatrunArmor):
            row['patrol'] = [str(v) for v in a.get_editor_property('patrol_points')]
        rows.append(row)
    report[name] = rows
out = Path(unreal.Paths.project_saved_dir()) / 'Flow' / 'playability-inventory.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('PLAYABILITY_INVENTORY_OK')
