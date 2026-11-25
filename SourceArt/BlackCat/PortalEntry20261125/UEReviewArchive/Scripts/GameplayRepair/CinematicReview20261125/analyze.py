"""Make review videos/contact sheets and quantify actual captured frame coverage."""
import argparse
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageStat

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
args = parser.parse_args()
run = args.run.resolve()
report = json.loads((run / 'report.json').read_text(encoding='utf-8'))
out = run / 'review'
out.mkdir(exist_ok=True)
summary = {'runtime_success': report.get('success'), 'runtime_error': report.get('error'), 'sequences': {}}

for sequence, last in [('departure', 312), ('arrival', 378)]:
    rows = [r for r in report['viewport_frames'] if r.get('sequence') == sequence]
    for row in rows:
        matches = list(run.glob(row['shot'] + '*.png'))
        assert len(matches) == 1, (row['shot'], matches)
        row['image_path'] = str(matches[0])
    if not rows:
        continue
    frames = [r['frame'] for r in rows]
    last = rows[-1].get('sequence_end', last)
    deltas = [b - a for a, b in zip(frames, frames[1:])]
    stats = {'captures': len(rows), 'first_frame': frames[0], 'last_frame': frames[-1],
             'missing_frames': sorted(set(range(frames[0], frames[-1] + 1)) - set(frames)),
             'largest_frame_step': max(deltas, default=0), 'expected_end': last}
    camera = []
    paws = []
    for prev, row in zip(rows, rows[1:]):
        if 'view_pos' in prev and 'view_pos' in row:
            rotation = [abs((b - a + 180) % 360 - 180) for a, b in zip(prev['view_rot'], row['view_rot'])]
            camera.append({'frame': row['frame'], 'distance_cm': math.dist(prev['view_pos'], row['view_pos']),
                           'max_angle_deg': max(rotation)})
        a, b = prev.get('visual', {}), row.get('visual', {})
        if a.get('visible') and b.get('visible'):
            paws.append({'frame': row['frame'], 'max_bone_step_cm': max(math.dist(xyz, b['bones'][bone])
                         for bone, xyz in a['bones'].items())})
    stats['largest_camera_steps'] = sorted(camera, key=lambda x: x['max_angle_deg'], reverse=True)[:16]
    stats['largest_bone_steps'] = sorted(paws, key=lambda x: x['max_bone_step_cm'], reverse=True)[:16]
    concat = out / (sequence + '.ffconcat')
    lines = ['ffconcat version 1.0']
    for index, row in enumerate(rows):
        path = row['image_path'].replace('\\', '/').replace("'", "'\\''")
        duration = ((rows[index + 1]['frame'] - row['frame']) / 30. if index + 1 < len(rows) else 1 / 30.)
        lines.extend([f"file '{path}'", f'duration {max(duration, 1 / 30):.8f}'])
    lines.append(lines[-2])
    concat.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    video = out / (sequence + '.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-safe', '0', '-i', str(concat),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', str(video)], check=True)
    stats['video'] = str(video)
    sampled = [row for index, row in enumerate(rows) if index == 0 or row['frame'] // 5 != rows[index - 1]['frame'] // 5]
    sheets = []
    for start in range(0, len(sampled), 20):
        batch = sampled[start:start + 20]
        sheet = Image.new('RGB', (1600, 4 * 204), '#121820')
        draw = ImageDraw.Draw(sheet)
        for i, row in enumerate(batch):
            x, y = (i % 5) * 320, (i // 5) * 204
            with Image.open(row['image_path']) as im:
                im.thumbnail((320, 180))
                sheet.paste(im, (x + (320 - im.width) // 2, y))
            draw.text((x + 6, y + 184), f"{sequence} f{row['frame']:03d}  {row['frame']/30:.2f}s", fill='white')
        target = out / f'{sequence}_sheet_{start // 20:02d}.jpg'
        sheet.save(target, quality=93)
        sheets.append(str(target))
    stats['sheets'] = sheets
    summary['sequences'][sequence] = stats

(out / 'analysis.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
