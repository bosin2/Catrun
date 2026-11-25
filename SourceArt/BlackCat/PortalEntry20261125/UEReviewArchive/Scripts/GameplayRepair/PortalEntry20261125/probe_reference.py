"""Read-only Stage1 rig/sequence reference for the animation production chat."""
from pathlib import Path
import hashlib
import json
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/GameplayRepair'))
import stage1_departure_shots as shots

OUT = ROOT / 'Saved/PortalEntry20261125/Reference'
OUT.mkdir(parents=True, exist_ok=True)
assert not shots.h.dirty()
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage1')
actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
pawn = next(a for a in actors if isinstance(a, u.Character) and 'BP_Cat' in a.get_class().get_name())
mesh = pawn.get_component_by_class(u.SkeletalMeshComponent)
skeletal_mesh = mesh.get_skeletal_mesh_asset()
sequence = u.load_asset('/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit')
shots.h.CAMERAS = shots.CAMERA_NAMES
report = {'sequence': shots.h.describe_sequence(sequence), 'mesh': skeletal_mesh.get_path_name(),
          'skeleton': skeletal_mesh.get_editor_property('skeleton').get_path_name(),
          'mesh_relative_transform': mesh.get_relative_transform().export_text(),
          'bones': [str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())], 'clips': {}}
director = next(a for a in actors if a.get_class().get_name() == 'BP_Stage1PortalExit_C')
report['cinematic_timeout'] = director.get_editor_property('CinematicTimeout')
options = u.AnimPoseEvaluationOptions()
options.set_editor_property('evaluation_type', u.AnimDataEvalType.SOURCE)
options.set_editor_property('optional_skeletal_mesh', skeletal_mesh)
options.set_editor_property('should_retarget', False)
for path in (shots.CLIPS[1], shots.CLIPS[2]):
    clip = u.load_asset(path)
    row = {'path': path, 'length': clip.get_editor_property('sequence_length'),
           'root_motion': clip.get_editor_property('enable_root_motion'), 'poses': []}
    for frame in ([0] if 'Idle' in path else [0, 8, 10, 12, 14, 16, 17, 17.5, 18, 19, 20, 24, 30, 35]):
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(clip, frame / 30., options)
        bones = {}
        for bone in report['bones']:
            transform = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD)
            bones[bone] = {'position': [transform.translation.x, transform.translation.y, transform.translation.z],
                           'rotation': [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w]}
        row['poses'].append({'source_frame_30fps': frame, 'bones': bones})
    report['clips'][clip.get_name()] = row
    export = u.AssetExportTask()
    export.object = clip
    export.filename = str(OUT / (clip.get_name() + '_Reference.fbx'))
    export.exporter = u.AnimSequenceExporterFBX()
    export.automated = True
    export.prompt = False
    export.replace_identical = True
    settings = u.FbxExportOption()
    settings.set_editor_property('export_preview_mesh', False)
    settings.set_editor_property('export_morph_targets', False)
    export.options = settings
    row['export_success'] = u.Exporter.run_asset_export_task(export)
    row['export'] = export.filename
    if row['export_success']:
        row['export_sha256'] = hashlib.sha256(Path(export.filename).read_bytes()).hexdigest()
assert not shots.h.dirty()
(OUT / 'reference.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PORTAL_ENTRY_REFERENCE', str(OUT / 'reference.json'))
