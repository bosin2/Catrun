import bpy, json, sys, pathlib
sys.path.insert(0, r'C:/Users/whghk/.codex/skills/blender-core/scripts')
import env_report
out=pathlib.Path(r'C:/Users/whghk/Catrun/SourceArt/Cinematics/ElevatorCat/Production01_20261125/QA')
def v(x): return list(x)
d={'environment':env_report.run(),'objects':[], 'actions':[]}
for o in bpy.data.objects:
    x={'name':o.name,'type':o.type,'location':v(o.location),'rotation':v(o.rotation_euler),'scale':v(o.scale),'dimensions':v(o.dimensions),'parent':o.parent.name if o.parent else None}
    if o.type=='ARMATURE':
        x['bones']=[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':v(b.head_local),'tail':v(b.tail_local),'matrix':[v(r) for r in b.matrix_local],'deform':b.use_deform} for b in o.data.bones]
        x['constraints']={b.name:[c.type for c in b.constraints] for b in o.pose.bones if b.constraints}
    if o.type=='MESH':
        x['verts']=len(o.data.vertices);x['polys']=len(o.data.polygons)
        x['shapekeys']=[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else []
        x['modifiers']=[(m.name,m.type) for m in o.modifiers]
    d['objects'].append(x)
for a in bpy.data.actions:d['actions'].append({'name':a.name,'range':v(a.frame_range),'slots':[s.identifier for s in a.slots]})
(out/'source_inspection.json').write_text(json.dumps(d,indent=2))
print('INSPECT', [(x['name'],x['type']) for x in d['objects']],d['actions'])
