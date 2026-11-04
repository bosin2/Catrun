import unreal,json
from pathlib import Path
seq=unreal.load_asset('/Game/Cinematics/LS_Tutorial')
print('SPAWNABLES',[b.get_name() for b in seq.get_spawnables()])
print('POSSESSABLES',[b.get_name() for b in seq.get_possessables()])
rows=[]
for t in seq.get_tracks():
    row={'class':t.get_class().get_name(),'sections':[]}
    for key in ['is_eval_disabled','is_local_eval_disabled']:
        try:row[key]=t.get_editor_property(key)
        except Exception:pass
    for s in t.get_sections():
        a={'class':s.get_class().get_name()}
        if s.has_start_frame() and s.has_end_frame():a['range']=[s.get_start_frame(),s.get_end_frame()]
        if isinstance(s,unreal.MovieSceneCameraCutSection):
            bid=s.get_camera_binding_id()
            a['binding_name']=seq.find_binding_by_id(bid.get_editor_property('guid')).get_name()
            a['active']=s.is_active()
        row['sections'].append(a)
    rows.append(row)
print(json.dumps(rows))
