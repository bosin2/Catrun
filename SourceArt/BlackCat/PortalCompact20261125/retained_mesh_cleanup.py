"""Small retained-mesh repairs; does not remesh the approved face.

The lower eyelid shells have coplanar side caps with the upper shells in
their hidden rest position. Narrow only the lower shells by 0.3 mm per side.
The green eyes, pupils, nose, head, ears, collar, bell and tail geometry stay
unchanged. Bell_Clapper is intentionally a separate moving part inside a bell.
"""

def _rigid_compact_head(mesh,armature):
    """Keep the approved closed head shell rigid while its neck is shortened.

    The original shell carries chest/breath weights at the back of the head.
    Compact retargeting gives head and torso different translations, turning
    those residual influences into thin protruding triangles. Other connected
    shells (ears, lids, eyes, collar and tail) retain their own weights.
    """
    if mesh.data.get('portal_compact_rigid_head_v2'):
        return {'head_already_rigid':True}
    count=len(mesh.data.vertices);parent=list(range(count))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for edge in mesh.data.edges:
        x,y=map(find,edge.vertices)
        if x!=y:parent[x]=y
    head=mesh.vertex_groups.get('head')
    if head is None:raise ValueError('Retained mesh has no head vertex group')
    islands={};scores={}
    for v in mesh.data.vertices:
        root=find(v.index);islands.setdefault(root,[]).append(v.index)
        scores[root]=scores.get(root,0.0)+sum(g.weight for g in v.groups if g.group==head.index)
    shell=max(scores,key=scores.get);ids=islands[shell]
    if len(ids)<100:raise ValueError('Could not identify the original connected head shell safely')
    changed=0
    deform={g.index for g in mesh.vertex_groups if g.name in armature.data.bones and armature.data.bones[g.name].use_deform}
    for index in ids:
        entries=[(g.group,g.weight) for g in mesh.data.vertices[index].groups if g.group in deform]
        if len(entries)!=1 or entries[0][0]!=head.index or abs(entries[0][1]-1)>1e-6:changed+=1
        for group,weight in entries:mesh.vertex_groups[group].remove([index])
        head.add([index],1.0,'REPLACE')
    mesh.data['portal_compact_rigid_head_v2']=True
    return {'head_shell_vertices':len(ids),'head_weight_vertices_changed':changed,'head_rest_geometry_changed':False,'head_weights':'100 percent head on connected fur head shell only'}

def cleanup(mesh,armature):
    compact_report=_rigid_compact_head(mesh,armature)
    if mesh.data.get('portal_retained_cleanup_v1'):
        return {'already_applied':True,**compact_report}
    deform={g.index for g in mesh.vertex_groups if g.name in armature.data.bones and armature.data.bones[g.name].use_deform}
    cleaned=0;max_removed=0.0
    for v in mesh.data.vertices:
        entries=sorted([(e.group,e.weight) for e in v.groups if e.group in deform and e.weight>1e-4],key=lambda x:x[1],reverse=True)
        if len(entries)<=4:continue
        cleaned+=1;max_removed=max(max_removed,sum(w for _,w in entries[4:]))
        for group,_ in entries[4:]:mesh.vertex_groups[group].remove([v.index])
        total=sum(w for _,w in entries[:4])
        for group,w in entries[:4]:mesh.vertex_groups[group].add([v.index],w/total,'REPLACE')
    shifted=0
    for side in ('L','R'):
        group_ids={g.index for g in mesh.vertex_groups if g.name.startswith('Lid_Lower_'+side+'_')}
        verts=[v for v in mesh.data.vertices if any(e.group in group_ids and e.weight>.5 for e in v.groups)]
        if not verts:continue
        lo=min(v.co.x for v in verts);hi=max(v.co.x for v in verts);mid=(lo+hi)*.5
        scale=1.0-.0006/(hi-lo)
        for v in verts:v.co.x=mid+(v.co.x-mid)*scale
        shifted+=len(verts)
    mesh.data['portal_retained_cleanup_v1']=True
    mesh.data.update()
    return {**compact_report,'limited_to_four_weights':cleaned,'max_removed_weight':max_removed,'lower_lid_vertices_narrowed':shifted,'lower_lid_cap_offset_m':.0003,'geometry_deleted':0,'triangles_added':0,'intentional_detached_part':'Bell_Clapper: free clapper inside the gold bell, all 42 vertices weighted to bell'}
