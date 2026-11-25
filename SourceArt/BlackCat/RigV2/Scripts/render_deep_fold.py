from pathlib import Path
code=Path(__file__).with_name('inspect_uniform.py').read_text(encoding='utf-8-sig').replace("parents[1]/'UniformJointRepair'","parents[1]/'UniformJointRepair'/'UniformDensity'")
code=code.replace("cam.location=(.25,-.25,.09)","cam.location=(.25,.25,.10)").replace("Vector((.026,-.035,.04))","Vector((.026,.035,.04))")
code=code.replace("[('forearm_L',0),('forearm_L',5),('forearm_L',60),('paw_F_L',45)]","[('shin_L',90),('shin_L',120)]")
exec(compile(code,__file__,'exec'))
