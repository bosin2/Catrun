"""Stable Stage3-only foreground cutaway for the possessed cat camera.

Preserves geometry/collision and all BaseColor, Normal, ORM, UV graph outputs.
Replaces the noisy generic wall dither on selected architecture only. Existing
shared materials/functions are never edited.
"""
import hashlib,json
from pathlib import Path
import unreal as u
DEST='/Game/Environment/Stage3/GothicRevision_20261125/CameraReadability'
OWNER='Stage3CameraCutaway20261125'
EA=u.EditorAssetLibrary;ML=u.MaterialEditingLibrary
CODE='''if(IsShadowDepthShader()) return 1.0;
if(Cat.a<0.5) return 1.0;
float3 Center = dot(GroupExtent,GroupExtent)>0.1 ? GroupCenter : ObjectCenter;
float3 E = max(dot(GroupExtent,GroupExtent)>0.1 ? GroupExtent : ObjectExtent,0.1);
if(Center.z+E.z<Cat.z-26.0) return 1.0;
float3 V=Cat.xyz+float3(0,0,35)-Camera;
float Depth=length(V); float3 R=V/max(Depth,1.0);
float Along=dot(Center-Camera,R), HalfDepth=dot(abs(R),E);
if(Along-HalfDepth>=Depth-20.0 || Along+HalfDepth<=0.0) return 1.0;
float3 SafeR=float3(R.x<0?-max(abs(R.x),1e-5):max(abs(R.x),1e-5),R.y<0?-max(abs(R.y),1e-5):max(abs(R.y),1e-5),R.z<0?-max(abs(R.z),1e-5):max(abs(R.z),1e-5));
float3 T0=(Center-E-Radius-Camera)/SafeR;
float3 T1=(Center+E+Radius-Camera)/SafeR;
float3 Lo=min(T0,T1),Hi=max(T0,T1);
float Enter=max(Lo.x,max(Lo.y,Lo.z)),Exit=min(Hi.x,min(Hi.y,Hi.z));
return (Exit>=max(Enter,0.0) && Enter<=Depth+65.0)?0.0:1.0;'''
def owned(path):
    if not EA.does_asset_exist(path):return None
    o=EA.load_asset(path);assert EA.get_metadata_tag(o,'Stage3ReadabilityOwner')==OWNER,path
    return o
def apply():
    root=Path(u.Paths.project_dir()).resolve();report={'assignments':[],'parents':{},'scope':'Architecture foreground presentation only; no collision/gameplay changes'}
    resolved={}
    def instance(source):
        if source.get_path_name().startswith(DEST):
            source=EA.load_asset(EA.get_metadata_tag(source,'Stage3ReadabilitySource'))
            assert source,'Owned cutaway material has no original source reference'
        if source.get_path_name() in resolved:return resolved[source.get_path_name()]
        key=hashlib.sha256(source.get_path_name().encode()).hexdigest()[:12]
        pp=DEST+'/M_Cutaway_'+key;ip=DEST+'/MI_Cutaway_'+key
        parent=owned(pp)
        base=source.get_base_material() if isinstance(source,u.MaterialInstanceConstant) else source
        if not parent:
            parent=EA.duplicate_asset(base.get_path_name(),pp);assert parent
            EA.set_metadata_tag(parent,'Stage3ReadabilityOwner',OWNER)
        if EA.get_metadata_tag(parent,'WholeComponentCutaway')!='2':
            parent.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED)
            parent.set_editor_property('opacity_mask_clip_value',.333)
            nodes={}
            for name,cls in [('ObjectCenter',u.MaterialExpressionObjectPositionWS),('ObjectExtent',u.MaterialExpressionObjectBounds),
                             ('GroupCenter',u.MaterialExpressionVectorParameter),('GroupExtent',u.MaterialExpressionVectorParameter),
                             ('Camera',u.MaterialExpressionCameraPositionWS),
                             ('Cat',u.MaterialExpressionCollectionParameter),('Radius',u.MaterialExpressionScalarParameter)]:
                nodes[name]=ML.create_material_expression(parent,cls,-600,1000+150*len(nodes))
            for name,index in [('GroupCenter',16),('GroupExtent',20)]:
                nodes[name].set_editor_property('parameter_name','Cutaway'+name)
                nodes[name].set_editor_property('default_value',u.LinearColor(0,0,0,0))
                nodes[name].set_editor_property('use_custom_primitive_data',True)
                nodes[name].set_editor_property('primitive_data_index',index)
            nodes['Cat'].set_editor_property('collection',EA.load_asset('/Game/Characters/BlackCat/Materials/MPC_CatOcclusion'))
            nodes['Cat'].set_editor_property('parameter_name','CatPosition')
            nodes['Radius'].set_editor_property('parameter_name','CameraClearRadius')
            nodes['Radius'].set_editor_property('default_value',90.)
            custom=ML.create_material_expression(parent,u.MaterialExpressionCustom,-150,1100)
            custom.set_editor_property('code',CODE);custom.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1)
            inputs=[]
            for name in nodes:
                inp=u.CustomInput();inp.set_editor_property('input_name',name);inputs.append(inp)
            custom.set_editor_property('inputs',inputs)
            for name,node in nodes.items():assert ML.connect_material_expressions(node,'',custom,name)
            assert ML.connect_material_property(custom,'',u.MaterialProperty.MP_OPACITY_MASK)
            EA.set_metadata_tag(parent,'WholeComponentCutaway','2')
            # Check every non-opacity root against the copied original.
        else:
            custom=ML.get_material_property_input_node(parent,u.MaterialProperty.MP_OPACITY_MASK)
            assert isinstance(custom,u.MaterialExpressionCustom)
            custom.set_editor_property('code',CODE)
        for prop in ['BASE_COLOR','NORMAL','AMBIENT_OCCLUSION','ROUGHNESS','METALLIC','EMISSIVE_COLOR']:
            p=getattr(u.MaterialProperty,'MP_'+prop)
            a=ML.get_material_property_input_node(base,p);b=ML.get_material_property_input_node(parent,p)
            assert (a.get_name() if a else None)==(b.get_name() if b else None),(source.get_name(),prop)
            assert ML.get_material_property_input_node_output_name(base,p)==ML.get_material_property_input_node_output_name(parent,p)
        ML.recompile_material(parent);assert EA.save_loaded_asset(parent)
        mi=owned(ip)
        if not mi:
            if isinstance(source,u.MaterialInstanceConstant):mi=EA.duplicate_asset(source.get_path_name(),ip)
            else:mi=u.AssetToolsHelpers.get_asset_tools().create_asset(ip.rsplit('/',1)[-1],DEST,u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
            EA.set_metadata_tag(mi,'Stage3ReadabilityOwner',OWNER)
            EA.set_metadata_tag(mi,'Stage3ReadabilitySource',source.get_path_name())
        ML.set_material_instance_parent(mi,parent)
        ML.set_material_instance_scalar_parameter_value(mi,'CameraClearRadius',90.)
        ML.update_material_instance(mi);assert EA.save_loaded_asset(mi)
        if isinstance(source,u.MaterialInstanceConstant):
            assert str(ML.get_material_instance_vector_parameter_value(source,'ColorTint'))==str(ML.get_material_instance_vector_parameter_value(mi,'ColorTint'))
            assert ML.get_material_instance_scalar_parameter_value(source,'Brightness')==ML.get_material_instance_scalar_parameter_value(mi,'Brightness')
        report['parents'][pp]={'source':base.get_path_name(),'instance':ip,'radius_cm':90,'mode':'whole wall group'}
        resolved[source.get_path_name()]=mi
        return mi
    actors=list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    walls=[a for a in actors if a.get_actor_label().startswith('S3_Wall_')]
    def bounds(a):
        p,e=a.get_actor_bounds(False,False)
        return [p.x-e.x,p.y-e.y,p.z-e.z],[p.x+e.x,p.y+e.y,p.z+e.z]
    wall_bounds={a.get_actor_label():bounds(a) for a in walls}
    groups={};members=[]
    for a in actors:
        label=a.get_actor_label()
        architecture=label.startswith(('S3_Wall_','S3_Gothic_Wall','S3_GrandPillar_','S3_GothicVisual_PlainWall'))
        attached_decor=label.startswith('S3_Gothic_') and any(k in label for k in ('_Sconce','_Banner'))
        if not (architecture or attached_decor or label in ('S3_FinalGate_LowerFrame','S3_FinalGate_UpperFrame')):continue
        c=a.get_component_by_class(u.StaticMeshComponent)
        if not c:continue
        if label.startswith('S3_Wall_'):group=label
        elif label.startswith('S3_GrandPillar_'):group=label.rsplit('_',1)[0]
        elif label.startswith('S3_FinalGate_'):group='FinalGateFrame'
        else:
            p,e=a.get_actor_bounds(False,False)
            def distance(item):
                lo,hi=item[1]
                return max(lo[0]-p.x,0,p.x-hi[0])**2+max(lo[1]-p.y,0,p.y-hi[1])**2+.0001*((p.x-(lo[0]+hi[0])/2)**2+(p.y-(lo[1]+hi[1])/2)**2)
            group=min(wall_bounds.items(),key=distance)[0]
        lo,hi=bounds(a)
        if group not in groups:groups[group]=[lo[:],hi[:]]
        else:
            groups[group]=[[min(x,y) for x,y in zip(groups[group][0],lo)],[max(x,y) for x,y in zip(groups[group][1],hi)]]
        members.append((a,c,group))
    report['groups']={}
    for a,c,group in members:
        label=a.get_actor_label();lo,hi=groups[group]
        center=[(x+y)/2 for x,y in zip(lo,hi)];extent=[(y-x)/2 for x,y in zip(lo,hi)]
        c.set_default_custom_primitive_data_vector4(16,u.Vector4(*center,1))
        c.set_default_custom_primitive_data_vector4(20,u.Vector4(*extent,1))
        report['groups'].setdefault(group,{'center':center,'extent':extent,'members':[]})['members'].append(label)
        for i in range(c.get_num_materials()):
            old=c.get_material(i)
            if not old:continue
            new=instance(old);c.set_material(i,new)
            report['assignments'].append({'actor':label,'slot':i,'source':old.get_path_name(),'assigned':new.get_path_name()})
    report['success']=True
    (root/'Saved/Stage3GothicRevision20261125/occlusion_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
