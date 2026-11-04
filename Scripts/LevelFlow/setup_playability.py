"""Set up Stage2 recovery stations only. The existing tutorial presentation is owned by its original assets."""
import json
import shutil
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir())
out = root / 'Saved/Flow/Playability'
out.mkdir(parents=True, exist_ok=True)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report = {}

def begin(name):
    relative = Path('Content/Maps/' + name + '.umap')
    backup = out / 'Backups' / relative
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, backup)
    assert levels.load_level('/Game/Maps/' + name)
    return {a.get_actor_label(): a for a in actors.get_all_level_actors()}

def spawn(labels, cls, name, position):
    a = labels.get(name) or actors.spawn_actor_from_class(cls, unreal.Vector(*position))
    assert isinstance(a, cls), name
    a.set_actor_label(name)
    a.set_actor_location(unreal.Vector(*position), False, True)
    a.set_folder_path('Gameplay/Guidance')
    return a

def zone(labels, name, pos, extent, priority, title, message):
    a = spawn(labels, unreal.CatrunGuidanceZone, name, pos)
    a.get_editor_property('Area').set_box_extent(unreal.Vector(*extent))
    a.set_editor_property('Priority', priority)
    a.set_editor_property('Title', title)
    a.set_editor_property('Message', message)

def clear_marker_position(labels, candidates):
    # Include the actual SoundTest props, not just the original drawing's wall list.
    for point in candidates:
        blocked = False
        for actor in labels.values():
            if isinstance(actor,(unreal.CatrunPuzzleReset,unreal.CatrunGuidanceZone,unreal.CatrunStatuePuzzle)):
                continue
            if not actor.get_actor_enable_collision(): continue
            center, half = actor.get_actor_bounds(True)
            if half.z <= 0 or center.z+half.z < 12 or center.z-half.z > 60: continue
            if abs(center.x-point[0]) < half.x+40 and abs(center.y-point[1]) < half.y+40:
                blocked = True
                break
        if not blocked: return point
    raise AssertionError('No clear recovery marker position among ' + str(candidates))

# Tutorial intro, hints, cinematic and door state must not be rewritten here.

for name in ('Stage2', 'SoundTest_Stage2'):
    labels = begin(name)
    puzzle = labels['S2_StatuePuzzle']
    positions = {'A': (1820,3010,1), 'B': (780,1740,1), 'C': (1650,3830,1)}
    positions['B'] = clear_marker_position(labels, [(820,1900,1),(700,1920,1),(900,1570,1),(500,1830,1),(850,1400,1)])
    for key, pos in positions.items():
        pedestal = spawn(labels, unreal.CatrunPuzzleReset, 'S2_Recovery_' + key, pos)
        pedestal.set_editor_property('Puzzle', puzzle)
        pedestal.set_editor_property('PuzzleId', key)
    zone(labels, 'Guide_StatuePractice', (1375,3620,70), (375,410,180), 2,
         '동상을 발판 위로 밀어보세요', '동상 뒤에서 이동키를 누르면 밀 수 있어요. 잘못 밀었다면 푸른 복구 장치 가까이에서 F를 누르세요. 이 방의 동상만 돌아갑니다.')
    zone(labels, 'Guide_Stage2Goal', (1200,1900,70), (1400,2100,180), 0,
         '동상으로 길을 열고 출구로', '발판 위에 동상을 놓으면 연결된 문이 열려요. 방울로 갑옷을 유인하면서 다음 방으로 이동하세요.')
    assert levels.save_current_level()
    report[name] = positions

(out / 'setup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('PLAYABILITY_SETUP_OK ' + json.dumps(report, ensure_ascii=False))
