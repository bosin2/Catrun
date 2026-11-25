"""Exercise the new effect's Sequencer APIs in unsaved temporary packages."""
from pathlib import Path
import json
import sys
import unreal as u

sys.path.insert(0, str(Path(__file__).resolve().parent))
import integrate as entry

assert not entry.h.dirty()
seq = u.AssetToolsHelpers.get_asset_tools().create_asset('LS_UnsavedRippleAPITest', entry.FOLDER,
        u.LevelSequence, u.LevelSequenceFactoryNew())
seq.set_display_rate(u.FrameRate(30, 1))
seq.set_tick_resolution_directly(u.FrameRate(24000, 1))
seq.set_playback_start(0)
seq.set_playback_end(340)
material = entry.ripple_material()
binding = entry.add_ripple(seq, material, 200, (101., -315., .28), 340)
report = {'binding': binding.get_id().export_text(), 'bindings': []}
for item in seq.get_bindings():
    report['bindings'].append({'name': item.get_name(), 'tracks': [t.get_class().get_name() for t in item.get_tracks()]})
report['dirty'] = entry.h.dirty()
(entry.OUT/'ripple_api.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('RIPPLE_API_VALIDATED', report)
