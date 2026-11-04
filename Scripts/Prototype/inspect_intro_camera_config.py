"""Read-only sequencer diagnostics; never saves a package."""
import unreal, json
seq = unreal.load_asset('/Game/Cinematics/LS_Tutorial')
rows = []
for binding in seq.get_bindings():
    row = {'name': binding.get_name(), 'tracks': []}
    for track in binding.get_tracks():
        item = {'class': track.get_class().get_name(), 'sections': []}
        for key in ['bIsEvalDisabled', 'bIsLocalEvalDisabled', 'is_eval_disabled']:
            try: item[key] = track.get_editor_property(key)
            except Exception: pass
        if isinstance(track, unreal.MovieSceneSpawnTrack):
            for section in track.get_sections():
                detail = {'active': section.is_active(), 'channels': []}
                for channel in section.get_all_channels():
                    channel_detail = {'class': channel.get_class().get_name()}
                    try: channel_detail['default'] = channel.get_default()
                    except Exception as exc: channel_detail['error'] = str(exc)
                    try: channel_detail['keys'] = [str(k.get_value()) for k in channel.get_keys()]
                    except Exception: pass
                    detail['channels'].append(channel_detail)
                item['sections'].append(detail)
        row['tracks'].append(item)
    rows.append(row)
print(json.dumps(rows))
