"""Read local UE import and material APIs without saving any package."""
from pathlib import Path
import json
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
clip = u.load_asset('/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalJumpIn')
data = clip.get_editor_property('asset_import_data')
report = {'import_class': data.get_class().get_name(), 'import': {}, 'api': {}}
for name in ('import_translation', 'import_rotation', 'import_uniform_scale', 'convert_scene',
             'force_front_x_axis', 'convert_scene_unit', 'preserve_local_transform',
             'use_default_sample_rate', 'custom_sample_rate'):
    try:
        report['import'][name] = str(data.get_editor_property(name))
    except Exception as exc:
        report['import'][name] = 'unavailable: ' + str(exc)
for cls, name in ((u.MovieSceneComponentMaterialTrack, 'set_material_info'),
                  (u.MovieSceneComponentMaterialParameterSection, 'add_scalar_parameter_key'),
                  (u.FbxImportUI, 'set_editor_property'),
                  (u.EditorActorSubsystem, 'spawn_actor_from_class')):
    report['api'][cls.__name__ + '.' + name] = getattr(cls, name).__doc__
output = root / 'Saved/PortalEntry20261125/preflight.json'
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PORTAL_PREFLIGHT', str(output))
