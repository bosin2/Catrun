"""Stage3 interactive objects stay opaque before, during and after interaction.

Only material overrides on existing Stage3 instances are changed. Native
references, transforms, meshes, collision and animation are preserved.
"""
import hashlib,json
from pathlib import Path
import unreal as u
DEST='/Game/Environment/Stage3/GothicRevision_20261125/InteractiveReadability'
OWNER='Stage3AlwaysVisibleInteractions20261125'
EA=u.EditorAssetLibrary;ML=u.MaterialEditingLibrary

def apply():
    actors=u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    report={'success':False,'policy':'Always opaque, including before interaction','assignments':[],'parents':{}}
    cached={}
    def opaque(source):
        if source.get_path_name().startswith(DEST):
            assert EA.get_metadata_tag(source,'Stage3InteractiveOwner')==OWNER
            source=EA.load_asset(EA.get_metadata_tag(source,'Stage3InteractiveSource'))
        key=source.get_path_name()
        if key in cached:return cached[key]
        base=source.get_base_material() if isinstance(source,u.MaterialInstanceConstant) else source
        digest=hashlib.sha256(key.encode()).hexdigest()[:12]
        pp=DEST+'/M_Interactive_'+digest;ip=DEST+'/MI_Interactive_'+digest
        def owned(path):
            if not EA.does_asset_exist(path):return None
            obj=EA.load_asset(path)
            assert EA.get_metadata_tag(obj,'Stage3InteractiveOwner')==OWNER,path
            return obj
        parent=owned(pp)
        if not parent:
            parent=EA.duplicate_asset(base.get_path_name(),pp);assert parent
            EA.set_metadata_tag(parent,'Stage3InteractiveOwner',OWNER)
        parent.set_editor_property('blend_mode',u.BlendMode.BLEND_OPAQUE)
        # Both roots are explicitly constant so neither camera MPC nor old
        # actor-specific dither can become active through a future override.
        one=ML.create_material_expression(parent,u.MaterialExpressionConstant,-150,1500)
        one.set_editor_property('r',1.)
        for prop in (u.MaterialProperty.MP_OPACITY,u.MaterialProperty.MP_OPACITY_MASK):
            assert ML.connect_material_property(one,'',prop)
        for name in ('BASE_COLOR','NORMAL','AMBIENT_OCCLUSION','ROUGHNESS','METALLIC','EMISSIVE_COLOR','WORLD_POSITION_OFFSET'):
            prop=getattr(u.MaterialProperty,'MP_'+name)
            a=ML.get_material_property_input_node(base,prop);b=ML.get_material_property_input_node(parent,prop)
            assert (a.get_name() if a else None)==(b.get_name() if b else None),(key,name)
            assert ML.get_material_property_input_node_output_name(base,prop)==ML.get_material_property_input_node_output_name(parent,prop)
        ML.recompile_material(parent);assert EA.save_loaded_asset(parent)
        mi=owned(ip)
        if not mi:
            if isinstance(source,u.MaterialInstanceConstant):mi=EA.duplicate_asset(key,ip)
            else:mi=u.AssetToolsHelpers.get_asset_tools().create_asset(ip.rsplit('/',1)[-1],DEST,u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
            EA.set_metadata_tag(mi,'Stage3InteractiveOwner',OWNER)
            EA.set_metadata_tag(mi,'Stage3InteractiveSource',key)
        ML.set_material_instance_parent(mi,parent)
        overrides=mi.get_editor_property('base_property_overrides')
        overrides.set_editor_property('override_blend_mode',False)
        mi.set_editor_property('base_property_overrides',overrides)
        ML.update_material_instance(mi);assert EA.save_loaded_asset(mi)
        assert parent.get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE
        if isinstance(source,u.MaterialInstanceConstant):
            assert ML.get_material_instance_vector_parameter_value(source,'ColorTint')==ML.get_material_instance_vector_parameter_value(mi,'ColorTint')
            assert ML.get_material_instance_scalar_parameter_value(source,'Brightness')==ML.get_material_instance_scalar_parameter_value(mi,'Brightness')
        report['parents'][pp]={'source':key,'instance':ip,'blend_mode':'OPAQUE','opacity':1,'opacity_mask':1}
        cached[key]=mi
        return mi
    for actor in actors:
        label=actor.get_actor_label()
        relevant=label.startswith(('S3_Release','S3_GothicConnections_','S3_GothicVisual_Dock','S3_GothicVisual_Weight','S3_GothicVisual_FloorFrame','S3_GothicVisual_PressureDeck','S3_GothicVisual_Lock','S3_D0','S3_D1_','S3_D2_','S3_FinalGate_Leaf'))
        if not relevant:continue
        comp=actor.get_component_by_class(u.StaticMeshComponent)
        if not comp or not comp.get_editor_property('visible') or comp.get_editor_property('hidden_in_game'):continue
        before=(actor.get_actor_transform().export_text(),str(comp.get_collision_enabled()),comp.static_mesh.get_path_name())
        for slot in range(comp.get_num_materials()):
            source=comp.get_material(slot)
            if not source:continue
            material=opaque(source);comp.set_material(slot,material)
            report['assignments'].append({'actor':label,'slot':slot,'source':source.get_path_name(),'assigned':material.get_path_name()})
        assert before==(actor.get_actor_transform().export_text(),str(comp.get_collision_enabled()),comp.static_mesh.get_path_name())
    labels={r['actor'] for r in report['assignments']}
    assert all('S3_Release%d_%s'%(n,part) in labels for n in (1,2,3) for part in ('Housing','Ring','Pin'))
    report['success']=True
    (Path(u.Paths.project_dir())/'Saved/Stage3GothicRevision20261125/interactive_visibility.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report

if __name__=='__main__':
    le=u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert le.load_level('/Game/Maps/Stage3')
    apply()
    u.CatrunAuthoringLibrary.finish_asset_compilation()
    assert le.save_current_level()
    print('GOTHIC_INTERACTIVE_OPAQUE_SAVED')
