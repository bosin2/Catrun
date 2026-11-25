"""Inert, root-invoked Stage3 original 900cm pillar restoration. Never saves.

User's later request explicitly permits decorated pillar tops in the play view.
Retired extensions keep their objects, transforms and materials for recovery.
"""
import hashlib
import json
from pathlib import Path

HEIGHT_CM = 900.
PARTS = {'Base', 'ShaftLower', 'ShaftUpper', 'Capital'}
PREFIX = 'S3_GrandPillar_'
RETIRED = 'S3_RetiredPillar_'


def bounds(actor):
    c, e = actor.get_actor_bounds(False, False)
    return [c.x-e.x, c.y-e.y, c.z-e.z], [c.x+e.x, c.y+e.y, c.z+e.z]


def groups(actors):
    result = {}
    for actor in actors:
        label = actor.get_actor_label()
        if label.startswith(PREFIX):
            stem, part = label.rsplit('_', 1)
            assert part not in result.setdefault(stem, {}), label
            result[stem][part] = actor
    assert len(result) == 10, len(result)
    return result


def union(actors):
    boxes = [bounds(a) for a in actors]
    return ([min(b[0][i] for b in boxes) for i in range(3)],
            [max(b[1][i] for b in boxes) for i in range(3)])


def readback():
    """Read-only structural contract; caller must inspect actual Lit play views."""
    import unreal as u
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    result = {'success': False, 'groups': [], 'retired': [], 'level_saved': False}
    active = groups(actors)
    for stem, parts in active.items():
        assert set(parts) == PARTS, (stem, list(parts))
        lo, hi = union(parts.values())
        assert abs(lo[2]) < .1 and abs(hi[2]-900) < .1, (stem, lo, hi)
        expected = [(x+y)/2 for x,y in zip(lo,hi)] + [1.] + [(y-x)/2 for x,y in zip(lo,hi)] + [1.]
        cap_lo, cap_hi = bounds(parts['Capital'])
        assert abs(cap_lo[2]-840) < .1 and abs(cap_hi[2]-900) < .1
        assert abs(bounds(parts['ShaftUpper'])[1][2]-840) < .1
        for part, actor in parts.items():
            c = actor.get_component_by_class(u.StaticMeshComponent)
            assert c.get_editor_property('visible') and not c.get_editor_property('hidden_in_game'), actor.get_actor_label()
            data = list(c.get_editor_property('custom_primitive_data').get_editor_property('data'))
            assert len(data) >= 24 and all(abs(x-y)<.1 for x,y in zip(data[16:24],expected)), (stem,part,data[16:24],expected)
        result['groups'].append({'group':stem,'min':lo,'max':hi,'active_parts':4,'cpd':expected})
    for actor in actors:
        if not actor.get_actor_label().startswith(RETIRED):
            continue
        c=actor.get_component_by_class(u.StaticMeshComponent)
        assert not c.get_editor_property('visible') and c.get_editor_property('hidden_in_game')
        assert c.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION
        assert not c.get_editor_property('cast_shadow')
        result['retired'].append(actor.get_actor_label())
    assert len(result['retired'])==50, len(result['retired'])
    camera=next(a for a in actors if a.get_actor_label()=='S3_FollowCamera').get_component_by_class(u.CameraComponent)
    result['camera']={key:camera.get_editor_property(key) for key in ('ortho_width','ortho_near_clip_plane','ortho_far_clip_plane')}
    assert result['camera']=={'ortho_width':900.,'ortho_near_clip_plane':-4000.,'ortho_far_clip_plane':10000.},result['camera']
    result['success']=True
    return result


def apply(expected_map_sha=None):
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    map_path=root/'Content/Maps/Stage3.umap'
    sha=lambda:hashlib.sha256(map_path.read_bytes()).hexdigest()
    before_sha=sha()
    if expected_map_sha is not None:
        assert before_sha==expected_map_sha, 'Map changed; root must review the latest saved map'
    editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not editor.get_game_world()
    assert editor.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
    subsystem=u.get_editor_subsystem(u.EditorActorSubsystem)
    actors=list(subsystem.get_all_level_actors())
    active=groups(actors)
    snapshots={}
    for actor in actors:
        c=actor.get_component_by_class(u.StaticMeshComponent)
        snapshots[actor.get_path_name()]={
            'actor':actor, 'label':actor.get_actor_label(), 'transform':actor.get_actor_transform(),
            'transform_text':actor.get_actor_transform().export_text(),
            'component':c,
            'materials':[c.get_material(i) for i in range(c.get_num_materials())] if c else [],
        }
        if actor.get_actor_label().startswith(PREFIX):
            snapshots[actor.get_path_name()].update({
                'visible':c.get_editor_property('visible'),'hidden':c.get_editor_property('hidden_in_game'),
                'collision':c.get_collision_enabled(),'shadow':c.get_editor_property('cast_shadow'),
                'cpd':list(c.get_editor_property('custom_primitive_data').get_editor_property('data'))})
    expected_parts=PARTS|{'Continuation'+str(i) for i in range(5)}
    for stem,parts in active.items():
        assert set(parts)==expected_parts,(stem,list(parts))
        assert abs(union(parts.values())[1][2]-3450)<.1
        assert abs(bounds(parts['ShaftUpper'])[1][2]-840)<.1
        assert abs(bounds(parts['Capital'])[1][2]-bounds(parts['Capital'])[0][2]-60)<.1
        for name,a in parts.items():
            if name.startswith('Continuation'):
                c=a.get_component_by_class(u.StaticMeshComponent)
                assert c.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION and not c.get_editor_property('cast_shadow')
    grid=next(a for a in actors if a.get_actor_label()=='S3_SoundGrid')
    grid_before=grid.call_method('ExportBakedGridSnapshot')
    moved=set()
    retired=[]
    try:
        for stem,parts in active.items():
            for name,actor in parts.items():
                if not name.startswith('Continuation'):
                    continue
                c=actor.get_component_by_class(u.StaticMeshComponent)
                old_label=actor.get_actor_label()
                actor.set_actor_label(RETIRED+old_label[len(PREFIX):])
                c.set_visibility(False)
                c.set_hidden_in_game(True)
                retired.append({'path':actor.get_path_name(),'old_label':old_label,'new_label':actor.get_actor_label()})
            capital=parts['Capital']
            delta=840.-bounds(capital)[0][2]
            capital.set_actor_location(capital.get_actor_location()+u.Vector(0,0,delta),False,True)
            moved.add(capital.get_path_name())
            lo,hi=union([parts[name] for name in PARTS])
            center=[(x+y)/2 for x,y in zip(lo,hi)]
            extent=[(y-x)/2 for x,y in zip(lo,hi)]
            for name in PARTS:
                c=parts[name].get_component_by_class(u.StaticMeshComponent)
                c.set_default_custom_primitive_data_vector4(16,u.Vector4(*center,1.))
                c.set_default_custom_primitive_data_vector4(20,u.Vector4(*extent,1.))
        report=readback()
        assert {a.get_path_name() for a in subsystem.get_all_level_actors()}==set(snapshots)
        for path,s in snapshots.items():
            a,c=s['actor'],s['component']
            if path not in moved:
                assert a.get_actor_transform().export_text()==s['transform_text'],s['label']
            if c:
                assert [c.get_material(i) for i in range(c.get_num_materials())]==s['materials'],s['label']
            if s['label'].startswith(PREFIX):
                assert c.get_collision_enabled()==s['collision'] and c.get_editor_property('cast_shadow')==s['shadow'],s['label']
        assert grid.call_method('ExportBakedGridSnapshot')==grid_before,'Sound grid changed'
        assert sha()==before_sha,'Map file changed during unsaved patch'
        report.update({'map_sha_before':before_sha,'map_sha_unsaved':sha(),'moved_capitals':sorted(moved),
                       'retirement_mapping':retired,'actor_count':len(actors),'collision_shadow_materials_preserved':True,
                       'original_shaft_transforms_preserved':True,'grid_unchanged':True,
                       'pending':'Root save, fresh saved readback, actual possessed GateMiddle/GateExtreme Lit frames; no visual claim yet'})
        return report
    except Exception:
        for s in snapshots.values():
            if not s['label'].startswith(PREFIX):
                continue
            a,c=s['actor'],s['component']
            a.set_actor_label(s['label']);a.set_actor_transform(s['transform'],False,True)
            c.set_visibility(s['visible']);c.set_hidden_in_game(s['hidden'])
            for index,value in enumerate(s['cpd']):
                c.set_default_custom_primitive_data_float(index,value)
        raise
