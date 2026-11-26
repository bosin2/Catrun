"""Find enclosed no-floor regions (dead space) inside the Stage3 outer walls."""
import json, sys, collections
rows = json.load(open('C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/geometry_cpd.json', encoding='utf8'))
G = 10
floors = [(mn, mx) for l, r, mn, mx, c, h, v in rows if l.startswith(('S3_Floor', 'S3_GothicRecess', 'S3_ExitLanding')) and not h and mx[2] < 20]
walls = [(mn, mx) for l, r, mn, mx, c, h, v in rows if (l.startswith(('S3_Wall_', 'S3_H')) or 'Frame' in l and l.startswith(('S3_D', 'S3_FinalGate'))) and not h and mx[2] >= 200]
xs = [p for mn, mx in floors + walls for p in (mn[0], mx[0])]; ys = [p for mn, mx in floors + walls for p in (mn[1], mx[1])]
X0, X1, Y0, Y1 = int(min(xs)) - 40, int(max(xs)) + 40, int(min(ys)) - 40, int(max(ys)) + 40
W, H = (X1 - X0) // G, (Y1 - Y0) // G
grid = [[0] * W for _ in range(H)]  # 0 empty, 1 floor, 2 wall
def mark(mn, mx, val):
    for j in range(max(0, int((mn[1] - Y0) // G)), min(H, int((mx[1] - Y0) // G) + 1)):
        for i in range(max(0, int((mn[0] - X0) // G)), min(W, int((mx[0] - X0) // G) + 1)):
            cx, cy = X0 + i * G + G / 2, Y0 + j * G + G / 2
            if mn[0] <= cx <= mx[0] and mn[1] <= cy <= mx[1] and grid[j][i] < val: grid[j][i] = val
for mn, mx in floors: mark(mn, mx, 1)
for mn, mx in walls: mark(mn, mx, 2)
ext = [[False] * W for _ in range(H)]
q = collections.deque([(0, 0)]); ext[0][0] = True
while q:
    j, i = q.popleft()
    for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a, b = j + dj, i + di
        if 0 <= a < H and 0 <= b < W and not ext[a][b] and grid[a][b] == 0:
            ext[a][b] = True; q.append((a, b))
dead = [[grid[j][i] == 0 and not ext[j][i] for i in range(W)] for j in range(H)]
# greedy rectangle decomposition
used = [[False] * W for _ in range(H)]; rects = []
for j in range(H):
    for i in range(W):
        if dead[j][i] and not used[j][i]:
            w = 1
            while i + w < W and dead[j][i + w] and not used[j][i + w]: w += 1
            h = 1
            while j + h < H and all(dead[j + h][i + k] and not used[j + h][i + k] for k in range(w)): h += 1
            for a in range(j, j + h):
                for b in range(i, i + w): used[a][b] = True
            rects.append([X0 + i * G, Y0 + j * G, X0 + (i + w) * G, Y0 + (j + h) * G])
rects = [r for r in rects if (r[2] - r[0]) * (r[3] - r[1]) >= 40 * 40]
print('bbox', X0, X1, Y0, Y1, 'dead rects', len(rects))
for r in sorted(rects, key=lambda r: -(r[2] - r[0]) * (r[3] - r[1])): print(r, (r[2] - r[0]), 'x', (r[3] - r[1]))
json.dump({'bbox': [X0, X1, Y0, Y1], 'dead': rects}, open('C:/Users/whghk/Catrun/Saved/Stage3Polish20261126/Audit/deadspace.json', 'w'))
# ascii map
for j in range(0, H, 10):
    print(''.join('#' if grid[j][i] == 2 else '.' if grid[j][i] == 1 else ('X' if dead[j][i] else ' ') for i in range(0, W, 5)))
