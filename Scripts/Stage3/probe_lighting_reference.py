"""Read saved lighting/camera settings without saving any package."""
import unreal as u,json
from pathlib import Path
out=Path(u.Paths.project_dir())/'Saved/Stage3Correction20261125'
out.mkdir(parents=True,exist_ok=True)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
report={}
for name in ['Stage1','Stage2','Stage3']:
    assert levels.load_level('/Game/Maps/'+name)
    rows=[]
    for actor in actors.get_all_level_actors():
        if isinstance(actor,u.Light):
            component=actor.get_component_by_class(u.LightComponent)
            row={'label':actor.get_actor_label(),'class':actor.get_class().get_name(),'position':str(actor.get_actor_location())}
            for prop in ['intensity','light_color','cast_shadows','attenuation_radius','source_radius','intensity_units']:
                try:row[prop]=str(component.get_editor_property(prop))
                except Exception:pass
            rows.append(row)
        elif isinstance(actor,u.SkyLight):
            component=actor.get_component_by_class(u.SkyLightComponent)
            rows.append({'label':actor.get_actor_label(),'class':'SkyLight','intensity':component.get_editor_property('intensity'),'cubemap':str(component.get_editor_property('cubemap'))})
        elif isinstance(actor,u.PostProcessVolume):
            settings=actor.get_editor_property('settings')
            rows.append({'label':actor.get_actor_label(),'class':'PostProcessVolume','exposure':{p:str(settings.get_editor_property(p)) for p in ['auto_exposure_min_brightness','auto_exposure_max_brightness','auto_exposure_bias','auto_exposure_method','override_auto_exposure_bias']}})
        elif 'QuarterViewCamera' in actor.get_class().get_name():
            rows.append({'label':actor.get_actor_label(),'class':'Camera','transform':actor.get_actor_transform().export_text(),'components':[{'name':c.get_name(),'transform':c.get_relative_transform().export_text()} for c in actor.get_components_by_class(u.SceneComponent)]})
    report[name]=rows
(out/'lighting_reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('STAGE3_LIGHTING_REFERENCE_OK')
