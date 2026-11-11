"""Tune existing Stage2 reveal instances; never rebuild presentation or gameplay.

Run with -catrunCameraTuningAuthor or -catrunCameraTuningAudit in an isolated
editor commandlet. Defaults to a read-only inspection. Root owns editor access.
"""
import datetime
import hashlib
import json
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/CinematicPolish20261111/Stage2Tuning' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
MAPS = ('Stage2', 'SoundTest_Stage2')
TUNING = {'CameraTravelTime': 3.0, 'CameraReturnTime': 2.6, 'MaximumLockTime': 10.5}
COMMAND = u.SystemLibrary.get_command_line().lower()
MODE = 'author' if '-catruncameratuningauthor' in COMMAND else ('audit' if '-catruncameratuningaudit' in COMMAND else 'inspect')
REPORT = {'mode': MODE, 'completed': False, 'maps': {}, 'saved': []}


def dirty():
    return sorted(p.get_name() for p in list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    puzzles = [a for a in actors if isinstance(a, u.CatrunStatuePuzzle)]
    assert len(puzzles) == 1, len(puzzles)
    reveal = puzzles[0].get_editor_property('Reveal')
    assert reveal.get_editor_property('bPreserveGameplayFraming')
    state = {a.get_name(): {'class': a.get_class().get_path_name(), 'label': a.get_actor_label(),
                          'transform': a.get_actor_transform().export_text()} for a in actors}
    return reveal, state, {key: float(reveal.get_editor_property(key)) for key in TUNING}


def check(values):
    assert all(abs(values[k] - v) < .0001 for k, v in TUNING.items()), values


OUT.mkdir(parents=True, exist_ok=False)
try:
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    assert not dirty(), dirty()
    files = {name: ROOT / ('Content/Maps/' + name + '.umap') for name in MAPS}
    report_hashes = REPORT['before_hashes'] = {n: digest(p) for n, p in files.items()}
    presentation = ROOT / 'Content/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.uasset'
    protected = digest(presentation)
    if MODE == 'author':
        for name, source in files.items():
            backup = OUT / 'Before' / source.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
            assert digest(backup) == report_hashes[name]
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    for name in MAPS:
        package = '/Game/Maps/' + name
        assert level.load_level(package)
        reveal, actors_before, before = inspect()
        REPORT['maps'][name] = {'before': before, 'actor_count': len(actors_before)}
        if MODE == 'author':
            for key, value in TUNING.items():
                reveal.set_editor_property(key, value)
            _, actors_after, after = inspect()
            assert actors_after == actors_before, 'Actor geometry changed'
            check(after)
            assert not (set(dirty()) - {package}), dirty()
            assert level.save_current_level()
            REPORT['saved'].append(package)
            del reveal
            assert level.load_level('/Game/Maps/MainMenu')
            assert level.load_level(package)
            reveal, reloaded, after = inspect()
            assert reloaded == actors_before, 'Reloaded actor geometry differs'
        else:
            after = before
        if MODE != 'inspect':
            check(after)
        REPORT['maps'][name]['after'] = after
        del reveal
    assert not dirty(), dirty()
    assert digest(presentation) == protected, 'Presentation BP changed'
    REPORT['after_hashes'] = {n: digest(p) for n, p in files.items()}
    if MODE != 'author':
        assert REPORT['after_hashes'] == report_hashes
    REPORT['completed'] = True
except Exception:
    REPORT['error'] = traceback.format_exc()
    raise
finally:
    (OUT / 'report.json').write_text(json.dumps(REPORT, indent=2), encoding='utf-8')
    print('CATRUN_CAMERA_TUNING', MODE, REPORT['completed'], str(OUT / 'report.json'))
