"""Compare rendered cat-visible and cat-hidden captures of the same portal camera frame."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def face_light(root,rendered):
    # Matched background captures isolate actual face pixels from blue corridor walls.
    import numpy as np
    result=[]
    for frame in (57,96,138,176):
        name=f'Frame_{frame:03d}.png'
        screen=rendered['samples'][frame]['screen']
        hx,hy=screen['head']
        ears=[xy for b,xy in screen.items() if b.lower() in ('ear_tip_l','ear_tip_r')]
        half_width=abs(ears[0][0]-ears[1][0])*.72
        head_height=hy-min(p[1] for p in ears)
        with Image.open(root/name) as img, Image.open(root/'FaceBackground'/name) as bg:
            w,h=img.size
            window=tuple(round(v) for v in ((hx-half_width)*w,(hy-.7*head_height)*h,
                                              (hx+half_width)*w,(hy+.42*head_height)*h))
            face=np.asarray(img.convert('RGB').crop(window),dtype=np.int16)
            background=np.asarray(bg.convert('RGB').crop(window),dtype=np.int16)
        mask=np.max(np.abs(face-background),axis=2)>3
        # Exclude the bright green eye material from the dark-fur sample.
        fur=face[mask & (face[:,:,1]<=face[:,:,2]*1.12)]
        assert len(fur)>300,(frame,window,len(fur))
        blue=fur[:,2]-(fur[:,0]+fur[:,1])*.5
        result.append(dict(frame=frame,fur_pixels=len(fur),blue_over_redgreen=float(blue.mean()),
                           blue_luma=float(fur[:,2].mean()),blue_dominant_fraction=float((blue>8).mean())))
    return result


def differences(folder):
    result=[]
    for path in sorted((folder/'Visible').glob('Frame_*.png')):
        with Image.open(path) as vis,Image.open(folder/'Hidden'/path.name) as hid:
            assert vis.size==hid.size==(1280,720)
            diff=ImageChops.difference(vis.convert('RGB'),hid.convert('RGB'))
            channels=diff.split()
            maximum=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
            hist=maximum.histogram()
        result.append({'frame':int(path.stem.split('_')[-1]),'pixels_different':sum(hist[1:]),
                       'pixels_above_3':sum(hist[4:]),'max_channel_delta':max(i for i,n in enumerate(hist) if n)})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames_dir',type=Path)
    p.add_argument('--depth-dir',type=Path,help='Focused same-sequence geometry and shadow captures.')
    args=p.parse_args()
    root=args.frames_dir
    depth_root=args.depth_dir or root
    rendered=json.loads((root/'report.json').read_text(encoding='utf-8'))
    depth_report=json.loads((depth_root/'report.json').read_text(encoding='utf-8'))
    assert all(row['completed'] and row['packages_unchanged'] for row in (rendered,depth_report))
    if rendered.get('sequence_sha256'):
        assert rendered['sequence_sha256']==depth_report['sequence_sha256']
    if depth_root!=root:
        for sample in depth_report['samples']:
            previous=rendered['samples'][sample['frame']]
            assert abs(previous['mesh_rear_y']-sample['mesh_rear_y'])<.01
            assert all(abs(a-b)<.01 for a,b in zip(previous['image']['camera_location'],sample['camera']))
    result=differences(root/'Occlusion')
    assert len(result)==5,result
    assert result[0]['pixels_above_3']>100,('Cat in front must change visible pixels',result[0])
    depth=differences(depth_root/'Depth')
    no_shadow=differences(depth_root/'NoCatShadow')
    lighting=face_light(root,rendered)
    print(json.dumps(dict(lit=result,visible_surface_depth=depth,lit_without_cat_shadow=no_shadow,face_lighting=lighting),indent=2))
    assert [r['frame'] for r in depth]==[266,280,291,293,294],depth
    assert depth[0]['pixels_different']>1000,('Foreground cat must alter geometric depth',depth[0])
    assert all(r['pixels_different']==0 for r in depth[-3:]),('Cat surface visible at portal exit',depth)
    assert [r['frame'] for r in no_shadow]==[291,293],no_shadow
    assert lighting[-1]['blue_over_redgreen']>lighting[0]['blue_over_redgreen']+3,('Face blue gradient',lighting)


if __name__=='__main__':
    main()
