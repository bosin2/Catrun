"""DLL 링크에 쓰인 obj 가 현재 헤더보다 오래됐는지 확인한다(읽기 전용).

  python -B Scripts/Regression20261126/stale_objects.py [OBJ_DIR]

헤더 멤버 배치가 바뀐 뒤 다시 컴파일되지 않은 obj 가 섞이면 링크는 성공하지만 멤버 오프셋이 어긋난다.
"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBJ = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'Intermediate/Build/Win64/x64/UnrealEditor/Development/Catrun'


def stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime('%m-%d %H:%M:%S')


def main():
    rows, nodep = [], []
    for obj in sorted(OBJ.glob('*.obj')):
        if '.lc.' in obj.name:
            continue
        dep = OBJ / (obj.name[:-4] + '.dep.json')
        if not dep.exists():
            nodep.append(obj.name)
            continue
        data = json.loads(dep.read_text(encoding='utf-8', errors='replace'))['Data']
        t = obj.stat().st_mtime
        for name in [data.get('Source')] + list(data.get('Includes', [])):
            if not name or not name.lower().startswith(str(ROOT).lower()):
                continue
            p = Path(name)
            if p.exists() and p.stat().st_mtime > t + 1:
                rows.append((obj.name, p.relative_to(ROOT).as_posix(), stamp(t), stamp(p.stat().st_mtime)))
    for r in rows:
        print('%-46s <- %-64s obj %s  header %s' % r)
    print('obj 검사 완료: 오래된 쌍 %d, 오래된 obj %d, dep 없음 %d %s' % (len(rows), len({r[0] for r in rows}), len(nodep), nodep[:8]))


if __name__ == '__main__':
    main()
