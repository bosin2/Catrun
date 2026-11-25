"""Read current Catrun audio presentation bindings without modifying packages."""
import hashlib
import json
from pathlib import Path
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/CatAudioDirector/Production20261112'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP

PATHS = (
    '/Game/Systems/Player/Interaction/BP_CatActions',
    '/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor',
    '/Game/Characters/LivingArmor/Final/Animations/ABP_ArmorPresentation',
    '/Game/Cinematics/Stage1/Portal/BP_Stage1PortalExit',
    '/Game/Cinematics/Stage1/Portal/BP_Stage1PortalPresentation',
    '/Game/Blueprints/BP_TutorialIntro',
)

def dirty():
    io = u.EditorLoadingAndSavingUtils
    return [p.get_path_name() for p in (*io.get_dirty_map_packages(), *io.get_dirty_content_packages())]

assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
assert not dirty(), dirty()
report = {'blueprints': {}, 'api': {}, 'sounds': [], 'source_hashes': {}}
for folder in ('Source/Catrun/Sound', 'Source/Catrun/Perception', 'Source/Catrun/Monster',
               'Source/Catrun/Pathfinding', 'Source/Catrun/Interaction'):
    for path in (ROOT / folder).rglob('*'):
        if path.is_file():
            report['source_hashes'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in PATHS:
    bp = u.EditorAssetLibrary.load_asset(path)
    assert bp, path
    cdo = u.get_default_object(bp.generated_class())
    row = {'variables': {}, 'graphs': {}, 'class': cdo.get_class().get_path_name()}
    for name in BP.list_variables(bp):
        try:
            value = cdo.get_editor_property(str(name))
            row['variables'][str(name)] = value.get_path_name() if isinstance(value, u.Object) else str(value)
        except Exception:
            pass
    for graph in BP.list_graphs(bp):
        nodes = []
        for info in BP.get_node_infos(BP.find_nodes(graph)):
            node = info.node
            nodes.append({'name': node.get_name(), 'type': info.type_id, 'pins': [
                {'name': str(p.get_pin_name()), 'direction': str(p.get_pin_direction()),
                 'value': str(p.get_pin_value()), 'links': [
                    [x.get_owning_node().get_name(), str(x.get_pin_name())] for x in p.list_connected_pins()]}
                for p in node.list_all_pins()]})
        row['graphs'][graph.get_name()] = nodes
    report['blueprints'][path] = row
for name in ('AnimationLibrary', 'AnimationBlueprintLibrary', 'SoundFactory', 'SoundAttenuation',
             'SoundConcurrency', 'MovieSceneAudioTrack', 'MovieSceneAudioSection'):
    cls = getattr(u, name, None)
    report['api'][name] = [n for n in dir(cls) if any(s in n.lower() for s in ('notif', 'sound', 'attenu', 'concurr', 'bone'))] if cls else None
registry = u.AssetRegistryHelpers.get_asset_registry()
for data in registry.get_assets_by_path('/Game/Audio', recursive=True):
    if str(data.asset_class_path.asset_name) in ('SoundWave', 'SoundCue'):
        sound = data.get_asset()
        report['sounds'].append({'path': sound.get_path_name(), 'class': sound.get_class().get_name(),
            'duration': float(sound.get_editor_property('duration'))})
assert not dirty(), dirty()
report['complete'] = True
(OUT / 'game_audio_probe.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print('CATRUN_AUDIO_PROBE_COMPLETE')
