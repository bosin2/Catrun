"""Narrow saved-map author/probe/audit for the 2026-11-12 enemy follow-up.

Root integrator only. No PIE, input, rendering, Blueprint edits or shared settings edits.
Default is read-only probe. Author: -catrunEnemyPresentationAuthor
Cold audit: -catrunEnemyPresentationAuditOnly -catrunEnemyPresentationBaseline=<report.json>
All modes require -catrunGeometryIsolated and an initially clean editor.
Native owner-lease/display code must be built before authoring.
"""
import datetime
import gc
import hashlib
import json
from pathlib import Path
import re
import shutil
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayRepair20261112/EnemyPresentation' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
COMMAND = unreal.SystemLibrary.get_command_line()
AUTHOR = '-catrunenemypresentationauthor' in COMMAND.lower()
AUDIT = '-catrunenemypresentationauditonly' in COMMAND.lower()
MAPS = tuple('/Game/Maps/' + name for name in (
    'Tutorial', 'SoundTest_Tutorial', 'Stage1', 'SoundTest_Stage1', 'Stage2', 'SoundTest_Stage2'))
STAGE2 = set(MAPS[-2:])
COLOR = (0.015, 0.035, 0.12, 1.0)
OPACITY = 0.12
ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
REPORT = {'mode': 'author' if AUTHOR else 'audit' if AUDIT else 'probe', 'completed': False,
          'runtime_or_visual_verified': False, 'maps': {}, 'backups': [], 'saved': [],
          'scope': list(MAPS), 'notes': [
              'Stage2 candle translation patrol disabled; authored transforms/routes/scan/marks preserved.',
              'Armor reuses existing VisionFan: navy color, independent 0.12 opacity, actual cat-center boundary.',
              'Actual radius is settings ArmorDetectRadius + CatSightRadius; no fixed radius authored.',
              'No global vision opacity, sight range, sound propagation or perception rules changed.']}


def persist():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def clean():
    assert ED.get_game_world() is None, 'Game world active; no authoring permitted'
    dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    dirty += list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    assert not dirty, ['Unexpected dirty package; preserving it', [p.get_name() for p in dirty]]


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def file_for(package):
    return ROOT / ('Content/' + package.removeprefix('/Game/') + '.umap')


def vec(v):
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def path(obj):
    return obj.get_path_name() if obj else None


def transform(actor):
    t = actor.get_actor_transform()
    rotation = [round(float(getattr(t.rotation, axis)), 6) for axis in ('x', 'y', 'z', 'w')]
    sign = next((1 if value > 0 else -1 for value in reversed(rotation) if abs(value) > 1.e-6), 1)
    return {'location': vec(t.translation), 'scale': vec(t.scale3d),
            'rotation': [sign * value for value in rotation]}


def snapshot():
    rows = {}
    for actor in ACTORS.get_all_level_actors():
        row = {'class': path(actor.get_class()), 'label': actor.get_actor_label(), 'transform': transform(actor)}
        if isinstance(actor, unreal.CatrunCandle):
            row['candle'] = {key: actor.get_editor_property(key) for key in (
                'patrol_enabled', 'patrol_speed', 'patrol_pause_seconds', 'patrol_loop',
                'penalties_enabled', 'show_sight_display', 'auto_align_eyes', 'body_yaw_offset')}
            row['candle']['patrol_points'] = [path(p) for p in actor.get_editor_property('patrol_points')]
            row['candle']['patrol_relative_points'] = [vec(p) for p in actor.get_editor_property('patrol_relative_points')]
        if isinstance(actor, unreal.CatrunArmor):
            c = actor.get_editor_property('detection_display_color')
            row['armor'] = {'show_detection_display': actor.get_editor_property('show_detection_display'),
                            'detection_display_opacity': round(float(actor.get_editor_property('detection_display_opacity')), 6),
                            'detection_display_color': [round(float(getattr(c, axis)), 6) for axis in ('r', 'g', 'b', 'a')],
                            'patrol_points': [path(p) for p in actor.get_editor_property('patrol_points')]}
        if isinstance(actor, unreal.SoundGridManager):
            settings = actor.get_editor_property('settings')
            row['sound'] = {'settings': path(settings),
                            'debug_show_armor_detection': actor.get_editor_property('debug_show_armor_detection')}
            if settings:
                radius = float(settings.get_editor_property('armor_detect_radius'))
                cat_radius = float(settings.get_editor_property('cat_sight_radius'))
                row['sound'].update({'armor_detect_radius': radius, 'cat_sight_radius': cat_radius,
                                     'effective_cat_center_radius': radius + cat_radius,
                                     'vision_opacity': float(settings.get_editor_property('vision_opacity'))})
        rows[actor.get_name()] = row
    return rows


def expected_after(before, package):
    rows = json.loads(json.dumps(before))
    for row in rows.values():
        if package in STAGE2 and 'candle' in row:
            row['candle']['patrol_enabled'] = False
        if 'armor' in row:
            row['armor'].update({'show_detection_display': True, 'detection_display_opacity': OPACITY,
                                  'detection_display_color': list(COLOR)})
    return rows


def process_map(package, baseline):
    clean()
    assert LEVEL.load_level(package), package
    before = snapshot()
    assert any('armor' in row for row in before.values()), ('No armor found', package)
    if package in STAGE2:
        assert sum('candle' in row for row in before.values()) == 3, ('Unexpected Stage2 candle count', package)
    expected = expected_after(before, package)
    if AUDIT:
        assert before == baseline['maps'][package]['after'], ('Saved-map audit mismatch', package)
        assert before == expected, ('Requested presentation state absent', package)
    if AUTHOR:
        source = file_for(package)
        backup = OUT / 'Before' / source.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        assert digest(source) == digest(backup), ('Backup hash mismatch', package)
        REPORT['backups'].append({'package': package, 'file': str(backup), 'sha256': digest(backup)})
        for actor in ACTORS.get_all_level_actors():
            if package in STAGE2 and isinstance(actor, unreal.CatrunCandle):
                actor.set_editor_property('patrol_enabled', False)
            if isinstance(actor, unreal.CatrunArmor):
                actor.set_editor_property('show_detection_display', True)
                actor.set_editor_property('detection_display_opacity', OPACITY)
                actor.set_editor_property('detection_display_color', unreal.LinearColor(*COLOR))
        del actor
        assert snapshot() == expected, ('Unexpected actor/property mutation', package)
        assert LEVEL.save_current_level(), ('Map save failed', package)
        REPORT['saved'].append(package)
    after = snapshot()
    REPORT['maps'][package] = {'before': before, 'after': after, 'sha256': digest(file_for(package))}
    persist()


try:
    assert '-catrungeometryisolated' in COMMAND.lower(), 'Use an isolated integrator-owned commandlet'
    assert not (AUTHOR and AUDIT), 'Choose author or cold audit, never both'
    clean()
    baseline = None
    if AUDIT:
        match = re.search(r'-catrunEnemyPresentationBaseline=(?:"([^"]+)"|(\S+))', COMMAND, re.I)
        assert match, 'Cold audit requires author report path'
        baseline = json.loads(Path(match.group(1) or match.group(2)).read_text(encoding='utf-8'))
        assert baseline['completed'] and baseline['mode'] == 'author'
    # Shared settings and every content package outside the six maps must remain byte-identical.
    protected = {p: digest(p) for p in (ROOT / 'Content').rglob('*')
                 if p.suffix in ('.uasset', '.umap') and p not in {file_for(m) for m in MAPS}}
    for package in MAPS:
        process_map(package, baseline)
        gc.collect()
    assert all(digest(p) == value for p, value in protected.items()), 'Out-of-scope package changed'
    clean()
    REPORT['completed'] = True
except Exception:
    REPORT['error'] = traceback.format_exc()
    raise
finally:
    persist()
