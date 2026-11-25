from pathlib import Path
folder=Path(__file__).resolve().parent
for script_name in ['scan_uniform_surface.py','review_uniform_motion.py']:
 path=folder/script_name;code=path.read_text(encoding='utf-8-sig').replace("parents[1]/'UniformJointRepair'","parents[1]/'UniformJointRepair'/'UniformDensity'")
 if script_name=='review_uniform_motion.py':code=code.replace('report={}',"O=O/'UniformDensity';report={}")
 exec(compile(code,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
