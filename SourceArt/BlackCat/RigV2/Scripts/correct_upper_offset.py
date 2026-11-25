import bpy,math
from mathutils import Vector
m=bpy.data.objects['SK_BlackCat_RigV2'];rid=m.data.attributes['uniform_ring_id'];keys=m.data.shape_keys.key_blocks
for v in m.data.vertices:
 code=rid.data[v.index].value
 if code%100!=7:continue
 side=1 if code//100 in [1,3] else -1;cx=.026*side;cy=-.036 if code//100<3 else .038;rad=Vector((v.co.x-cx,v.co.y-cy,0)).normalized();delta=Vector((side*.0008,0,0))-rad*.0008
 v.co+=delta
 for key in keys:key.data[v.index].co+=delta
m.data.update();bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
