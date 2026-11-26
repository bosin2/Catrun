import sys, json, collections
sys.path.insert(0, 'C:/Users/whghk/Catrun/Scripts/Stage3/Polish20261126')
from cutaway_sim import *
walls = {k: v for k, v in groups.items()}
def box(k):
    c, e = groups[k]; return [c[i]-e[i] for i in range(3)], [c[i]+e[i] for i in range(3)]
def touch(a, b, tol=2.0):
    (al, ah), (bl, bh) = box(a), box(b)
    return all(al[i] <= bh[i]+tol and bl[i] <= ah[i]+tol for i in range(2))
corner = [k for k in groups if any('CornerJoin' in m for m in members[k])]
wallg = [k for k in groups if any(m.startswith('S3_Wall_') and 'Corner' not in m for m in members[k])]
mb = {}
for l, ref, mn, mx, cpd, hid, vis in rows:
    if cpd and not hid and vis and 'CornerJoin' in l:
        k = tuple(round(v, 1) for v in cpd[:3] + cpd[4:7]); mb.setdefault(k, []).append((mn, mx))
def touchm(c, w, tol=2.0):
    (bl, bh) = box(w)
    return any(all(mn[i] <= bh[i]+tol and bl[i] <= mx[i]+tol for i in range(2)) for mn, mx in mb.get(c, []))
corner = [c for c in corner if c in mb]
adj = {c: [w for w in wallg if touchm(c, w) and w != c] for c in corner}
solid = [box(k) for k in wallg + corner]
def inside_wall(x, y):
    return any(lo[0]-15 <= x <= hi[0]+15 and lo[1]-15 <= y <= hi[1]+15 for lo, hi in solid)
pts = []
for xi in range(-1150, 1200, 25):
    for yi in range(0, -4700, -25):
        if on_floor(xi, yi) and not inside_wall(xi, yi): pts.append((xi, yi))
stand = collections.Counter(); ex = {}
void = collections.Counter(); vex = {}
cutcount = collections.Counter()
for (x, y) in pts:
    cat = (x, y, 26.0)
    cs = {k for k in groups if cut(cat, *groups[k])}
    for k in cs: cutcount[k] += 1
    for c in corner:
        if c not in cs and any(w in cs for w in adj[c]):
            stand[c] += 1; ex.setdefault(c, (x, y))
    for k in cs & set(wallg):
        lo, hi = box(k)
        cx, cy = (lo[0]+hi[0])/2, (lo[1]+hi[1])/2
        thin = 0 if hi[0]-lo[0] < hi[1]-lo[1] else 1
        probe = (hi[0]+60, cy) if thin == 0 else (cx, hi[1]+60)
        if not on_floor(*probe):
            void[k] += 1; vex.setdefault(k, (x, y))
print('walkable samples', len(pts))
print('corner posts left standing while adjacent wall cut: %d corners, %d sample-hits' % (len(stand), sum(stand.values())))
for c, n in stand.most_common(12): print('  ', members[c][0], n, 'e.g. cat', ex[c])
print('cut walls exposing no-floor (void) on camera side: %d walls, %d hits' % (len(void), sum(void.values())))
for k, n in void.most_common(15): print('  ', members[k][0], n, 'e.g. cat', vex[k], box(k)[0][:2], box(k)[1][:2])
out = {'samples': len(pts), 'standing_corners': {members[c][0]: [n, ex[c]] for c, n in stand.items()},
       'void_walls': {members[k][0]: [n, vex[k]] for k, n in void.items()}}
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/cutaway_sim_before.json', 'w'), indent=1)
