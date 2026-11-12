"""Restore the Tutorial and first Stage1 basket in their four saved maps.

Run with -run=pythonscript and the four geometry CVars at zero. The default
probe stages the candidates in memory and discards them. -catrunUsabilityApply
preflights all maps and backs them up before saving. -catrunUsabilityAudit
cold-loads the result and checks the apply report. Pass that report with
-catrunUsabilityProof=PATH or the CATRUN_BASKET_USABILITY_PROOF launcher global.
"""

from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import traceback
from types import SimpleNamespace

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = Path(globals().get('CATRUN_BASKET_USABILITY_OUT') or
           ROOT / 'Saved/GameplayRepair20261112/BasketUsability' / datetime.now().strftime('%H%M%S-%f')).resolve()
COMMAND = u.SystemLibrary.get_command_line()
MAPS = ('Tutorial', 'SoundTest_Tutorial', 'Stage1', 'SoundTest_Stage1')
FILES = {name: f'Content/Maps/{name}.umap' for name in MAPS}
TUTORIAL = 'BP_Tutorial_HideBasket'
STORAGE = 'BP_S1_storage_HideBasket_26_Interaction'
STORAGE_BODY = 'S1_storage_HideBasket_26'
STORAGE_CLOTH = 'S1_storage_HideBasket_26_Cloth'


def load_helpers():
    path = ROOT / 'Scripts/GameplayRepair/repair_basket_doors.py'
    source = path.read_text(encoding='utf-8-sig')
    prefix, marker, footer = source.partition('\nreport = {')
    assert marker and "main(report)" in footer and "def main(report):" in prefix, 'Basket helper layout changed'
    namespace = {}
    exec(compile(prefix, str(path), 'exec'), namespace)
    for key in ('actor_snapshot', 'cold_actor_snapshots_match', 'grid', 'group', 'set_pose',
                'basket_geometry', 'body_support', 'supported', 'sweep', 'overlap', 'line',
                'at', 'angle', 'path', 'v', 'hitinfo', 'hash_data', 'sha', 'dirty', 'file_hashes',
                'preserve_actors'):
        assert callable(namespace.get(key)), ('Missing basket helper', key)
    return SimpleNamespace(**namespace)


def snapshot(actors):
    return {a.get_name(): h.actor_snapshot(a) for a in actors}


def target(w, actors, name):
    tutorial = name.endswith('Tutorial')
    actor, = [a for a in actors if a.get_actor_label() == (TUTORIAL if tutorial else STORAGE)]
    assert isinstance(actor, u.CatrunHideBasket)
    a, body, cloth, anchor, body_mesh, cloth_mesh = h.group(actor)
    cloth_owner = cloth.get_owner() if cloth else None
    if tutorial:
        assert body is None and cloth is None, h.path(a)
    else:
        assert body.get_actor_label() == STORAGE_BODY and cloth_owner.get_actor_label() == STORAGE_CLOTH
        assert body.get_name() == 'StaticMeshActor_62' and cloth_owner.get_name() == 'SkeletalMeshActor_2'
    guide, = [c for c in a.get_components_by_class(u.ArrowComponent) if c.get_name() == 'ExitDirectionGuide']
    members = [a] if tutorial else [a, body, cloth_owner]
    return SimpleNamespace(world=w, actor=a, members=members, body=body_mesh, cloth=cloth_mesh,
                           hidden=anchor, guide=guide, tutorial=tutorial)


def assert_pose(actor, location, yaw):
    assert (actor.get_actor_location() - u.Vector(*location)).length() < .005, h.path(actor)
    assert (actor.get_actor_forward_vector() - h.at(yaw)).length() < .001, h.path(actor)


def set_candidate(group):
    a = group.actor
    if group.tutorial:
        assert_pose(a, (330, 60, .1), -90)
        assert h.v(a.get_editor_property('OpenDirectionLocal')) == [0., -1., 0.]
        h.set_pose(a, u.Vector(260, 60, .1), 0.)
        yaw = -90.
    else:
        _, body, cloth = group.members
        assert_pose(a, (710, 1750, .58489), 180)
        assert_pose(body, (710, 1750, .58489), 0)
        assert_pose(cloth, (710, 1750, 3.08489), 0)
        a.modify()
        a.set_editor_property('OpenDirectionLocal', u.Vector(-1, 0, 0))
        h.set_pose(a, a.get_actor_location(), 0.)
        h.set_pose(body, body.get_actor_location(), 180.)
        h.set_pose(cloth, cloth.get_actor_location(), 180.)
        yaw = 180.
    guide, = [c for c in a.get_components_by_class(u.ArrowComponent) if c.get_name() == 'ExitDirectionGuide']
    guide.modify()
    guide.set_world_rotation(u.Rotator(pitch=0., yaw=yaw, roll=0.), False, False)


def direction_allowed(yaw, front_yaw, camera_yaw):
    def sector(heading):
        relative_yaw = (heading - camera_yaw + 180.) % 360. - 180.
        return math.floor((relative_yaw + 22.5) / 45.) % 8

    difference = abs(sector(yaw) - sector(front_yaw))
    return math.cos(math.radians(yaw - front_yaw)) >= -1.e-4 and min(difference, 8 - difference) <= 2


def entry_geometry(group, cap, action, origin, yaw, allowed):
    """Evaluate the saved collision fixtures used by native directional entry."""
    w = group.world
    cat = cap.get_owner()
    approach_ignore = [cat]
    jump_ignore = approach_ignore + group.members[:2]
    direction = h.at(yaw)
    entry_distance = action.get_editor_property('EntryDistance')
    radius = action.get_editor_property('InteractionRange')
    approach, approach_hit = h.supported(w, origin + direction * min(100., radius - 2.),
                                         cap, approach_ignore, 0., 50.)
    stage, stage_hit = h.supported(w, origin + direction * entry_distance, cap, approach_ignore, 0., 50.)
    outer_sweep = h.sweep(w, approach, stage, cap, approach_ignore) if approach is not None and stage is not None else None
    distance = (approach - origin).length() if approach is not None else None
    stand_overlap = h.overlap(w, approach, cap, approach_ignore) if approach is not None else None
    jump_sweep, sight, stage_overlap = None, None, None
    if stage is not None:
        inner = u.Vector(origin.x, origin.y, stage.z)
        jump_sweep = h.sweep(w, stage, inner, cap, jump_ignore)
        sight = h.line(w, stage, origin, jump_ignore)
        stage_overlap = h.overlap(w, stage, cap, approach_ignore)
    geometry_clear = (approach is not None and stage is not None and distance < radius
                      and not (stand_overlap or outer_sweep or stage_overlap or jump_sweep or sight))
    safe = allowed and geometry_clear
    return dict(approach=h.v(approach) if approach is not None else None,
                stage=h.v(stage) if stage is not None else None, approach_floor=approach_hit, stage_floor=stage_hit,
                outer_sweep=h.hitinfo(outer_sweep), jump_sweep=h.hitinfo(jump_sweep), sight=h.hitinfo(sight),
                stand_overlap=stand_overlap, stage_overlap=stage_overlap, distance=distance,
                direction_allowed=allowed, geometry_clear=geometry_clear, safe=safe,
                facing_predictions={label: dict(yaw=heading % 360., safe=safe) for label, heading in
                                    (('toward_basket', yaw + 180.), ('away_from_basket', yaw))})


def inspect_candidate(group, cat, camera):
    cap = cat.get_component_by_class(u.CapsuleComponent)
    movement = cat.get_component_by_class(u.CharacterMovementComponent)
    action = cat.get_component_by_class(u.CatrunBasketInteractionComponent)
    assert cap and movement and action and camera
    assert str(cap.get_collision_profile_name()) == 'Pawn' and cap.get_collision_object_type() == h.PAWN
    assert all(cap.get_collision_response_to_channel(ch) == h.BLOCK for ch in h.OBJECT_CHANNELS)
    assert action.get_editor_property('ObstacleChannel') == u.CollisionChannel.ECC_VISIBILITY
    assert (movement.get_gravity_direction() - u.Vector(0, 0, -1)).length() < .001
    assert (cap.get_up_vector() - u.Vector(0, 0, 1)).length() < .001
    assert group.body.get_collision_response_to_channel(h.PAWN) == h.BLOCK
    assert group.cloth.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION

    actor = group.actor
    origin = group.hidden.get_world_location()
    local = actor.get_editor_property('OpenDirectionLocal')
    front = actor.get_actor_forward_vector() * local.x + actor.get_actor_right_vector() * local.y
    expected = h.at(-90. if group.tutorial else 180.)
    expected_origin = u.Vector(260, 60, 26.35) if group.tutorial else u.Vector(710, 1750, 26.83489)
    assert (origin - expected_origin).length() < .005, h.path(actor)
    assert (front - expected).length() < .001, h.path(actor)
    assert all((mesh.get_forward_vector() - expected).length() < .001
               for mesh in (group.body, group.cloth, group.guide)), h.path(actor)
    assert_pose(actor, (260, 60, .1) if group.tutorial else (710, 1750, .58489), 0.)
    if not group.tutorial:
        assert_pose(group.members[1], (710, 1750, .58489), 180.)
        assert_pose(group.members[2], (710, 1750, 3.08489), 180.)

    yaw = h.angle(expected)
    camera_yaw = camera.get_world_rotation().yaw
    headings = {'front': yaw, 'right': yaw + 90., 'rear': yaw + 180., 'left': yaw - 90.}
    entries = {label: entry_geometry(group, cap, action, origin, heading,
                                     direction_allowed(heading, yaw, camera_yaw))
               for label, heading in headings.items()}
    geometry = h.basket_geometry(group.world, origin, yaw, camera, cap, action, group.members, False)
    support = h.body_support(group.world, group.body, [cat] + group.members)
    return dict(hidden=h.v(origin), native_front=h.v(front), visual_front=h.v(group.body.get_forward_vector()),
                cloth_front=h.v(group.cloth.get_forward_vector()), guide_front=h.v(group.guide.get_forward_vector()),
                entries=entries, exits=geometry['exits'], body_support=support,
                camera_yaw=camera_yaw, camera_sight=geometry['camera_sight'],
                safe=(entries['front']['safe'] and not entries['rear']['direction_allowed'] and support['safe']
                      and geometry['exits']['front']['safe']))


def load(name):
    assert not h.dirty() and h.LEVEL.load_level('/Game/Maps/' + name), name
    world = h.ED.get_editor_world()
    actors = list(h.ACTORS.get_all_level_actors())
    cat, = [a for a in actors if a.get_class().get_name() == 'BP_Cat_C']
    camera, = [a for a in actors if a.get_class().get_name() == 'BP_QuarterViewCamera_C']
    manager, = [a for a in actors if isinstance(a, u.SoundGridManager)]
    return actors, cat, camera.get_component_by_class(u.CameraComponent), manager, target(world, actors, name)


def stage(name, row):
    actors, cat, camera, manager, group = load(name)
    row['before'] = snapshot(actors)
    row['grid_sha256'] = h.hash_data(h.grid(manager))
    owned = {a.get_name() for a in group.members}
    row['owned_actors'] = sorted(owned)
    set_candidate(group)
    group = target(group.world, actors, name)
    row['geometry'] = inspect_candidate(group, cat, camera)
    assert row['geometry']['safe'], (name, 'Required geometry failed', row['geometry'])
    row['after'] = snapshot(h.ACTORS.get_all_level_actors())
    row['changed_actors'] = h.preserve_actors(row['before'], row['after'], owned)
    assert set(row['changed_actors']) == {a.get_actor_label() for a in group.members}, name
    assert h.hash_data(h.grid(manager)) == row['grid_sha256'], (name, 'Saved grid changed')
    assert set(h.dirty()) <= {'/Game/Maps/' + name}, (name, h.dirty())


def audit(name, row, applied):
    actors, cat, camera, manager, group = load(name)
    row['after'] = snapshot(actors)
    row['grid_sha256'] = h.hash_data(h.grid(manager))
    row['geometry'] = inspect_candidate(group, cat, camera)
    assert row['geometry']['safe'], (name, 'Cold geometry failed', row['geometry'])
    assert h.cold_actor_snapshots_match(row['after'], applied['after']), (name, 'Cold actor snapshot differs')
    assert row['grid_sha256'] == applied['grid_sha256'], (name, 'Cold saved grid differs')


def read_proof(report):
    argument = re.search(r'(?:^|\s)-catrunUsabilityProof=(?:"([^"]+)"|(\S+))', COMMAND, re.I)
    proof_path = globals().get('CATRUN_BASKET_USABILITY_PROOF') or (
        next(value for value in argument.groups() if value) if argument else None)
    assert proof_path, 'Audit requires an apply report'
    proof = json.loads(Path(proof_path).read_text(encoding='utf-8-sig'))
    assert proof['mode'] == 'apply' and proof['completed'] and proof['pid'] != report['pid']
    assert proof['content_after'] == report['content_before'], 'Saved content differs from apply report'
    report['proof'] = str(proof_path)
    return proof


def run(report):
    assert '-run=pythonscript' in COMMAND.lower() and not h.ED.get_game_world() and not h.dirty()
    report['cvars'] = {key: u.SystemLibrary.get_console_variable_int_value(key) for key in h.CVARS}
    assert all(value == 0 for value in report['cvars'].values()), report['cvars']
    report['content_before'] = h.file_hashes()
    if report['mode'] == 'audit':
        proof = read_proof(report)
        for name in MAPS:
            row = report['maps'][name] = {}
            audit(name, row, proof['maps'][name])
        assert not h.dirty(), h.dirty()
    else:
        for name in MAPS:
            row = report['maps'][name] = {}
            stage(name, row)
            u.EditorLoadingAndSavingUtils.new_blank_map(False)
            assert not h.dirty() and h.sha(ROOT / FILES[name]) == report['content_before'][FILES[name]], name

    written = {}
    try:
        if report['mode'] == 'apply':
            report['backups'] = {}
            for name, relative in FILES.items():
                backup = OUT / 'Before' / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, backup)
                assert h.sha(backup) == report['content_before'][relative], name
                report['backups'][name] = str(backup)
            for name, relative in FILES.items():
                staged = {}
                assert h.sha(ROOT / relative) == report['content_before'][relative], name
                stage(name, staged)
                expected = report['maps'][name]
                assert all(h.cold_actor_snapshots_match(staged[key], expected[key]) for key in ('before', 'after')), name
                assert staged['grid_sha256'] == expected['grid_sha256'], name
                saved = h.LEVEL.save_current_level()
                written[name] = h.sha(ROOT / relative)
                assert saved and not h.dirty() and written[name] != report['content_before'][relative], name
                expected['saved_sha256'] = written[name]
        report['content_after'] = h.file_hashes()
        before, after = report['content_before'], report['content_after']
        assert before.keys() == after.keys(), 'Unexpected content addition or removal'
        report['changed_files'] = [key for key in before if before[key] != after[key]]
        assert set(report['changed_files']) == (set(FILES.values()) if written else set()), report['changed_files']
    except Exception:
        if written:
            u.EditorLoadingAndSavingUtils.new_blank_map(False)
            report['restored_after_failure'] = []
            for name, digest in written.items():
                file = ROOT / FILES[name]
                if h.sha(file) == digest and digest != report['content_before'][FILES[name]]:
                    shutil.copy2(report['backups'][name], file)
                    assert h.sha(file) == report['content_before'][FILES[name]], name
                    report['restored_after_failure'].append(name)
        raise


flags = COMMAND.lower().split()
modes = [mode for mode in ('apply', 'audit') if '-catrunusability' + mode in flags]
report = dict(mode=modes[0] if modes else 'probe', maps={}, completed=False, pid=os.getpid(),
              scope='Saved actor and collision queries. Entry gate uses the approach side and ignores cat facing.')
OUT.mkdir(parents=True, exist_ok=True)
try:
    assert len(modes) <= 1, 'Choose a single mode'
    h = load_helpers()
    run(report)
    report['completed'] = True
except Exception:
    report['error'] = traceback.format_exc()
finally:
    report_file = OUT / 'report.json'
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CATRUN_BASKET_USABILITY_REPORT', str(report_file), report['completed'])
if not report['completed']:
    raise RuntimeError(report['error'])
