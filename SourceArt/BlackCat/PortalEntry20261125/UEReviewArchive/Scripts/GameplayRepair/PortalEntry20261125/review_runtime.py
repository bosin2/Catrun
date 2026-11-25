"""Quantify the requested beats in actual PIE footage; create a normal-speed clip.

This is not a replacement for viewing the contact sheets and seam frames.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
run = args.run.resolve()
contract = json.loads((root/'SourceArt/BlackCat/PortalEntry20261125/contract.json').read_text())
integration = json.loads((root/'Saved/PortalEntry20261125/integration_latest.json').read_text())
report = json.loads((run/'report.json').read_text())
timing = integration['timing']
rows = {r['frame']: r for r in report['viewport_frames'] if r.get('sequence') == 'departure'}
out = run/'portal_review'
out.mkdir(exist_ok=True)


def interval(a, b):
    return [rows[f] for f in range(a, b) if f in rows]


def bone(row, name):
    return row['visual']['bones'][name]


def distance_from_first(series, getter):
    start = getter(series[0])
    return max(math.dist(start, getter(row)) for row in series)


def project(row, point):
    pitch, yaw, roll = map(math.radians, row['view_rot'])
    assert abs(roll) < .001
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    forward, right, up = (cp*cy, cp*sy, sp), (-sy,cy,0), (-sp*cy,-sp*sy,cp)
    delta = [b-a for a,b in zip(row['view_pos'], point)]
    dot = lambda v: sum(a*b for a,b in zip(v,delta))
    half = dot(forward)*math.tan(math.radians(row['projected_horizontal_fov'])/2)
    return [.5+.5*dot(right)/half, .5-.5*dot(up)*(16/9)/half]


held = interval(timing['prep_start']-15, timing['prep_start'])
prep = interval(timing['prep_start'], timing['takeoff_start'])
# The camera manager can return the preceding cut's cached view on the cut's
# exact tick. Begin one tick later; the wiggle and entire push remain included.
push = interval(timing['prep_start']+1, timing['lift']+1)
probe = interval(timing['probe_start'], timing['prep_start'])
foot_drift = {name: distance_from_first(prep, lambda r: bone(r, name)) for name in ('paw_f_l', 'paw_f_r')}
still_camera = distance_from_first(held, lambda r:r['view_pos'])
still_head = distance_from_first(held, lambda r:bone(r,'head'))
push_camera = distance_from_first(push, lambda r:r['view_pos'])
hip = [(r['frame'], bone(r, 'pelvis')[0]) for r in prep]
extrema = [(f,y) for (fa,a),(f,y),(fb,b) in zip(hip,hip[1:],hip[2:]) if (y-a)*(b-y)<-1e-6]
visible_extrema = [(f,y) for f,y in extrema if abs(y-hip[0][1])>.08]
probe_features = [project(r, bone(r, n)) for r in probe for n in ('ear_tip_L','ear_tip_R','paw_f_l','paw_f_r')]
prep_features = [project(r, bone(r,n)) for r in push
                 for n in ('ear_tip_L','ear_tip_R','head','chest','paw_f_l','paw_f_r','paw_h_l','paw_h_r','tail_07')]
continuity = sorted(rows) == list(range(min(rows),max(rows)+1))
air = interval(timing['lift'],timing['air_end'])
rise = max(r['cat_root'][2] for r in air)-rows[timing['lift']]['cat_root'][2]
unoccluded_air = [r for r in air if r['cat_root'][1] > -373.1-25.]
air_features = [project(r,bone(r,n)) for r in unoccluded_air
                for n in ('ear_tip_L','ear_tip_R','head','paw_f_l','paw_f_r','paw_h_l','paw_h_r','tail_07')]
ripple_frames = [f for f,r in rows.items() if r.get('ripple')]
checks = {
    'actual_exit_travel_and_restored_control': report['success'],
    'continuous_thirty_fps_capture': continuity,
    'departure_within_9_to_12_seconds': 270<=timing['end']<=360,
    'cat_visible_through_probe_preparation_and_push': all(r['visual']['visible'] for r in probe+push),
    'half_second_still_head_and_camera': len(held)==15 and still_head<.1 and still_camera<.05,
    'front_paws_planted_during_preparation': max(foot_drift.values())<.2,
    'two_visible_pelvic_cycles': len(visible_extrema)==4,
    'same_stationary_camera_through_liftoff': push_camera<.05,
    'paw_and_ear_bones_framed_during_probe': all(.025<v<.975 for p in probe_features for v in p),
    'whole_cat_bones_framed_through_push': all(.025<v<.975 for p in prep_features for v in p),
    'high_upward_world_arc': rise>75.,
    'airborne_bones_framed_until_portal_occlusion': all(.025<v<.975 for p in air_features for v in p),
    'ripple_only_after_contact_without_collision': bool(ripple_frames) and min(ripple_frames)>=timing['contact']-1
        and max(ripple_frames)<=timing['contact']+11 and not any(obj['collision'] for f in ripple_frames for obj in rows[f]['ripple']),
}
result = {'success':all(checks.values()),'checks':checks,'timing':timing,'measurements':{
    'front_paw_drift_cm':foot_drift,'still_camera_cm':still_camera,'still_head_cm':still_head,
    'push_camera_cm':push_camera,'pelvis_extrema':visible_extrema,'root_rise_cm':rise,'ripple_frames':ripple_frames},
    'scope':'Actual exit-overlap PIE backbuffer, bone and camera telemetry. Mesh deformation and beat readability also require image review.'}
(out/'runtime_qa.json').write_text(json.dumps(result,indent=2))

selected = interval(timing['probe_start'],timing['air_end']+2)
paths = {}
for row in selected:
    path, = run.glob(row['shot']+'*.png')
    paths[row['frame']] = path
concat = out/'probe_to_portal.ffconcat'
lines=['ffconcat version 1.0']
for row in selected:
    filename=str(paths[row['frame']]).replace('\\','/').replace("'", "'\\''")
    lines += [f"file '{filename}'", 'duration 0.0333333333']
lines.append(lines[-2])
concat.write_text('\n'.join(lines)+'\n')
video = out/'Stage1_PawProbe_To_Portal_30fps.mp4'
with Image.open(paths[selected[0]['frame']]) as im:
    w,h=im.size
    picture=round(w*9/16)
    top=(h-picture)//2
picture_filter=f'crop={w}:{picture}:0:{top},pad=ceil(iw/2)*2:ceil(ih/2)*2'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-safe','0','-i',str(concat),
                '-vf',picture_filter,'-c:v','libx264','-crf','18','-preset','fast',
                '-pix_fmt','yuv420p','-r','30','-frames:v',str(len(selected)),
                '-movflags','+faststart',str(video)],check=True)
# Every third frame of the complete new action, plus every frame of both seams.
samples = sorted(set(range(timing['probe_start'],timing['air_end']+1,3)) |
                 set(range(timing['takeoff_start']-3,timing['takeoff_start']+4)) |
                 set(range(timing['bridge_end']-3,timing['bridge_end']+4)))
samples = [f for f in samples if f in paths]
for start in range(0,len(samples),12):
    batch=samples[start:start+12]
    sheet=Image.new('RGB',(1600,3*259),'#111820')
    draw=ImageDraw.Draw(sheet)
    for index,frame in enumerate(batch):
        x,y=(index%4)*400,(index//4)*259
        with Image.open(paths[frame]) as im:
            # Remove only letterbox bars; do not crop the actual cinematic view.
            w,h=im.size;picture=round(w*9/16);top=(h-picture)//2
            im=im.crop((0,top,w,top+picture));im.thumbnail((400,225))
            sheet.paste(im,(x+(400-im.width)//2,y))
        draw.text((x+8,y+231),f'f{frame} | {frame/30:.2f}s',fill='white')
    sheet.save(out/f'action_{start//12:02d}.jpg',quality=95)
print(json.dumps(result,indent=2))
print('CONTINUOUS_NORMAL_SPEED_VIDEO',video)
raise SystemExit(0 if result['success'] else 1)
