from pathlib import Path
code=Path(__file__).with_name('scan_uniform_surface.py').read_text(encoding='utf-8-sig')
exec(compile(code.split("report={'neutral'")[0],__file__,'exec'))
reset();co,_,_=evaluated();mats=np.array([p.material_index for p in m.data.polygons]);auth=np.array([x.value for x in m.data.attributes['uniform_body_surface'].data]);low=np.where((auth[poly]>0)&(co[tris].max(axis=1)[:,2]<.085))[0];r=surface(co,low);print(r)
ring=m.data.attributes['uniform_ring_id']
for pair in r['examples']:
 for tid in pair:print('TRI',tid,'region',int(pf[poly[tid]]),'verts',[(int(i),co[i].tolist(),ring.data[int(i)].value) for i in tris[tid]])
