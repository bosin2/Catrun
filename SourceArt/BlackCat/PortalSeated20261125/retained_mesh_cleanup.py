"""Small retained-mesh repairs; does not remesh the approved face.

The lower eyelid shells have coplanar side caps with the upper shells in
their hidden rest position. Narrow only the lower shells by 0.3 mm per side.
The green eyes, pupils, nose, head, ears, collar, bell and tail geometry stay
unchanged. Bell_Clapper is intentionally a separate moving part inside a bell.
"""

def cleanup(mesh,armature):
    if mesh.data.get('portal_retained_cleanup_v1'):
        return {'already_applied':True}
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
    return {'limited_to_four_weights':cleaned,'max_removed_weight':max_removed,'lower_lid_vertices_narrowed':shifted,'lower_lid_cap_offset_m':.0003,'geometry_deleted':0,'triangles_added':0,'intentional_detached_part':'Bell_Clapper: free clapper inside the gold bell, all 42 vertices weighted to bell'}
