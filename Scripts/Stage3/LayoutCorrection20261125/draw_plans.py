"""Measured CAD-style plan and in-game minimap raster, not an edited reference image."""
import json,sys
from pathlib import Path
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
data=json.loads((OUT/'applied.json').read_text(encoding='utf8'))
before=json.loads((OUT/'QA/before/snapshot.json').read_text(encoding='utf8'))
old=[]
for a in before['actors'].values():
    if not a['label'].startswith(('S3_Floor_','S3_Wall_','S3_D0','S3_D1','S3_D2','S3_H1','S3_H2','S3_H3','S3_GrandPillar_')):continue
    b=a['all_component_bounds'];lo=[c-e for c,e in zip(b['center'],b['extent'])];hi=[c+e for c,e in zip(b['center'],b['extent'])]
    old.append({'label':a['label'],'min':lo,'max':hi,'tags':['SoundFloor' if a['label'].startswith('S3_Floor_') else 'SoundWall']})
plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False
labels={'Entrance':'입구','Lobby':'로비','LowerHall':'하단 복도','Exhibition':'마왕 물품 전시방','Warehouse':'전시 물품 창고','CentralCorridor':'중앙 복도','CatBypass':'긴 캣홀','ControlAnnex':'왼쪽 추가 구간','ControlRoom':'제단실','UpperCorridor':'상단 복도','GateHall':'성문 홀'}
def plan(rows,name,title,annotations=False):
    fig,ax=plt.subplots(figsize=(8,13));fig.patch.set_facecolor('#f7f5ee');ax.set_facecolor('#f7f5ee')
    for tag,color in [('SoundFloor','#eee1c8'),('SoundWall','#252528')]:
        for b in rows:
            if tag not in b['tags']:continue
            lo,hi=b['min'],b['max'];ax.add_patch(Rectangle((lo[0]/100,lo[1]/100),(hi[0]-lo[0])/100,(hi[1]-lo[1])/100,facecolor=color,linewidth=0))
    if annotations:
        for key,(x0,y0,x1,y1) in data['rooms'].items():
            ax.text((x0+x1)/200,(y0+y1)/200,labels[key]+'\n'+f'{(x1-x0)/100:g} × {(y1-y0)/100:g} m',ha='center',va='center',fontsize=8,bbox=dict(facecolor='white',alpha=.75,edgecolor='none',pad=1.5))
        for key,p in data['portals'].items():
            x,y,_=p['position'];ax.plot(x/100,y/100,'o',markerfacecolor='none',markeredgecolor=('#64ae19' if p['kind']=='cat' else '#e9b321' if p['kind']=='door' else '#15945d'),markersize=13,markeredgewidth=2)
    ax.set_xlim(-13,13);ax.set_ylim(-1,43);ax.set_aspect('equal');ax.set_xlabel('도면 가로 X (m)');ax.set_ylabel('도면 세로 Y (m)');ax.set_title(title);ax.grid(alpha=.12);fig.tight_layout();fig.savefig(OUT/name,dpi=140);plt.close(fig)
plan(old,'plan_before.png','수정 전 · 저장된 실제 액터 바운드')
plan(data['bounds'],'plan_after.png','수정 후 · 실제 바닥/벽 바운드 및 외곽 치수',True)
floors=[b for b in data['bounds'] if 'SoundFloor' in b['tags']]
lo=[min(b['min'][i] for b in floors) for i in (0,1)];hi=[max(b['max'][i] for b in floors) for i in (0,1)]
center=[(a+b)/2 for a,b in zip(lo,hi)];size=[hi[1]-lo[1],hi[0]-lo[0]]
w,h=1680,round(1680*size[1]/size[0]);im=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(im)
def project(x,y):return((y-lo[1])/size[0]*w,(hi[0]-x)/size[1]*h)
def rect(a,b,color):
    p,q=project(a[0],a[1]),project(b[0],b[1]);draw.rectangle((min(p[0],q[0]),min(p[1],q[1]),max(p[0],q[0]),max(p[1],q[1])),fill=color)
for tag,color in [('SoundFloor',(155,151,142,255)),('SoundWall',(44,43,47,255))]:
    for b in data['bounds']:
        if tag in b['tags']:rect(b['min'],b['max'],color)
for p in data['portals'].values():
    x,y,_=p['position'];width=60 if p['kind']=='cat' else 140
    a,b=((x-width/2,y-16),(x+width/2,y+16)) if p['orientation']=='h' else ((x-16,y-width/2),(x+16,y+width/2))
    rect(a,b,(155,151,142,255))
im.save(OUT/'T_Floorplan_Stage3.png')
(OUT/'minimap_projection.json').write_text(json.dumps({'center':center,'size':size,'yaw':0,'pixels':[w,h]},indent=2))
print('PLANS_DRAWN',center,size)
