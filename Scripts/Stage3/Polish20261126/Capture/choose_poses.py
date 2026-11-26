"""Offline: choose cat poses (walkable, target occluder cut by the cutaway shader replica)."""
import os, sys, json, math
os.environ.setdefault('S3P_GEO', 'C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/geometry_cpd_after_plan.json')
sys.path.insert(0, 'C:/Users/whghk/Catrun/Scripts/Stage3/Polish20261126')
from cutaway_sim import rows, groups, members, cut, on_floor
TARGETS = {
 'Corner09': 'S3_Gothic_WallCornerJoin_09_0', 'Corner02': 'S3_Wall_CornerJoin_02', 'Corner04': 'S3_Wall_CornerJoin_04',
 'Corner00': 'S3_Wall_CornerJoin_00', 'Corner08': 'S3_Wall_CornerJoin_08',
 'DecorTrophyLobby': 'S3_Art26_Trophy_Lobby', 'DecorStandoffCentral': 'S3_Art26_Standoff_Central',
 'CatHole1': 'S3_H1_Frame', 'CatHole2': 'S3_H2_Frame', 'CatHole3': 'S3_H3_Frame',
 'VoidEast1325': 'S3_Wall_0094', 'VoidGateEast': 'S3_Wall_0083', 'VoidWest1425': 'S3_Wall_0011', 'VoidLobbySouth': 'S3_Wall_0005',
}
solid = []
for l, ref, mn, mx, cpd, hid, vis in rows:
    if not hid and vis and (l.startswith('S3_Wall') or 'Corner' in l or 'Pillar' in l): solid.append((mn, mx))
def free(x, y):
    return not any(mn[0]-30 <= x <= mx[0]+30 and mn[1]-30 <= y <= mx[1]+30 and mn[2] < 60 for mn, mx in solid)
key_of = {}
for k, ms in members.items():
    for m in ms: key_of[m] = k
out = {}
for name, label in TARGETS.items():
    k = key_of.get(label)
    if not k: out[name] = None; print(name, 'missing group'); continue
    c, e = groups[k]
    best = None
    for dx in range(-400, 401, 20):
        for dy in range(-400, 401, 20):
            x, y = c[0]+dx, c[1]+dy
            if not on_floor(x, y) or not free(x, y): continue
            if not cut((x, y, 26.0), c, e): continue
            # prefer cat 60..140cm from the occluder centre on the far (-X/-Y) side
            d = math.hypot(dx, dy)
            score = abs(d-110)
            if best is None or score < best[0]: best = (score, x, y)
    cutset = [members[g][0] for g in groups if best and cut((best[1], best[2], 26.0), *groups[g])]
    out[name] = {'label': label, 'group_center': c, 'cat': best and [best[1], best[2], 26.2], 'cut_groups_at_pose': cutset[:12]}
    print(name, label, out[name]['cat'], cutset[:6])
json.dump(out, open('C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Captures/poses_cutaway.json', 'w'), indent=1)
