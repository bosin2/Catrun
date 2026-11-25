"""Copy a completed animation handoff from the explicitly named production chat."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
args = parser.parse_args()
source = args.source.resolve()
root = Path(__file__).resolve().parents[3]
destination = root/'SourceArt/BlackCat/PortalEntry20261125'
handoff = json.loads((source/'handoff.json').read_text(encoding='utf-8'))
assert handoff['ready_for_import'] is True, 'Production has not released the animations yet'
assert handoff['target_skeleton'] == '/Game/Characters/BlackCat/Final/Skeletons/SKEL_BlackCat_Final'
assert handoff['bone_count'] == 78 and not handoff['mesh_in_fbx'] and not handoff['root_motion']
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for entry in handoff['files']:
    path = Path(entry['path'])
    assert path.resolve().parent == source and sha(path) == entry['sha256'], path
roundtrip = json.loads(Path(handoff['fbx_roundtrip_qa']).read_text())
preservation = json.loads(Path(handoff['preservation_qa']).read_text())
assert all(preservation['original_asset_unchanged'].values())
assert all(preservation['original_actions_unchanged'].values())
for clip in handoff['clips']:
    qa = roundtrip[clip['name']]
    assert qa['bones'] == 78 and qa['meshes'] == 0 and qa['actions'] == 1
    assert qa['bone_names_match'] and qa['hierarchy_match']
    assert qa['max_position_error_m'] < 1e-5 and qa['max_rest_matrix_error'] < 1e-4
destination.mkdir(parents=True,exist_ok=True)
for entry in handoff['files']:
    path = Path(entry['path'])
    target = destination/path.name
    assert not target.exists() or sha(target) == entry['sha256'], 'A previous receipt must be versioned, not overwritten'
    shutil.copy2(path,target)
    assert sha(target) == entry['sha256']
shutil.copy2(source/'handoff.json',destination/'handoff.json')
for path in (Path(handoff['fbx_roundtrip_qa']),Path(handoff['preservation_qa']),
             source/'QA/motion_metrics.json',source/'QA/contact_samples.json',
             Path(handoff['normal_speed_full_body_video'])):
    assert path.is_file(), path
    target=destination/path.relative_to(source)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,target)
names=('probe','prep','takeoff')
settings={k:v for k,v in handoff['recommended_ue_import'].items()
          if k in ('import_uniform_scale','convert_scene','force_front_x_axis','convert_scene_unit','preserve_local_transform')}
clips={key:{'file':Path(clip['fbx']).name,'sha256':sha(destination/Path(clip['fbx']).name),
            'asset':clip['name'],'import_settings':settings}
       for key,clip in zip(names,handoff['clips'],strict=True)}
probe,prep,takeoff=handoff['clips']
contract={'production_status':'received_and_reviewed','source_chat':'01a2107b-42cf-7283-91ba-0c114fc29bba',
          'handoff_sha256':sha(destination/'handoff.json'),'clips':clips,
          'probe_frames':round(probe['duration_seconds']*30),'prep_frames':round(prep['duration_seconds']*30),
          'takeoff_frames':round(takeoff['duration_seconds']*30),
          'takeoff_liftoff_frame':takeoff['hind_liftoff_source_frame_30fps'],
          'jump_air_source_frame':takeoff['existing_jump_next_source_frame_30fps'],
          'contact_frame':probe['contact_source_frame_30fps'],'contact_bone':probe['tap_paw'],
          'contact_point_blender_local_m':probe['contact_point_blender_local_m'],
          'air_frames':39,'arc_height_cm':80.,
          'surface_review_note':handoff['known_limitations']}
(destination/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'received':str(destination),'contract':contract},indent=2,ensure_ascii=False))
