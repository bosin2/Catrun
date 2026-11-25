"""Check the final video against uninterrupted, directly captured PIE frames.

The black-bar check catches the editor viewport contamination observed when the
global Shot request was consumed by a different viewport. It supplements image
review and is specific to this letterboxed portal cinematic.
"""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageStat

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
args = parser.parse_args()
run = args.run.resolve()
report = json.loads((run/'report.json').read_text())
rows = [r for r in report['viewport_frames']
        if r.get('sequence') == 'departure' and 189 <= r['frame'] <= 322]
frame_ids = [r['frame'] for r in rows]
sizes = set()
bar_maxima = []
empty_frames = []
for row in rows:
    path, = run.glob(row['shot']+'*.png')
    with Image.open(path) as source:
        im = source.convert('RGB')
        w,h = im.size
        sizes.add((w,h))
        picture = round(w*9/16)
        top = (h-picture)//2
        assert top > 8, (w,h)
        bars = [im.crop((0,0,w,top-2)), im.crop((0,top+picture+2,w,h))]
        maximum = max(v[1] for bar in bars for v in bar.getextrema())
        bar_maxima.append({'frame':row['frame'],'maximum':maximum})
        if max(ImageStat.Stat(im.crop((0,top,w,top+picture))).mean) < 1:
            empty_frames.append(row['frame'])

video = run/'portal_review/Stage1_PawProbe_To_Portal_30fps.mp4'
info = json.loads(subprocess.check_output([
    'ffprobe','-v','error','-select_streams','v:0','-count_frames',
    '-show_entries','stream=nb_read_frames,r_frame_rate,width,height,duration',
    '-of','json',str(video)],text=True))['streams'][0]
checks = {
    'every_requested_frame_present_once': frame_ids == list(range(189,323)),
    'direct_pie_viewport_only': all(r.get('capture_method') == 'PIE viewport direct readback' for r in rows),
    'constant_native_dimensions': len(sizes) == 1,
    'letterbox_has_no_editor_view': all(r['maximum'] == 0 for r in bar_maxima),
    'no_blank_action_frame': not empty_frames,
    'one_video_frame_per_source_frame': int(info['nb_read_frames']) == len(rows),
    'normal_thirty_fps': info['r_frame_rate'] == '30/1',
}
result = {'success':all(checks.values()),'checks':checks,'video':info,
          'native_dimensions':sorted(sizes),'frames':len(rows),
          'nonblack_bars':[r for r in bar_maxima if r['maximum']],
          'empty_frames':empty_frames}
(run/'capture_integrity.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['success'] else 1)
