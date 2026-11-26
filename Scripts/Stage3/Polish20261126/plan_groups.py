"""Plan CPD group fixes: corner joins -> union with touching wall segments;
decor straddling segments -> union of overlapped segments; cathole frames own box."""
import json, collections
rows = json.load(open('C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/geometry_cpd.json', encoding='utf8'))
def gbox(cpd): return [cpd[i]-cpd[4+i] for i in range(3)], [cpd[i]+cpd[4+i] for i in range(3)]
walls = {r[0]: (r[2], r[3]) for r in rows if r[0].startswith('S3_Wall_') and 'Corner' not in r[0] and not r[5] and r[6]}
groups = collections.defaultdict(list)
for r in rows:
    if r[4] and not r[5] and r[6]: groups[tuple(r[4])].append(r)
def touch(a, b, tol=2.0):
    return all(a[0][i] <= b[1][i] + tol and b[0][i] <= a[1][i] + tol for i in range(2))
def union(boxes):
    return [min(b[0][i] for b in boxes) for i in range(3)], [max(b[1][i] for b in boxes) for i in range(3)]
def cpd_of(box):
    lo, hi = box
    return [(lo[i]+hi[i])/2 for i in range(3)] + [1] + [(hi[i]-lo[i])/2 for i in range(3)] + [1]
plan = {}
for key, mem in groups.items():
    if not any('CornerJoin' in m[0] for m in mem): continue
    gb = gbox(list(key))
    adj = [w for w in walls.values() if touch(gb, w)]
    nb = union([gb] + adj)
    for m in [x for x in mem if 'CornerJoin' in x[0]]: plan[m[1]] = {'label': m[0], 'reason': 'corner-union', 'cpd': cpd_of(nb), 'adjacent': len(adj)}
def ov(a0, a1, b0, b1): return max(0, min(a1, b1) - max(a0, b0))
for l, ref, mn, mx, cpd, hid, vis in rows:
    if not l.startswith(('S3_Art26_Trophy', 'S3_Art26_Lantern_D2', 'S3_Art26_Lantern_LobbyEast', 'S3_Art26_TagBoard', 'S3_Art26_KeyRack', 'S3_Art26_Standoff')) or not cpd or hid: continue
    hits = [w for w in walls.values() if ov(mn[0], mx[0], w[0][0]-25, w[1][0]+25) > 0 and ov(mn[1], mx[1], w[0][1]-25, w[1][1]+25) > 0]
    if not hits: continue
    nb = union([gbox(cpd)] + hits)
    plan[ref] = {'label': l, 'reason': 'decor-union', 'cpd': cpd_of(nb), 'walls': len(hits)}
for l, ref, mn, mx, cpd, hid, vis in rows:
    if l.startswith('S3_H') and ('_Frame' in l or '_Trim' in l):
        frame = next(r for r in rows if r[0] == l.split('_')[0] + '_' + l.split('_')[1] + '_Frame')
        plan[ref] = {'label': l, 'reason': 'cathole-cutaway', 'cpd': cpd_of((frame[2], frame[3]))}
json.dump(plan, open('C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/group_plan.json', 'w'), indent=1)
c = collections.Counter(v['reason'] for v in plan.values()); print(c)
for k, v in list(plan.items())[:5]: print(k, v)
