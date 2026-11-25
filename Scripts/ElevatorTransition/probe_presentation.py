import unreal as u,json
from pathlib import Path
ac=u.get_editor_subsystem(u.EditorActorSubsystem)
data={'actors':[],'effects':[]}
for a in ac.get_all_level_actors():
    if any(t in a.get_class().get_name() for t in ['Light','Fog','PostProcess','Camera','Player']):
        row={'label':a.get_actor_label(),'class':a.get_class().get_name(),'loc':a.get_actor_location().to_tuple()}
        if isinstance(a,u.Character):
            row['mesh_pose']=str(a.mesh.get_relative_transform()); row['mesh']=a.mesh.skeletal_mesh.get_path_name()
        if isinstance(a,u.Light):
            row['intensity']=a.light_component.intensity
        data['actors'].append(row)
for asset in u.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game',True):
    if any(s in str(asset.asset_name).lower() for s in ['dust','fog','clank','metal','elevator','chain','woodcreak']):
        data['effects'].append(str(asset.package_name))
(Path(u.Paths.project_dir()).resolve()/'Saved/ElevatorTransition/presentation_probe.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print(data)
