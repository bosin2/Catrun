"""Read-only: dump portal-related track keys of LS_Stage2_PortalArrival (no save)."""
import json
from pathlib import Path
import unreal as u

seq = u.load_asset('/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival')
out = {}
for b in seq.get_bindings():
    n = b.get_name()
    if not any(k in n for k in ('Portal', 'Surface', 'Halo', 'Stone', 'Sparks', 'BlueLight', 'Arrival')):
        continue
    for t in b.get_tracks():
        for s in t.get_sections():
            row = {'track': t.get_class().get_name(), 'range': [s.get_start_frame(), s.get_end_frame()], 'channels': []}
            try:
                row['prop'] = str(t.get_property_name())
            except Exception:
                pass
            for ch in s.get_all_channels():
                keys = [(k.get_time(u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value, str(k.get_value())) for k in ch.get_keys()]
                d = ch.get_default() if hasattr(ch, 'has_default') and ch.has_default() else None
                row['channels'].append({'name': str(ch.get_name()), 'default': str(d), 'keys': keys[:40]})
            out.setdefault(n, []).append(row)
Path(u.Paths.project_dir(), 'Saved/PortalCinematic/probe_portal_keys.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print('PORTALCINE_PROBE_DONE', len(out))
