"""Generate a dimensioned approval diagram from the measured map, not an image edit."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3ApprovalAudit20261125'
snapshot = json.loads((OUT / 'QA/before/snapshot.json').read_text(encoding='utf8'))
proposal = json.loads((OUT / 'proposal_b.json').read_text(encoding='utf8'))
plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 10})

def rect(ax, xy, color, **kwargs):
    x0, y0, x1, y1 = xy
    ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, facecolor=color, **kwargs))

def bounds(row):
    c = row['center']; e = row['extent']
    return c[0]-e[0], -c[1]-e[1], c[0]+e[0], -c[1]+e[1]

fig, axes = plt.subplots(1, 2, figsize=(15, 8), facecolor='#f4f2ee')
old_route = [(520,2140),(520,2380),(150,2380),(150,2100)]
new_route = proposal['recommended_B1_conditioned_on_additional_approval']['armor_route_canonical_xy']
for ax, proposed in zip(axes, (False, True)):
    ax.set_facecolor('#e4e0da')
    # Actual saved floor footprint; convert world -Y back into drawing +Y.
    for row in snapshot['actors'].values():
        if row['label'].startswith('S3_Floor_'):
            rect(ax, bounds(row['all_component_bounds']), '#fffaf0', zorder=0)
    for row in snapshot['actors'].values():
        label = row['label']
        if not label.startswith('S3_Wall_'):
            continue
        if proposed and label in proposal['virtual_removals_only']:
            continue
        rect(ax, bounds(row['colliding_bounds']), '#61707c' if label in proposal['virtual_removals_only'] else '#383b40', zorder=2)
    if proposed:
        for b in proposal['wall_boxes_canonical_xy'].values():
            rect(ax, b, '#b64f28', zorder=3)
    # Existing console, P2 weight and docking footprint retain measured locations.
    for label, color, text in [('S3_Console','#aaa296','조작대'),('S3_Statue2','#80716b','중량추'),('S3_Plate2','#9a7ba8','도킹')]:
        row = next(a for a in snapshot['actors'].values() if a['label'] == label)
        b = bounds(row['all_component_bounds'])
        rect(ax, b, color, alpha=.8, zorder=3)
        ax.text((b[0]+b[2])/2, (b[1]+b[3])/2, text, ha='center', va='center', fontsize=9, zorder=4)
    e3_y = 2290 if proposed else 2240
    rect(ax, (335,e3_y-30,415,e3_y+30), '#d8aa36', edgecolor='#7b5d1f', zorder=5)
    ax.text(375,e3_y,'장치',ha='center',va='center',fontsize=9,zorder=6)
    route = new_route if proposed else old_route
    closed = route + [route[0]]
    ax.plot([p[0] for p in closed],[p[1] for p in closed],color='#286bb0',lw=2,ls='--',zorder=4)
    ax.add_patch(Circle(route[0],35,facecolor='#6f9fcd',edgecolor='#204f83',zorder=6))
    ax.text(route[0][0],route[0][1],'갑옷',fontsize=8,ha='center',va='center',zorder=7)
    ax.add_patch(Circle((375,2010),20,facecolor='#252525',zorder=6))
    ax.text(375,1972,'고양이 Ø40cm',ha='center',fontsize=8)
    ax.annotate('',xy=(760,2335),xytext=(760,2210),arrowprops={'arrowstyle':'->','color':'#85625a','lw':2})
    ax.text(-255,2010,'하단 연결부',ha='center',va='center',fontsize=9)
    ax.text(-250,2475,'상단 복도',ha='center',va='center',rotation=90,fontsize=9)
    ax.set_xlim(-445,1000); ax.set_ylim(1770,2630); ax.set_aspect('equal')
    ax.set_xticks(range(-400,1001,200)); ax.set_yticks(range(1800,2601,200))
    ax.set_xticklabels([f'{v/100:g}' for v in range(-400,1001,200)])
    ax.set_yticklabels([f'{v/100:g}' for v in range(1800,2601,200)])
    ax.grid(alpha=.14,zorder=1)
    ax.set_xlabel('도면 X (m)'); ax.set_ylabel('도면 Y (m)')
    ax.set_title('승인 요청안 · 외곽 10×6m 유지' if proposed else '현재 저장 맵 · 작은 ㄴ벽 1개',fontweight='bold',pad=16)
    if proposed:
        ax.annotate('',xy=(680,2375),xytext=(680,2250),arrowprops={'arrowstyle':'<->','color':'#923b1d'})
        ax.text(695,2312.5,'1.25m',color='#923b1d',va='center',fontsize=9)
        ax.annotate('',xy=(490,2070),xytext=(260,2070),arrowprops={'arrowstyle':'<->','color':'#923b1d'})
        ax.text(375,2040,'중앙 2.30m',ha='center',color='#923b1d',fontsize=9)
        ax.text(90,2312,'좌우 분절벽',ha='right',va='center',color='#923b1d',fontsize=9)
        ax.text(375,2573,'장치 위로 0.50m / 갑옷 경로 조정',ha='center',fontsize=10,color='#71491d')

fig.suptitle('Stage3 제단실 벽 · 통행 검토안',fontsize=18,fontweight='bold',y=.97)
fig.text(.5,.06,'갈색 = 새 벽 6구간  |  파랑 점선 = 갑옷 순찰  |  아래 ㄴ/ㄱ벽 각각 외곽 1.5×1.5m로 해석',ha='center',fontsize=11)
fig.text(.5,.025,'승인 전 제안입니다. 본맵·에셋에는 적용하지 않았습니다. 소품의 최종 몰딩 돌출은 적용 후 재검사합니다.',ha='center',fontsize=10,color='#954323')
fig.subplots_adjust(left=.05,right=.98,bottom=.17,top=.88,wspace=.13)
fig.savefig(OUT/'altar_proposal.png',dpi=160,facecolor=fig.get_facecolor())
fig.savefig(OUT/'altar_proposal.svg',facecolor=fig.get_facecolor())
print(OUT/'altar_proposal.png')
