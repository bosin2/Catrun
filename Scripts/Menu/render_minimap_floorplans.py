"""Deterministic geometry-only minimaps. Requires Pillow; no image model or assets.

python Scripts/Menu/render_minimap_floorplans.py [--input geometry.json] [--out dir]
Each projected triangle/polygon contributes to a binary union mask. Only the
union boundary is outlined, never triangle or tile edges. No dilation, gap fill,
room guessing, automatic cropping, or changed marker projection is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT/'Saved/GameplayRepair20261112/BasketUsability/Floorplans'
MAPS = ('Tutorial', 'Stage1', 'Stage2', 'SoundTest_Tutorial', 'SoundTest_Stage1', 'SoundTest_Stage2')
SIZE, SCALE = 1024, 2
FLOOR = (65, 80, 89, 255)
FLOOR_EDGE = (111, 128, 129, 255)
WALL = (178, 158, 119, 255)
WALL_EDGE = (213, 192, 148, 255)


def project(point, frame, size):
    assert abs(float(frame['yaw'])) < .0001
    x, y = point
    cx, cy = frame['center']
    width, height = frame['size']
    # Same yaw-0 orthographic view and native marker mapping as the original capture.
    return ((.5+(y-cy)/width)*size, (.5-(x-cx)/height)*size)


def polygons(actor):
    if actor['method'] == 'lod0_projected_triangle_union':
        vertices, indices = actor['points_xy'], actor['triangles']
        for offset in range(0, len(indices), 3):
            yield [vertices[indices[offset+i]] for i in range(3)]
    else:
        yield actor['polygon_xy']


def fill(mask, color):
    layer = Image.new('RGBA', mask.size, color)
    layer.putalpha(mask)
    return layer


def render(name, data, out):
    size = SIZE*SCALE
    masks = {role: Image.new('L', (size, size), 0) for role in ('floor', 'wall')}
    draws = {role: ImageDraw.Draw(mask) for role, mask in masks.items()}
    skipped, counts, clipped = 0, {'floor': 0, 'wall': 0}, []
    for actor in data['geometry']:
        role = actor['role']
        bounds = [project(p, data['frame'], size) for p in actor['bounds_polygon_xy']]
        if any(x < 0 or y < 0 or x > size or y > size for x, y in bounds):
            clipped.append(actor['label'])
        for polygon in polygons(actor):
            points = [project(p, data['frame'], size) for p in polygon]
            area = abs(sum(points[i][0]*points[(i+1)%len(points)][1]
                           -points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points))))*.5
            if area < .001:  # Vertical triangle projects to zero area; it is not a footprint.
                skipped += 1
                continue
            draws[role].polygon(points, fill=255)
            counts[role] += 1
    assert not clipped, f'{name}: architecture exceeds the stored marker frame: {clipped}'
    assert masks['floor'].getbbox() and masks['wall'].getbbox(), f'{name}: empty architecture'
    # Inner boundaries only: preserving the original footprint also preserves doorway gaps.
    image = fill(masks['floor'], FLOOR)
    edge = ImageChops.subtract(masks['floor'], masks['floor'].filter(ImageFilter.MinFilter(9)))
    image = Image.alpha_composite(image, fill(edge, FLOOR_EDGE))
    image = Image.alpha_composite(image, fill(masks['wall'], WALL))
    edge = ImageChops.subtract(masks['wall'], masks['wall'].filter(ImageFilter.MinFilter(5)))
    image = Image.alpha_composite(image, fill(edge, WALL_EDGE))
    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    path = out/f'Minimap_{name}.png'
    image.save(path, optimize=True)
    image.resize((240, 240), Image.Resampling.LANCZOS).save(out/f'Preview_{name}_240.png')
    return image, dict(image=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        frame=data['frame'], floor_count=data['floor_count'], wall_count=data['wall_count'],
        actual_mesh_count=data['actual_mesh_count'], bounds_approximation_count=data['bounds_approximation_count'],
        geometry_sha256=data['geometry_sha256'], projected_polygons=counts, skipped_degenerate_polygons=skipped,
        clipped_actors=clipped, opaque_bounds_px=image.getbbox(),
        floor_coverage=sum(masks['floor'].histogram()[1:])/(size*size),
        wall_coverage=sum(masks['wall'].histogram()[1:])/(size*size))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT/'geometry.json')
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding='utf8'))
    assert source.get('completed') and all(name in source['maps'] for name in MAPS), 'Export all six maps first'
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'completed': False, 'maps': {}, 'source': str(args.input),
              'source_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
              'size': [SIZE, SIZE], 'projection': source['projection'], 'limitations': source['limitations'],
              'rendering': 'Supersampled binary floor/wall union; inward outlines; no dilation or invented geometry'}
    sheet = Image.new('RGB', (3*264, 2*286), (24, 28, 33))
    draw = ImageDraw.Draw(sheet)
    try:
        for index, name in enumerate(MAPS):
            image, metadata = render(name, source['maps'][name], args.out)
            report['maps'][name] = metadata
            x, y = (index%3)*264+12, (index//3)*286+30
            preview = image.resize((240, 240), Image.Resampling.LANCZOS)
            sheet.paste(preview, (x, y), preview)
            draw.text((x, y-21), name, fill=(225, 224, 214))
        sheet.save(args.out/'Floorplans_240_comparison.png')
        report['completed'] = True
    finally:
        (args.out/'render_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    print(args.out/'render_report.json')


if __name__ == '__main__':
    main()
