"""Rasterize current reflected world bounds in the reference plan orientation."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'Saved/Stage3OrientationFix20261125'
data=json.loads((OUT/'applied.json').read_text())
rows=data['bounds'];floors=[b for b in rows if 'SoundFloor' in b['tags']]
lo=[min(b['min'][i] for b in floors) for i in (0,1)]
hi=[max(b['max'][i] for b in floors) for i in (0,1)]
size=[hi[i]-lo[i] for i in (0,1)];center=[(lo[i]+hi[i])/2 for i in (0,1)]
w,h=round(1680*size[0]/size[1]),1680
im=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(im)
def project(x,y):return((x-lo[0])/size[0]*w,(y-lo[1])/size[1]*h)
def rect(a,b,color):
    p,q=project(*a[:2]),project(*b[:2])
    draw.rectangle((min(p[0],q[0]),min(p[1],q[1]),max(p[0],q[0]),max(p[1],q[1])),fill=color)
for tag,color in [('SoundFloor',(155,151,142,255)),('SoundWall',(44,43,47,255))]:
    for b in rows:
        if tag in b['tags']:rect(b['min'],b['max'],color)
portals=json.loads((ROOT/'Saved/Stage3LayoutCorrection20261125/applied.json').read_text(encoding='utf8'))['portals']
for p in portals.values():
    x,y,_=p['position'];y=-y;width=60 if p['kind']=='cat' else 140
    a,b=((x-width/2,y-16),(x+width/2,y+16)) if p['orientation']=='h' else ((x-16,y-width/2),(x+16,y+width/2))
    rect(a,b,(155,151,142,255))
im.save(OUT/'T_Floorplan_Stage3.png')
(OUT/'minimap_projection.json').write_text(json.dumps({'center':center,'size':size,'yaw':-90,'pixels':[w,h]},indent=2))
print('REFERENCE_ORIENTATION_MINIMAP',center,size)
