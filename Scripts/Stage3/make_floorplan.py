"""Draw the minimap from the saved map's measured collision/actor footprints."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Stage3Integration20261125'
r=json.loads((OUT/'map_report.json').read_text())
size=(1700,880);image=Image.new('RGBA',size,(0,0,0,0));draw=ImageDraw.Draw(image)
# CaptureYaw 0: +Y right, +X up. Bounds include the external exit landing.
def project(x,y):return (y/4250*size[0],(1200-x)/2200*size[1])
def rect(lo,hi,color):
    a=project(lo[0],hi[1]);b=project(hi[0],lo[1])
    draw.rectangle((min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])),fill=color)
for b in r['bounds']:
    if 'SoundFloor' in b['tags']:rect(b['min'],b['max'],(155,151,142,255))
for b in r['bounds']:
    if 'SoundWall' in b['tags']:rect(b['min'],b['max'],(44,43,47,255))
    elif 'SoundObstacle' in b['tags'] and b['min'][2]<20:rect(b['min'],b['max'],(91,87,86,255))
# Openings use measured portal positions, not the full frame bounding box.
for p in r['portals'].values():
    x,y,_=p['position'];w=p.get('clear_width',60 if p['kind']=='cat' else 140)
    lo=(x-w/2,y-16) if p['orientation']=='h' else (x-16,y-w/2)
    hi=(x+w/2,y+16) if p['orientation']=='h' else (x+16,y+w/2)
    rect(lo,hi,(155,151,142,255))
image.save(OUT/'T_Floorplan_Stage3.png')
print(OUT/'T_Floorplan_Stage3.png')
