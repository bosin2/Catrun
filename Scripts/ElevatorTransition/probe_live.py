import unreal as u
import json
from pathlib import Path
out=Path(u.Paths.project_dir()).resolve()/'Saved/ElevatorTransition'
out.mkdir(parents=True,exist_ok=True)
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
data={'project':u.Paths.get_project_file_path(),'world':ed.get_editor_world().get_path_name(),
      'dirty_maps':[x.get_path_name() for x in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
      'dirty_content':[x.get_path_name() for x in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
      'actors':[]}
for a in actors.get_all_level_actors():
    l=a.get_actor_label()
    if any(s in l.lower() for s in ['start','entry','entrance','exit','flow','camera','arrival','gate']):
        data['actors'].append({'label':l,'class':a.get_class().get_path_name(),'path':a.get_path_name(),
        'location':list(a.get_actor_location().to_tuple()),'rotation':list(a.get_actor_rotation().to_tuple()),'tags':[str(t) for t in a.tags]})
(out/'probe_live.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(data,ensure_ascii=False))
