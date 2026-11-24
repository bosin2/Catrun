import unreal as u, json
from pathlib import Path
r=Path(u.Paths.project_dir())/'Saved/Stage3Integration20261125';r.mkdir(parents=True,exist_ok=True)
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage2')
w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
out={'game_mode':str(w.get_world_settings().get_editor_property('default_game_mode')),'actors':[]}
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a,(u.CatrunArmor,u.CatrunCandle,u.SoundGridManager,u.PlayerStart,u.DirectionalLight,u.SkyLight,u.PostProcessVolume)) or any(s in a.get_class().get_name() for s in ('QuarterView','BP_Cat_C','SoundController','Minimap')):
        row={'label':a.get_actor_label(),'class':a.get_class().get_path_name(),'location':str(a.get_actor_location()),'components':[]}
        for c in a.get_components_by_class(u.SceneComponent):
            x={'name':c.get_name(),'class':c.get_class().get_name(),'relative_location':str(c.relative_location),'relative_rotation':str(c.relative_rotation),'relative_scale':str(c.relative_scale3d)}
            if isinstance(c,u.SkeletalMeshComponent):x['mesh']=str(c.skeletal_mesh_asset);x['materials']=[str(m) for m in c.get_materials()]
            row['components'].append(x)
        out['actors'].append(row)
(r/'source_probe.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print('STAGE3_PROBE_COMPLETE')
