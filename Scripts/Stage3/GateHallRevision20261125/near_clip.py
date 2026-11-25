"""Measured Stage3-only near-plane repair; import inert, root calls apply().

The 3450cm cap screen-up bound did not constrain intermediate shaft geometry
against the near plane. Numeric risk is checked here; the same extreme Lit
view after repair is still required to attribute the observed artifact.
"""
import hashlib
import itertools
import json
import math
import os
import traceback
from pathlib import Path

NEAR_CM=-4000.
FAR_CM=10000.
REGIONS={'hall_inner_faces':[-970,-4570,470,-2930],
         'exit_to_goal':[-530,-4690,30,-4550]}
OFFSET=[147.7898938366867,147.78989383668707,409.57602214449524]


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def basis():
    pitch,yaw=map(math.radians,(-55,-135))
    return ([math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch)],
            [-math.sin(yaw),math.cos(yaw),0.],[-math.sin(pitch)*math.cos(yaw),-math.sin(pitch)*math.sin(yaw),math.cos(pitch)])


def clipped_vertices(lo,hi,right,up):
    """Vertices of AABB intersected with900cm16:9 projected viewport prism."""
    planes=[]
    for i in range(3):
        n=[0.,0.,0.];n[i]=1.;planes.append((n,hi[i]));planes.append(([-x for x in n],-lo[i]))
    planes += [(right,450.),([-x for x in right],450.),(up,253.125),([-x for x in up],253.125)]
    result=[]
    for (a,aa),(b,bb),(c,cc) in itertools.combinations(planes,3):
        det=dot(a,cross(b,c))
        if abs(det)<1.e-9:continue
        terms=[cross(b,c),cross(c,a),cross(a,b)]
        p=[(aa*terms[0][i]+bb*terms[1][i]+cc*terms[2][i])/det for i in range(3)]
        if all(dot(n,p)<=value+1.e-5 for n,value in planes):result.append(p)
    return result


def calculate(actor_bounds):
    forward,right,up=basis();full=[];visible=[]
    for label,lo,hi in actor_bounds:
        for region,(x0,y0,x1,y1) in REGIONS.items():
            # Independent camera positions within a rectangle give this exact
            # relative-AABB range; mesh geometry inside the AABB is conservative.
            lower=[lo[0]-x1-OFFSET[0],lo[1]-y1-OFFSET[1],lo[2]-26.2-OFFSET[2]]
            upper=[hi[0]-x0-OFFSET[0],hi[1]-y0-OFFSET[1],hi[2]-26.2-OFFSET[2]]
            corners=list(itertools.product(*zip(lower,upper)))
            full.append({'actor':label,'region':region,'minimum_depth':min(dot(p,forward) for p in corners)})
            vertices=clipped_vertices(lower,upper,right,up)
            if vertices:visible.append({'actor':label,'region':region,'minimum_visible_depth':min(dot(p,forward) for p in vertices)})
    worst=min(full,key=lambda r:r['minimum_depth']);vis=min(visible,key=lambda r:r['minimum_visible_depth'])
    selected=math.floor((worst['minimum_depth']-50)/500)*500
    assert selected==NEAR_CM,(selected,worst)
    return {'success':True,'method':'CPU affine orthographic depth bounds; actual saved AABBs, all region positions. Viewport-prism intersection also evaluated. Not GPU verification.',
            'regions_world_xy':REGIONS,'cat_z':26.2,'camera_minus_cat':OFFSET,'forward':forward,
            'old_near_cm':-2000.,'full_geometry_minimum_depth':worst,'visible_prism_minimum_depth':vis,
            'minimum_full_geometry_with50cm_margin':worst['minimum_depth']-50,
            'selected_near_cm':selected,'selected_far_cm':FAR_CM,
            'retained_depth_margin_cm':worst['minimum_depth']-selected,
            'parts_checked':len(actor_bounds),'full_depth_rows':full,'visible_depth_rows':visible,
            'evidence_image':'Saved/Stage3IntegrationRevision20261125/After01/GateExtreme_Lit.png',
            'observed_intermediate_module':{'world_top':[220,-3725,1920],'approx_screen_1280x720':[987,541],
                'depth_cm':-1901.,'next_top_z2460_depth_cm':-2343.,
                'interpretation':'Intermediate shaft termination coincides with visible artifact, while next section crosses old near. Near clipping is supported as a candidate cause; after-render required.'},
            'not_changed':['camera pitch/yaw','camera transform/offset','ortho width/aspect','far plane','shared camera Blueprint','Stage1/Stage2']}


def offline():
    root=Path(__file__).resolve().parents[3]
    source=root/'Saved/Stage3IntegrationRevision20261125/Core01/QA/after/snapshot.json'
    snapshot=json.loads(source.read_text())
    rows=[]
    for actor in snapshot['actors'].values():
        if actor['label'].startswith('S3_GrandPillar_'):
            b=actor['all_component_bounds'];c,e=b['center'],b['extent']
            rows.append((actor['label'],[x-y for x,y in zip(c,e)],[x+y for x,y in zip(c,e)]))
    report=calculate(rows);report['snapshot']=str(source)
    output=root/'Saved/Stage3GateHallRevision20261125/RuntimeQANearClipProjection01.json'
    assert not output.exists();output.write_text(json.dumps(report,indent=2),encoding='utf8')
    return report


def apply():
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    suffix=os.environ.get('CATRUN_GATE_NEAR_FIX_PASS','01');assert suffix.replace('_','').isalnum()
    output=root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQANearClipFix'+suffix+'.json')
    assert not output.exists()
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert ed.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3' and not ed.get_game_world()
    actors=list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    selected=[a for a in actors if a.get_actor_label()=='S3_FollowCamera'];assert len(selected)==1
    actor=selected[0]
    def camera():return actor.get_component_by_class(u.CameraComponent)
    fields=('projection_mode','ortho_width','aspect_ratio','constrain_aspect_ratio','auto_calculate_ortho_planes',
            'update_ortho_planes','ortho_near_clip_plane','ortho_far_clip_plane','auto_plane_shift')
    def state():
        comp=camera()
        return {key:comp.get_editor_property(key) for key in fields}
    before=state();assert before['ortho_near_clip_plane']==-2000.,before
    assert before['ortho_far_clip_plane']==FAR_CM and not before['auto_calculate_ortho_planes'] and not before['update_ortho_planes']
    assert before['ortho_width']==900 and abs(before['aspect_ratio']-16/9)<.0001
    transforms={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
    relative_before=camera().get_relative_transform().export_text()
    package=actor.get_class().get_path_name().split('.')[0].removeprefix('/Game/')
    files=[root/'Content/Maps'/(s+'.umap') for s in ('Stage1','Stage2','Stage3')]+[root/'Content'/(package+'.uasset')]
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    rows=[]
    for a in actors:
        if a.get_actor_label().startswith('S3_GrandPillar_'):
            c,e=a.get_actor_bounds(False,False)
            rows.append((a.get_actor_label(),[c.x-e.x,c.y-e.y,c.z-e.z],[c.x+e.x,c.y+e.y,c.z+e.z]))
    result={'success':False,'save_count':0,'projection':calculate(rows),'protected_before':protected,
            'before':{k:str(v) for k,v in before.items()},'pending':'Root same GateExtreme Lit image + RuntimeQA/GPU verification'}
    try:
        camera().set_editor_property('ortho_near_clip_plane',NEAR_CM)
        # Inherited component mutation may reconstruct it: reacquire.
        after=state();expected=dict(before,ortho_near_clip_plane=NEAR_CM)
        assert after==expected,after
        assert relative_before==camera().get_relative_transform().export_text()
        assert transforms=={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
        result['after']={k:str(v) for k,v in after.items()}
        result['success']=True
    except Exception:
        result['error']=traceback.format_exc()
        camera().set_editor_property('ortho_near_clip_plane',before['ortho_near_clip_plane'])
    finally:
        result['protected_after']={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected}
        result['disk_preserved']=protected==result['protected_after'];result['success'] &= result['disk_preserved']
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf8')
    assert result['success'],'Near plane repair failed: '+str(output)
    return result
