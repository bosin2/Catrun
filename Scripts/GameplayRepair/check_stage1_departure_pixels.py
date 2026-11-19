"""Compare rendered cat-visible and cat-hidden captures of the same portal camera frame."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames_dir',type=Path)
    args=p.parse_args()
    root=args.frames_dir
    rendered=json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert rendered['completed'] and rendered['packages_unchanged']
    result=[]
    for path in sorted((root/'Occlusion'/'Visible').glob('Frame_*.png')):
        with Image.open(path) as vis, Image.open(root/'Occlusion'/'Hidden'/path.name) as hid:
            diff=ImageChops.difference(vis.convert('RGB'),hid.convert('RGB'))
            channels=diff.split()
            maximum=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
            hist=maximum.histogram()
        result.append({'frame':int(path.stem.split('_')[-1]),'pixels_different':sum(hist[1:]),
                       'pixels_above_3':sum(hist[4:]),'max_channel_delta':max(i for i,n in enumerate(hist) if n)})
    assert len(result)==5,result
    assert result[0]['pixels_above_3']>100,('Cat in front must change visible pixels',result[0])
    assert all(r['pixels_above_3']==0 for r in result[-3:]),('Visible mesh reappears behind portal',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
