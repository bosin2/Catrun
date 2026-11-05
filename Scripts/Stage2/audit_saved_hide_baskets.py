"""Read-only cold audit; root may pass CATRUN_STAGE2_BASKET_AUTHOR_REPORT.

The safe default is Author01, whose exact source/content hashes still apply.
Only generated editor billboard keys normalize; every value remains exact.
"""
import ast
import copy
import json
import re
import traceback
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
SOURCE = ROOT/'Scripts/Stage2/place_hide_baskets.py'
PROOF = Path(globals().get('CATRUN_STAGE2_BASKET_AUTHOR_REPORT',
    ROOT/'Saved/GameplayRepair20261105/Stage2Baskets/204541-741630/report.json')).resolve()
proof = json.loads(PROOF.read_text(encoding='utf-8'))
# Load frozen definitions without main(), its save path, or report-side effects.
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
tree.body = [n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.AnnAssign,ast.FunctionDef))]
g = {'__name__':'cold_audit_definitions','CATRUN_STAGE2_BASKET_MODE':'audit'}
exec(compile(tree,str(SOURCE),'exec'),g)
report, out = g['REPORT'], g['OUT']
report.update(mode='cold-audit-companion',proof=str(PROOF),normalization='Only unique hidden NoCollision EmptyActor BillboardComponent numeric keys; all value fields exact')


def canonical(snapshot):
    result, renamed = copy.deepcopy(snapshot), []
    for name, actor in result.items():
        if actor['class'] != '/Game/Systems/Interaction/Hiding/BP_HideBasket.BP_HideBasket_C':
            continue
        components = actor['components']
        matches = [k for k,c in components.items() if c['class'] == '/Script/Engine.BillboardComponent']
        assert len(matches) == 1, ('Nonunique basket editor billboard',name,matches)
        key, c = matches[0], components[matches[0]]
        assert re.fullmatch(r'BillboardComponent_\d+',key), ('Unexpected generated name',key)
        assert c['visible'] is False and c['profile'] == 'NoCollision' and c['collision'] == '<CollisionEnabled.NO_COLLISION: 0>'
        assert c['references'].get('sprite') == '/Engine/EditorResources/EmptyActor.EmptyActor'
        assert 'EditorEmptyActorBillboard' not in components
        components['EditorEmptyActorBillboard'] = components.pop(key)
        renamed.append({'actor':name,'original_key':key})
    assert len(renamed) == 3 and len(result) == 9
    return result, renamed


def content_hashes():
    return {str(p.relative_to(ROOT)).replace('\\','/'):g['digest'](p)
            for p in sorted((ROOT/'Content').rglob('*')) if p.suffix in ('.uasset','.umap')}


def audit():
    command = unreal.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and '-catrunstage2basketsisolated' in command
    g['require_clean']()
    report['pid'] = __import__('os').getpid()
    assert proof['completed'] and proof['mode'] == 'author' and not proof['errors'] and proof['pid'] != report['pid']
    report['source_hashes'] = {p:g['digest'](ROOT/p) for p in proof['source_hashes']}
    assert report['source_hashes'] == proof['source_hashes'], 'Original author source/dependency hash changed'
    report['companion_sha256'] = g['digest'](ROOT/'Scripts/Stage2/audit_saved_hide_baskets.py')
    report['content_before'] = content_hashes()
    assert report['content_before'] == proof['content_after'], 'Saved content differs from Author01'
    report['cvars'] = {k:unreal.SystemLibrary.get_console_variable_int_value(k) for k in proof['cvars']}
    assert report['cvars'] == proof['cvars'] and all(value == 0 for value in report['cvars'].values())
    for name in g['MAPS']:
        assert proof['maps'][name]['saved'] and g['LEVEL'].load_level('/Game/Maps/'+name)
        g['require_clean']()
        actual, unchanged = g['snapshot'](True), g['snapshot']()
        row = report['maps'][name] = {'owned_actual':actual,'nonowned_actual':unchanged}
        a, row['actual_billboard_keys'] = canonical(actual)
        b, row['authored_billboard_keys'] = canonical(proof['maps'][name]['owned_after'])
        assert a == b, 'Cold owned snapshot differs beyond permitted editor key names'
        assert unchanged == proof['maps'][name]['nonowned_before'], 'Cold nonowned snapshot changed'
        aa, w = g['all_actors'](), g['ED'].get_editor_world()
        cats = [x for x in aa if x.get_class().get_name() == 'BP_Cat_C']
        managers = [x for x in aa if isinstance(x,unreal.SoundGridManager)]
        cameras = [x for x in aa if x.get_class().get_name() == 'BP_QuarterViewCamera_C']
        assert len(cats) == len(managers) == len(cameras) == 1
        cap = cats[0].get_component_by_class(unreal.CapsuleComponent)
        action = cats[0].get_component_by_class(unreal.CatrunBasketInteractionComponent)
        assert cap and action and cap.get_collision_object_type() == g['PAWN']
        assert all(cap.get_collision_response_to_channel(c) == g['BLOCK'] for c in g['CHANNELS'])
        assert str(action.get_editor_property('ObstacleChannel')) == str(unreal.CollisionChannel.ECC_VISIBILITY)
        yaw = cameras[0].get_component_by_class(unreal.CameraComponent).get_world_rotation().yaw
        assert yaw == proof['maps'][name]['camera_yaw']
        row['grid'] = g['grid'](managers[0])
        assert row['grid'] == proof['maps'][name]['grid_after'], 'Cold grid differs from author'
        bodies, row['baskets'] = [], {}
        for spec in g['PLACEMENTS']:
            basket,body,cloth = g['owned_trio'](spec[0])
            assert basket and body and cloth and basket.get_editor_property('ExternalBody') == body
            assert basket.get_editor_property('ExternalCloth') == cloth.get_component_by_class(unreal.SkeletalMeshComponent)
            bodies.append(body)
            geom = g['validate_geometry'](w,basket,body,cap,action,yaw)
            row['baskets'][spec[0]] = geom
            assert geom['safe'], ('Cold entry/exit unsafe',name,spec[0])
        row['route_clearance'], row['grid_reachability'] = g['route_clearance'](bodies), g['grid_paths'](row['grid'])
        assert all(r['clear'] for r in row['route_clearance']) and all(r['reachable'] for r in row['grid_reachability'])
        assert g['snapshot'](True) == actual and g['snapshot']() == unchanged
        g['require_clean']()
    report['content_after'] = content_hashes()
    assert report['content_after'] == report['content_before'], 'Audit changed content bytes'
    report['completed'] = True


out.mkdir(parents=True,exist_ok=True)
try:
    audit()
except Exception:
    report['errors'].append(traceback.format_exc())
finally:
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CATRUN_STAGE2_COLD_AUDIT',str(out/'report.json'),'completed',report['completed'])
if report['errors']:
    raise RuntimeError(report['errors'][-1])
