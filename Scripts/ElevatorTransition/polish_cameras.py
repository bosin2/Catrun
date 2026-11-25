import unreal as u
LE=u.get_editor_subsystem(u.LevelEditorSubsystem);AC=u.get_editor_subsystem(u.EditorActorSubsystem)
for mapname in ['Stage2','Stage3']:
    assert LE.load_level('/Game/Maps/'+mapname)
    lookup={a.get_actor_label():a for a in AC.get_all_level_actors()}
    for name,a in lookup.items():
        if name.startswith('E23_') and isinstance(a,u.CameraActor):a.camera_component.set_editor_property('constrain_aspect_ratio',False)
    lamp=lookup['E23_Lift_LanternLight'];lc=lamp.light_component
    lc.set_intensity(35);lc.set_light_color(u.LinearColor(1,.90,.77,1));lc.set_editor_property('attenuation_radius',470);lc.set_editor_property('cast_shadows',False)
    lamp.set_actor_location(u.Vector(780,-1545,250) if mapname=='Stage2' else u.Vector(85,125,250),False,True)
    if mapname=='Stage2':
        warehouse=lookup['E23_View_Warehouse'];warehouse.set_actor_location(u.Vector(715,-680,1100),False,True)
        warehouse.set_actor_rotation(u.MathLibrary.find_look_at_rotation(warehouse.get_actor_location(),u.Vector(715,-1090,60)),True);warehouse.camera_component.set_field_of_view(86)
        for name,position,target,fov in [('E23_Shot_Ring',(875,-1300,120),(715,-1560,65),58),
            ('E23_Shot_Below',(735,-1350,-32),(715,-1525,260),66),
            ('E23_Shot_Ascent',(1115,-970,300),(715,-1585,168),70)]:
            a=lookup[name];a.set_actor_location(u.Vector(*position),False,True)
            a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(a.get_actor_location(),u.Vector(*target)),True);a.camera_component.set_field_of_view(fov)
        lookup['E23_Warehouse_OverheadBeam'].light_component.set_intensity(400)
        lookup['E23_Warehouse_OverheadBeam'].light_component.set_editor_property('attenuation_radius',1100)
        lookup['E23_Warehouse_BeamBounce'].light_component.set_intensity(8)
        lookup['E23_Warehouse_BeamBounce'].light_component.set_editor_property('attenuation_radius',850)
        bounce=lookup.get('E23_Warehouse_PathBounce')
        if not bounce:
            bounce=AC.spawn_actor_from_class(u.PointLight,u.Vector(715,-920,190));bounce.set_actor_label('E23_Warehouse_PathBounce');bounce.tags=['CatrunElevatorTransition20261125']
            d=lookup['E23_Director'];d.hide_during_ascent=list(d.hide_during_ascent)+[bounce]
        c=bounce.light_component;c.set_mobility(u.ComponentMobility.MOVABLE);c.set_intensity(12);c.set_editor_property('attenuation_radius',650)
        c.set_editor_property('lighting_channels',u.LightingChannels(channel0=False,channel1=True,channel2=False))
        c.set_light_color(u.LinearColor(.78,.82,.88,1))
    assert LE.save_current_level()
    del lookup
