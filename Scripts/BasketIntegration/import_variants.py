"""Import only the approved basket variants into a new isolated asset folder."""
import unreal as u,json,traceback
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/BasketIntegration20261125'
SRC=Path('C:/Users/whghk/Desktop/CastleKit/HideBasket/Variants20261125')
DEST='/Game/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125'
AT=u.AssetToolsHelpers.get_asset_tools();ML=u.MaterialEditingLibrary;EA=u.EditorAssetLibrary
REPORT={'root':DEST,'textures':{},'materials':{},'stages':{},'animations':{}}
def save_report(): (OUT/'import_report.json').write_text(json.dumps(REPORT,indent=2),encoding='utf8')
def task(file,folder,name,options=None):
    existing=EA.load_asset(folder+'/'+name) if EA.does_asset_exist(folder+'/'+name) else None
    if existing:return existing
    t=u.AssetImportTask();t.filename=str(file);t.destination_path=folder;t.destination_name=name;t.automated=True;t.save=True;t.replace_existing=False
    if options:t.options=options
    AT.import_asset_tasks([t]);assets=t.get_objects()
    obj=EA.load_asset(folder+'/'+name)
    assert obj,('Import failed',file,[x.get_path_name() for x in assets]);return obj
def material(name,prefix,cloth=False):
    path=DEST+'/Shared/Materials';m=EA.load_asset(path+'/'+name) if EA.does_asset_exist(path+'/'+name) else None
    if m:return m
    m=AT.create_asset(name,path,u.Material,u.MaterialFactoryNew());ML.delete_all_material_expressions(m)
    def node(cls,x,y):return ML.create_material_expression(m,cls,x,y)
    def connect(a,out,b,inp):assert ML.connect_material_expressions(a,out,b,inp)
    def prop(a,out,p):assert ML.connect_material_property(a,out,p)
    base=node(u.MaterialExpressionTextureSample,-650,0);base.texture=EA.load_asset(REPORT['textures'][prefix+'_BaseColor']);base.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_COLOR;prop(base,'RGB',u.MaterialProperty.MP_BASE_COLOR)
    orm=node(u.MaterialExpressionTextureSample,-650,300);orm.texture=EA.load_asset(REPORT['textures'][prefix+'_ORM']);orm.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
    for channel,output in [('R',u.MaterialProperty.MP_AMBIENT_OCCLUSION),('G',u.MaterialProperty.MP_ROUGHNESS),('B',u.MaterialProperty.MP_METALLIC)]:prop(orm,channel,output)
    normal=node(u.MaterialExpressionTextureSample,-650,-300);normal.texture=EA.load_asset(REPORT['textures'][prefix+'_Normal_DX']);normal.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
    mult=node(u.MaterialExpressionMultiply,-300,-300);strength=node(u.MaterialExpressionConstant3Vector,-500,-450);strength.constant=u.LinearColor(.10 if cloth else .38,.10 if cloth else .38,1.,1.)
    connect(normal,'RGB',mult,'A');connect(strength,'',mult,'B');normalize=node(u.MaterialExpressionNormalize,-100,-300);connect(mult,'',normalize,'VectorInput');prop(normalize,'',u.MaterialProperty.MP_NORMAL)
    if cloth:
        spec=node(u.MaterialExpressionConstant,-100,100);spec.r=.25;prop(spec,'',u.MaterialProperty.MP_SPECULAR)
    ML.recompile_material(m);EA.save_loaded_asset(m);return m
try:
    for file in sorted((SRC/'Shared/Textures').glob('*.png')):
        tex=task(file,DEST+'/Shared/Textures',file.stem)
        tex.set_editor_property('srgb',file.stem.endswith('_BaseColor'))
        if file.stem.endswith('_Normal_DX'):
            tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);tex.set_editor_property('flip_green_channel',False)
        elif file.stem.endswith('_ORM'):tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
        EA.save_loaded_asset(tex);REPORT['textures'][file.stem]=tex.get_path_name()
    for name,prefix in [('M_Walnut','T_Walnut'),('M_MilitaryWood','T_MilitaryWood'),('M_AgedBrass','T_AgedBrass'),('M_BlackIron','T_BlackIron'),('M_Rattan','T_HideBasket')]+[(f'M_Cloth_Stage{i}',f'T_Cloth_S{i}') for i in range(1,4)]:
        m=material(name,prefix,prefix.startswith('T_Cloth'));REPORT['materials'][name]=m.get_path_name()
    shared_skeleton=None
    for stage,label in [(1,'Linen'),(2,'Relic'),(3,'GuardSupply')]:
        folder=SRC/f'Stage{stage}_{label}';dest=DEST+f'/Stage{stage}/Meshes'
        def options(skeletal):
            o=u.FbxImportUI();o.set_editor_property('automated_import_should_detect_type',False);o.set_editor_property('import_mesh',True);o.set_editor_property('import_as_skeletal',skeletal);o.set_editor_property('import_materials',False);o.set_editor_property('import_textures',False);o.set_editor_property('import_animations',False);o.set_editor_property('create_physics_asset',False)
            o.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else u.FBXImportType.FBXIT_STATIC_MESH)
            data=o.skeletal_mesh_import_data if skeletal else o.static_mesh_import_data
            data.set_editor_property('import_uniform_scale',1.);data.set_editor_property('convert_scene',True);data.set_editor_property('convert_scene_unit',True);data.set_editor_property('force_front_x_axis',False)
            if not skeletal:data.set_editor_property('combine_meshes',True);data.set_editor_property('auto_generate_collision',False)
            if skeletal and shared_skeleton:o.set_editor_property('skeleton',shared_skeleton)
            return o
        bn=f'SM_HideBasket_Stage{stage}';cn=f'SK_HideBasket_Stage{stage}_Cloth'
        body=task(folder/(bn+'.fbx'),dest,bn,options(False));cloth=task(folder/(cn+'.fbx'),dest,cn,options(True))
        if not shared_skeleton:
            shared_skeleton=cloth.get_editor_property('skeleton');assert shared_skeleton
        assert cloth.get_editor_property('skeleton')==shared_skeleton
        for i,slot in enumerate(body.get_editor_property('static_materials')):
            name=str(slot.material_slot_name)
            key='M_Rattan' if 'Rattan' in name else 'M_AgedBrass' if 'Brass' in name else 'M_BlackIron' if 'Iron' in name else 'M_Walnut' if stage<3 else 'M_MilitaryWood'
            body.set_material(i,EA.load_asset(REPORT['materials'][key]))
        mats=cloth.get_editor_property('materials')
        for slot in mats:slot.set_editor_property('material_interface',EA.load_asset(REPORT['materials'][f'M_Cloth_Stage{stage}']))
        cloth.set_editor_property('materials',mats)
        EA.save_loaded_asset(body);EA.save_loaded_asset(cloth)
        REPORT['stages'][str(stage)]={'body':body.get_path_name(),'cloth':cloth.get_path_name(),'body_bounds':str(body.get_bounds()),'cloth_materials':len(mats)}
        save_report()
    REPORT['skeleton']=shared_skeleton.get_path_name()
    for file in sorted((SRC/'Shared/Animations').glob('*.fbx')):
        o=u.FbxImportUI();o.set_editor_property('automated_import_should_detect_type',False);o.set_editor_property('import_mesh',False);o.set_editor_property('import_animations',True);o.set_editor_property('import_materials',False);o.set_editor_property('import_textures',False);o.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_ANIMATION);o.set_editor_property('skeleton',shared_skeleton)
        data=o.anim_sequence_import_data;data.set_editor_property('import_uniform_scale',1.);data.set_editor_property('convert_scene',True);data.set_editor_property('convert_scene_unit',True);data.set_editor_property('force_front_x_axis',False);data.set_editor_property('use_default_sample_rate',False);data.set_editor_property('custom_sample_rate',30)
        anim=task(file,DEST+'/Shared/Animations',file.stem,o);anim.set_editor_property('enable_root_motion',False);EA.save_loaded_asset(anim)
        length=anim.get_play_length();assert abs(length-(1. if 'Idle' in file.stem else 64/30))<.001,(file.stem,length)
        REPORT['animations'][file.stem]={'path':anim.get_path_name(),'seconds':length}
    assert len(REPORT['animations'])==18
    # UE Interchange can omit these authored UCX boxes; install their exact
    # inexpensive primitive equivalents before declaring the import complete.
    save_report()
    import runpy
    runpy.run_path(str(ROOT/'Scripts/BasketIntegration/repair_collision.py'))
    REPORT['success']=True;save_report();print('BASKET_IMPORT_COMPLETE',len(REPORT['textures']),len(REPORT['materials']),len(REPORT['animations']))
except Exception:
    REPORT['success']=False;REPORT['error']=traceback.format_exc();save_report();raise
