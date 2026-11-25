"""Reversible style examples from the actual rig, not generated replacement cats."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1]/'StyleExamples';O.mkdir(exist_ok=True)
a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
sc.render.engine='BLENDER_EEVEE';sc.render.resolution_x=900;sc.render.resolution_y=900;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
sc.render.film_transparent=False
sc.world=bpy.data.worlds.new('StyleStudio_World');sc.world.use_nodes=True
bg=next(n for n in sc.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs['Color'].default_value=(.36,.40,.46,1);bg.inputs['Strength'].default_value=.45
sc.view_settings.view_transform='AgX';sc.view_settings.exposure=0
cam=bpy.data.objects.new('Style_Camera',bpy.data.cameras.new('Style_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.29
cam.location=(.38,-.57,.27);cam.rotation_euler=(Vector((0,0,.108))-cam.location).to_track_quat('-Z','Y').to_euler()
def light(name,pos,power,size,color):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(name,d);sc.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((0,0,.11))-o.location).to_track_quat('-Z','Y').to_euler()
light('Key',(-.30,-.42,.5),14,.35,(1,.9,.8));light('Fill',(.35,-.15,.25),5,.32,(.78,.87,1));light('Rim',(.1,.3,.4),18,.25,(1,.9,.72))
floor_mesh=bpy.data.meshes.new('StudioFloor');floor_mesh.from_pydata([(-10,-10,-.0015),(10,-10,-.0015),(10,10,-.0015),(-10,10,-.0015)],[],[(0,1,2,3)]);floor=bpy.data.objects.new('StudioFloor',floor_mesh);sc.collection.objects.link(floor)
fm=bpy.data.materials.new('StudioFloor_Matte');fm.use_nodes=True;p=next(n for n in fm.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.23,.25,.28,1);p.inputs['Roughness'].default_value=.92;floor_mesh.materials.append(fm)
meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.vertex_groups]
original_mats={mat.name:mat for mat in m.data.materials};basecolors={}
for mat in list(original_mats.values()):
 p=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
 if p:basecolors[mat.name]=tuple(p.inputs['Base Color'].default_value)
original_slots={o.name:[s.material for s in o.material_slots] for o in meshes}
original_smooth=[p.use_smooth for p in m.data.polygons]
def style_material(source,style):
 mat=source.copy();mat.name=style+'_'+source.name;nodes=mat.node_tree.nodes;links=mat.node_tree.links
 p=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');color=list(p.inputs['Base Color'].default_value)
 if 'Fur' in source.name:color=[.026,.031,.043,1]
 if style=='A_Matte':
  p.inputs['Base Color'].default_value=color;p.inputs['Roughness'].default_value=.84 if 'Fur' in source.name else .55
  if 'Fur' in source.name:p.inputs['Specular IOR Level'].default_value=.22
 elif style=='B_Clay':
  if 'Fur' in source.name:color=[.043,.049,.061,1]
  p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=0;p.inputs['Roughness'].default_value=.88;p.inputs['Specular IOR Level'].default_value=.23
  p.inputs['Subsurface Weight'].default_value=.035;p.inputs['Subsurface Scale'].default_value=.001
 elif style=='C_Toon':
  nodes.clear();out=nodes.new('ShaderNodeOutputMaterial');diff=nodes.new('ShaderNodeBsdfDiffuse');diff.inputs['Color'].default_value=(.8,.8,.8,1);diff.inputs['Roughness'].default_value=0
  rgb=nodes.new('ShaderNodeShaderToRGB');ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
  ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);e=ramp.color_ramp.elements[0];e.position=.20;e.color=(.25,.25,.25,1)
  e=ramp.color_ramp.elements.new(.48);e.color=(.62,.62,.62,1);e=ramp.color_ramp.elements.new(.75);e.color=(1,1,1,1)
  if 'Fur' in source.name:color=[.095,.115,.16,1]
  mult=nodes.new('ShaderNodeMixRGB');mult.blend_type='MULTIPLY';mult.inputs[0].default_value=1;mult.inputs[2].default_value=color
  em=nodes.new('ShaderNodeEmission');links.new(diff.outputs[0],rgb.inputs[0]);links.new(rgb.outputs[0],ramp.inputs[0]);links.new(ramp.outputs[0],mult.inputs[1]);links.new(mult.outputs[0],em.inputs[0]);links.new(em.outputs[0],out.inputs['Surface'])
 return mat
for style in ['A_Matte','B_Clay','C_Toon']:
 for o in meshes:
  for i,mat in enumerate(original_slots[o.name]):o.material_slots[i].material=style_material(mat,style)
 for p in m.data.polygons:
  center=sum((m.data.vertices[i].co for i in p.vertices),Vector())/len(p.vertices)
  p.use_smooth=True if style=='B_Clay' else original_smooth[p.index] or center.z<.10
 sub=None
 if style=='B_Clay':
  sub=m.modifiers.new('ClayPreview_Subdivision','SUBSURF');sub.levels=1;sub.render_levels=1;sub.subdivision_type='CATMULL_CLARK'
 for pose,action,frame in [('Neutral','V2_AUTHORING_TEMPLATE',1),('BentPaw','V2_TEST_PawReach',46)]:
  a.animation_data.action=bpy.data.actions[action];sc.frame_set(frame);a.update_tag();bpy.context.view_layer.update()
  sc.render.filepath=str(O/(style+'_'+pose+'.png'));bpy.ops.render.render(write_still=True)
 # Separate editable example; production rig is never overwritten by style exploration.
 a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1)
 bpy.ops.wm.save_as_mainfile(filepath=str(O/(style+'.blend')),copy=True)
 if sub:m.modifiers.remove(sub)
 print('STYLE_EXAMPLE_DONE',style,flush=True)
(O/'README.txt').write_text('Style examples only. Same source rig, camera, lighting and poses.\nA: angular head and silhouette with matte materials, smoother body shading.\nB: one preview subdivision level, smooth shading and soft clay materials.\nC: stepped diffuse toon shader in Blender Eevee. Needs a separate Unreal material implementation.\nThe existing limb topology is not repaired by these materials. Bent-paw images intentionally show its current limitations.\n',encoding='utf8')
