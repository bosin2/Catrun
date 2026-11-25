from pathlib import Path
HERE=Path(__file__).parent
exec(compile((HERE/'create_revision.py').read_text(encoding='utf8').split('cam=preview_setup()')[0],str(HERE/'create_revision.py'),'exec'))
cam=preview_setup();cam.data.ortho_scale=.50
for kind,f in [('launch',6),('launch',13),('flight',10)]:
 evaluate(kind,f)
 for label,loc in [('rear',(.40,.30,.19)),('side',(.50,.03,.17))]:
  cam.location=loc;cam.rotation_euler=(Vector((0,-.015,.14))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Previews'/f'latest_{kind}_{f}_{label}.png');bpy.ops.render.render(write_still=True)
