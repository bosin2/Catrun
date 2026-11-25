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
// CatPosition is the capsule centre, not its feet. Keep sampling on that
// screen-depth plane; neither enlarge world AABBs nor continue behind Cat.
bool Ortho=IsOrthoProjection(ResolvedView);
float3 Forward=normalize(ResolvedView.ViewForward);
float3 Right=normalize(ResolvedView.ViewRight);
float3 Up=normalize(ResolvedView.ViewUp);
float2 Samples[9]={float2(0,0),float2(1,0),float2(-1,0),
    float2(0,1),float2(0,-1),float2(0.70710678,0.70710678),
    float2(-0.70710678,0.70710678),float2(0.70710678,-0.70710678),
    float2(-0.70710678,-0.70710678)};
[unroll] for(int Sample=0;Sample<9;++Sample)
{
    float3 Origin=Cat.xyz+max(Radius,0.0)*(Right*Samples[Sample].x+Up*Samples[Sample].y);
    float3 ToCamera=Camera-Origin;
    float CameraDistance=length(ToCamera);
    float3 Direction=Ortho ? -Forward : ToCamera/max(CameraDistance,0.0001);
    // Ortho near planes may be behind the camera origin (-2000 cm here).
    // A foreground half-ray avoids incorrectly clipping visible architecture
    // to the camera pivot plane; off-screen primitives cannot draw pixels.
    float Enter=2.0,Exit=Ortho ? 1.0e20 : CameraDistance;
    bool Hit=true;
    [unroll] for(int Axis=0;Axis<3;++Axis)
    {
        float Lower=Center[Axis]-E[Axis],Upper=Center[Axis]+E[Axis];
        if(abs(Direction[Axis])<0.000001)
        {
            if(Origin[Axis]<Lower || Origin[Axis]>Upper) Hit=false;
        }
        else
        {
            float A=(Lower-Origin[Axis])/Direction[Axis];
            float B=(Upper-Origin[Axis])/Direction[Axis];
            Enter=max(Enter,min(A,B));Exit=min(Exit,max(A,B));
        }
    }
    if(Hit && Exit>2.0 && Enter<=Exit) return 0.0;
}
return 1.0;'''
def owned(path):
    if not EA.does_asset_exist(path):return None
    o=EA.load_asset(path);assert EA.get_metadata_tag(o,'Stage3ReadabilityOwner')==OWNER,path
    return o
def apply():
    root=Path(u.Paths.project_dir()).resolve();report={'assignments':[],'parents':{},'opaque_frames':[],'protected_interactive':[],'scope':'Unpadded wall bounds, 9 foreground silhouette rays; no collision/gameplay changes'}
    resolved={}
    def interactive(source):
        return bool(source and EA.get_metadata_tag(source,'Stage3InteractiveOwner'))
    def instance(source):
        # Reapplying architectural readability must never re-enable fading on
        # an object explicitly made opaque by interactive_visibility.py.
        if interactive(source):return source
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
            nodes['Radius'].set_editor_property('default_value',24.)
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
        ML.set_material_instance_scalar_parameter_value(mi,'CameraClearRadius',24.)
        ML.update_material_instance(mi);assert EA.save_loaded_asset(mi)
        if isinstance(source,u.MaterialInstanceConstant):
            assert str(ML.get_material_instance_vector_parameter_value(source,'ColorTint'))==str(ML.get_material_instance_vector_parameter_value(mi,'ColorTint'))
            assert ML.get_material_instance_scalar_parameter_value(source,'Brightness')==ML.get_material_instance_scalar_parameter_value(mi,'Brightness')
        report['parents'][pp]={'source':base.get_path_name(),'instance':ip,'radius_cm':24,'mode':'9 screen-space foreground rays; unpadded representative wall bounds'}
        resolved[source.get_path_name()]=mi
        return mi
    actors=list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    walls=[a for a in actors if a.get_actor_label().startswith('S3_Wall_')]
    def bounds(a):
        p,e=a.get_actor_bounds(False,False)
        return [p.x-e.x,p.y-e.y,p.z-e.z],[p.x+e.x,p.y+e.y,p.z+e.z]
    wall_bounds={a.get_actor_label():bounds(a) for a in walls}
    def opaque_frame(source):
        if interactive(source):return source
        # Unwrap previously assigned cutaway material without modifying it.
        while EA.get_metadata_tag(source,'Stage3ReadabilitySource'):
            source=EA.load_asset(EA.get_metadata_tag(source,'Stage3ReadabilitySource'))
            assert source,'Final gate frame lost its original material'
        key=hashlib.sha256(source.get_path_name().encode()).hexdigest()[:12]
        dest='/Game/Environment/Stage3/GothicRevision_20261125/InteractiveReadability'
        owner='Stage3AlwaysVisibleInteractions20261125'
        pp=dest+'/M_Interactive_'+key;ip=dest+'/MI_Interactive_'+key
        base=source.get_base_material() if isinstance(source,u.MaterialInstanceConstant) else source
        parent=EA.load_asset(pp) if EA.does_asset_exist(pp) else None
        if parent:assert EA.get_metadata_tag(parent,'Stage3InteractiveOwner')==owner,pp
        else:
            parent=EA.duplicate_asset(base.get_path_name(),pp);assert parent
            EA.set_metadata_tag(parent,'Stage3InteractiveOwner',owner)
            parent.set_editor_property('blend_mode',u.BlendMode.BLEND_OPAQUE)
            one=ML.create_material_expression(parent,u.MaterialExpressionConstant,-150,1500)
            one.set_editor_property('r',1.)
            for prop in (u.MaterialProperty.MP_OPACITY,u.MaterialProperty.MP_OPACITY_MASK):
                assert ML.connect_material_property(one,'',prop)
            ML.recompile_material(parent);assert EA.save_loaded_asset(parent)
        assert parent.get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE
        mi=EA.load_asset(ip) if EA.does_asset_exist(ip) else None
        if mi:assert EA.get_metadata_tag(mi,'Stage3InteractiveOwner')==owner,ip
        else:
            mi=EA.duplicate_asset(source.get_path_name(),ip) if isinstance(source,u.MaterialInstanceConstant) else u.AssetToolsHelpers.get_asset_tools().create_asset(ip.rsplit('/',1)[-1],dest,u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
            assert mi
            EA.set_metadata_tag(mi,'Stage3InteractiveOwner',owner)
            EA.set_metadata_tag(mi,'Stage3InteractiveSource',source.get_path_name())
            ML.set_material_instance_parent(mi,parent)
            overrides=mi.get_editor_property('base_property_overrides')
            overrides.set_editor_property('override_blend_mode',False)
            mi.set_editor_property('base_property_overrides',overrides)
            ML.update_material_instance(mi);assert EA.save_loaded_asset(mi)
        return mi
    groups={};members=[]
    for a in actors:
        label=a.get_actor_label()
        architecture=label.startswith(('S3_Wall_','S3_Gothic_Wall','S3_GrandPillar_','S3_GothicVisual_PlainWall'))
        attached_decor=label.startswith('S3_Gothic_') and any(k in label for k in ('_Sconce','_Banner'))
        if label in ('S3_FinalGate_LowerFrame','S3_FinalGate_UpperFrame'):
            c=a.get_component_by_class(u.StaticMeshComponent)
            if c:
                for slot in range(c.get_num_materials()):
                    old=c.get_material(slot)
                    if not old:continue
                    new=opaque_frame(old)
                    if new!=old:c.set_material(slot,new)
                    report['opaque_frames'].append({'actor':label,'slot':slot,'source':old.get_path_name(),'assigned':new.get_path_name()})
            continue
        if not (architecture or attached_decor):continue
        c=a.get_component_by_class(u.StaticMeshComponent)
        if not c:continue
        if label.startswith('S3_Wall_'):group=label
        elif label.startswith('S3_GrandPillar_'):group=label.rsplit('_',1)[0]
        else:
            p,e=a.get_actor_bounds(False,False)
            def distance(item):
                lo,hi=item[1]
                return max(lo[0]-p.x,0,p.x-hi[0])**2+max(lo[1]-p.y,0,p.y-hi[1])**2+.0001*((p.x-(lo[0]+hi[0])/2)**2+(p.y-(lo[1]+hi[1])/2)**2)
            group=min(wall_bounds.items(),key=distance)[0]
        # A sconce/banner can protrude into empty space. Use its supporting
        # wall's exact bounds for the shared decision, not the union AABB.
        lo,hi=wall_bounds[group] if group in wall_bounds else bounds(a)
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
        report['groups'].setdefault(group,{'center':center,'extent':extent,'bounds_source':'representative wall' if group in wall_bounds else 'coaxial pillar stack','members':[]})['members'].append(label)
        for i in range(c.get_num_materials()):
            old=c.get_material(i)
            if not old:continue
            if interactive(old):
                report['protected_interactive'].append({'actor':label,'slot':i,'material':old.get_path_name()})
                continue
            new=instance(old);c.set_material(i,new)
            report['assignments'].append({'actor':label,'slot':i,'source':old.get_path_name(),'assigned':new.get_path_name()})
    report['success']=True
    (root/'Saved/Stage3GothicRevision20261125/occlusion_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
