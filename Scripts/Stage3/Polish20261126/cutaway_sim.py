"""Offline replica of the Stage3 cutaway shader (occlusion.py CODE) for the
saved Stage3 geometry dump. Used to find corner posts / decor left standing,
holes and void exposure without running the editor. Input: geometry_cpd.json
(label, ref, min, max, cpd16..23, hiddenInGame, visible)."""
import json, math, sys, collections
P = __import__('os').environ.get('S3P_GEO') or 'C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/geometry_cpd.json'
rows = json.load(open(P, encoding='utf8'))
p, y = math.radians(-55), math.radians(-135)
F = (math.cos(p)*math.cos(y), math.cos(p)*math.sin(y), math.sin(p))
R = (-math.sin(y), math.cos(y), 0.0)
U = (F[1]*R[2]-F[2]*R[1], F[2]*R[0]-F[0]*R[2], F[0]*R[1]-F[1]*R[0])
if U[2] < 0: U = tuple(-c for c in U)
D = tuple(-c for c in F)
S = [(0,0),(1,0),(-1,0),(0,1),(0,-1)] + [(a*.70710678,b*.70710678) for a in (1,-1) for b in (1,-1)]
def cut(cat, center, ext, radius=24.0):
    for sx, sy in S:
        o = [cat[i] + radius*(R[i]*sx + U[i]*sy) for i in range(3)]
        enter, exit_, hit = 2.0, 1e20, True
        for a in range(3):
            lo, hi = center[a]-ext[a], center[a]+ext[a]
            if abs(D[a]) < 1e-6:
                if o[a] < lo or o[a] > hi: hit = False
            else:
                A, B = (lo-o[a])/D[a], (hi-o[a])/D[a]
                enter = max(enter, min(A, B)); exit_ = min(exit_, max(A, B))
        if hit and exit_ > 2.0 and enter <= exit_: return True
    return False
groups = {}
members = collections.defaultdict(list)
for l, ref, mn, mx, cpd, hid, vis in rows:
    if not cpd or hid or not vis: continue
    key = tuple(round(v, 1) for v in cpd[:3] + cpd[4:7])
    groups[key] = (cpd[:3], [max(v, .1) for v in cpd[4:7]])
    members[key].append(l)
floors = [(mn, mx) for l, ref, mn, mx, cpd, hid, vis in rows if l.startswith(('S3_Floor', 'S3_GothicRecess', 'S3_ExitLanding')) and not hid]
def on_floor(x, yy):
    return any(mn[0] <= x <= mx[0] and mn[1] <= yy <= mx[1] for mn, mx in floors)
if __name__ == '__main__':
    print('groups', len(groups), 'floors', len(floors), 'F', [round(c,3) for c in F], 'U', [round(c,3) for c in U])
