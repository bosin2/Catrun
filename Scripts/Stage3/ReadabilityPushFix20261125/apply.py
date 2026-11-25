"""Apply the two Stage3 fixes in a separate unattended editor; root owns saves."""
import hashlib
import importlib.util
import json
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
RUN = ROOT / 'Saved/Stage3ReadabilityPushFix20261125'
RUN.mkdir(parents=True, exist_ok=True)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

report = {'success': False}
try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    baseline = json.loads((RUN / 'QA/before/snapshot.json').read_text(encoding='utf8'))
    map_file = ROOT / 'Content/Maps/Stage3.umap'
    assert digest(map_file) == baseline['saved_map_sha256'], 'Stage3 changed after baseline; re-audit before writing'
    assert not (RUN / 'applied.json').exists(), 'Refusing to apply twice'
    backup = RUN / 'Backup'
    files = [map_file] + list((ROOT / 'Content/Environment/Stage3/GothicRevision_20261125/CameraReadability').rglob('*.uasset'))
    report['backup_sha256'] = {}
    for source in files:
        relative = source.relative_to(ROOT)
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), str(target)
        shutil.copy2(source, target)
        report['backup_sha256'][relative.as_posix()] = digest(source)
    assert LE.load_level('/Game/Maps/Stage3')
    assert not ED.get_game_world()
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    by_label = {a.get_actor_label(): a for a in actors}
    before = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
    statue = by_label['S3_Statue1']
    pos = statue.get_actor_location()
    assert abs(pos.x + 700) < .01 and abs(pos.y + 1430) < .01, str(pos)
    report['statue1_before'] = [pos.x, pos.y, pos.z]
    statue.set_actor_location(u.Vector(pos.x, pos.y - 80, pos.z), False, True)
    pos = statue.get_actor_location()
    report['statue1_after'] = [pos.x, pos.y, pos.z]
    permitted = {'S3_Statue1', 'S3_GothicVisual_Weight1', 'S3_GothicVisual_WeightShoe1'}
    changed = [a.get_actor_label() for a in actors if before[a.get_path_name()] != a.get_actor_transform().export_text()]
    assert set(changed) == permitted, changed
    report['changed_actor_transforms'] = changed
    for label in ('S3_GothicVisual_Weight1', 'S3_GothicVisual_WeightShoe1'):
        assert by_label[label].get_attach_parent_actor() == statue
        assert abs(by_label[label].get_actor_location().y + 1510) < .01
    occlusion = module('stage3_readability_fix', 'Scripts/Stage3/GothicRevision/occlusion.py')
    report['occlusion'] = occlusion.apply()
    assert LE.save_current_level()
    report['saved_map_sha256'] = digest(map_file)
    report['unchanged_actor_transform_count'] = len(actors) - len(changed)
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()
finally:
    (RUN / 'applied.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print('STAGE3_READABILITY_PUSH_FIX', report['success'], report.get('error', ''))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
