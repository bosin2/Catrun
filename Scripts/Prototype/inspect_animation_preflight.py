"""Read-only CDO, animation graph and skeleton preflight; no PIE/maps/saves."""
import json
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Expected no PIE'
result = {'world': editor.get_editor_world().get_path_name(), 'actors': {}, 'assets': {}, 'graphs': {}}

def value(v):
    if isinstance(v, (str, int, float, bool)) or v is None: return v
    return str(v)

def props(obj, names):
    out = {}
    for name in names:
        try: out[name] = value(obj.get_editor_property(name))
        except Exception as exc: out[name] = {'unavailable': str(exc)}
    return out

for path in ['/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor', '/Game/Characters/BlackCat/Blueprints/BP_Cat']:
    cls = unreal.load_class(None, path + '.' + path.rsplit('/', 1)[-1] + '_C')
    cdo = unreal.get_default_object(cls)
    mesh = cdo.get_editor_property('Mesh')
    row = {'class': cls.get_path_name(), 'mesh': props(mesh, ['skeletal_mesh_asset', 'anim_class', 'animation_mode', 'relative_location', 'relative_rotation', 'relative_scale3d'])}
    try: row['bones'] = [str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]
    except Exception as exc: row['bones_unavailable'] = str(exc)
    try: row['sockets'] = [str(x) for x in mesh.get_all_socket_names()]
    except Exception as exc: row['sockets_unavailable'] = str(exc)
    row['actor_properties'] = props(cdo, ['IdleAnim', 'RunAnim', 'WalkAnim', 'TurnLeftAnim', 'TurnRightAnim', 'PickupAnim', 'DoorOpenAnim', 'ArrivalLookAnim', 'SoundReactAnim', 'TurnPlayRate', 'bUseBlueprintAnimation'])
    try:
        capture = cdo.get_editor_property('CapturePresentation')
        row['capture'] = props(capture, ['bUseBlueprintPresentation', 'CatPickupAnimation', 'PickupPlayRate', 'MissingAnimationDuration', 'LeftHandBone', 'RightHandBone'])
    except Exception as exc: row['capture_unavailable'] = str(exc)
    result['actors'][path] = row

paths = ['/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final', '/Game/Characters/LivingArmor/Final/Meshes/SK_LivingArmor_Final',
    '/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnLeft90', '/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnRight90', '/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_Pickup',
    '/Game/Characters/BlackCat/Animations/AN_BlackCat_Body_Sway', '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_BasketEnter', '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Idle']
for path in paths:
    obj = unreal.load_asset(path)
    result['assets'][path] = {'class': obj.get_class().get_name(), 'properties': props(obj, ['skeleton', 'sequence_length', 'rate_scale', 'enable_root_motion', 'root_motion_root_lock'])} if obj else {'error': 'not found'}

for path in ['/Game/Characters/BlackCat/Final/Animations/ABP_Cat_Final', '/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor']:
    bp = unreal.load_asset(path)
    data = {'properties': props(bp, ['target_skeleton']), 'graphs': []}
    for graph in BP.list_graphs(bp):
        nodes = []
        for info in BP.get_node_infos(BP.find_nodes(graph)):
            row = {'name': info.node.get_name(), 'class': info.node.get_class().get_name(), 'type': info.type_id,
                'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in info.input_pins],
                'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in info.output_pins]}
            try:
                node = info.node.get_editor_property('node')
                row['anim_node'] = props(node, ['slot_name', 'group_name', 'sequence', 'blend_space', 'play_rate', 'loop_animation'])
            except Exception: pass
            nodes.append(row)
        data['graphs'].append({'name': graph.get_name(), 'path': graph.get_path_name(), 'nodes': nodes})
    result['graphs'][path] = data

out = Path(unreal.Paths.project_saved_dir()) / 'Prototype20261104' / 'animation-preflight-live.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print('ANIMATION_PREFLIGHT_SAVED', str(out))
print('WORLD_UNCHANGED', editor.get_editor_world().get_path_name(), 'NO_PIE', not editor.get_game_world())
