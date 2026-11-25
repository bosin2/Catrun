"""Compare planted feet in imported source and actual compressed poses."""
from pathlib import Path
import json
import math
import sys
import unreal as u

sys.path.insert(0,str(Path(__file__).resolve().parent))
import integrate as entry

contract=json.loads((entry.SOURCE/'contract.json').read_text())
report={}
mesh=u.load_asset(entry.MESH)
bounds=mesh.get_imported_bounds()
print('CAT_IMPORTED_BOUNDS',entry.xyz(bounds.origin),entry.xyz(bounds.box_extent))
for key,spec in contract['clips'].items():
    clip=u.load_asset(entry.FOLDER+'/'+spec['asset'])
    by_mode={}
    for mode in (u.AnimDataEvalType.SOURCE,u.AnimDataEvalType.COMPRESSED):
        options=u.AnimPoseEvaluationOptions()
        options.evaluation_type=mode
        options.optional_skeletal_mesh=u.load_asset(entry.MESH)
        options.should_retarget=True
        rows=[]
        for frame in range(contract[key+'_frames']+1):
            pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,frame/30,options)
            rows.append({n:entry.xyz(u.AnimPoseExtensions.get_bone_pose(pose,n,u.AnimPoseSpaces.WORLD).translation)
                         for n in entry.BONES})
        drift={n:2*max(math.dist(row[n],rows[0][n]) for row in rows) for n in ('paw_F_L','paw_F_R')}
        by_mode[str(mode)]={'front_paw_drift_world_cm':drift,'poses':rows}
    report[key]=by_mode
bridge=u.load_asset(entry.FOLDER+'/'+contract['clips']['takeoff']['asset'])
jump=u.load_asset(entry.old.CLIPS[2])
seam=entry.seam(bridge,bridge.sequence_length*30,jump,contract['jump_air_source_frame'],True)
(entry.OUT/'compressed_seam_qa.json').write_text(json.dumps(seam,indent=2))
print('COMPRESSED_JUMP_SEAM',max(v['distance_world_cm'] for v in seam.values()),max(v['angle_deg'] for v in seam.values()))
assert not entry.h.dirty(),entry.h.dirty()
(entry.OUT/'imported_pose_qa.json').write_text(json.dumps(report,indent=2))
print('IMPORTED_POSE_QA', {k:{m:r['front_paw_drift_world_cm'] for m,r in rows.items()} for k,rows in report.items()})
assert max(report['prep'][str(u.AnimDataEvalType.COMPRESSED)]['front_paw_drift_world_cm'].values()) < .05
