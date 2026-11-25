"""Offline delivery change sampler. poll_due() checks at most once per 5 min.

No Unreal calls/imports. Root or the active worker calls it during this task;
this is not a background service or permission to import changed packages.
"""
import datetime
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3PlacementRevision20261125'
SOURCE = Path('C:/Users/whghk/Desktop/CastleKit/Stage3')


def poll_due():
    OUT.mkdir(parents=True, exist_ok=True)
    state_path = OUT / 'delivery_watch.json'
    previous = json.loads(state_path.read_text(encoding='utf8')) if state_path.exists() else None
    now = time.time()
    if previous and now - previous['checked_at_epoch'] < 300:
        return {'checked': False, 'seconds_until_next': round(300 - (now-previous['checked_at_epoch']))}
    current = {}
    for p in SOURCE.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('QA', 'Screenshots', 'import_cache', '.git')) or '.fbm' in str(p):
            continue
        if p.suffix.lower() not in ('.fbx', '.blend', '.json', '.png'):
            continue
        stat = p.stat()
        current[str(p)] = [stat.st_size, stat.st_mtime_ns]
    old = previous['files'] if previous else current
    event = {'checked': True, 'checked_at_epoch': now,
             'checked_at': datetime.datetime.now().astimezone().isoformat(),
             'baseline': previous is None,
             'added': sorted(set(current)-set(old)),
             'changed': sorted(p for p in current.keys() & old.keys() if current[p] != old[p]),
             'removed': sorted(set(old)-set(current)), 'file_count': len(current)}
    history = previous.get('history', []) if previous else []
    history.append(event)
    state_path.write_text(json.dumps(dict(event, files=current, history=history), ensure_ascii=False, indent=2), encoding='utf8')
    return event


if __name__ == '__main__':
    print(json.dumps(poll_due(), ensure_ascii=False, indent=2))
