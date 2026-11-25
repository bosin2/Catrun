from pathlib import Path
folder=Path(__file__).resolve().parent
for script_name in ['unwrap_uniform.py','qa_uniform.py','review_uniform.py','inspect_uniform.py','wire_uniform.py','scan_uniform_surface.py','review_uniform_motion.py']:
 script_path=folder/script_name
 script_text=script_path.read_text(encoding='utf-8-sig').replace("parents[1]/'UniformJointRepair'","parents[1]/'UniformJointRepair'/'UniformDensity'")
 if script_name=='review_uniform_motion.py':script_text=script_text.replace('report={}',"O=O/'UniformDensity';report={}")
 exec(compile(script_text,str(script_path),'exec'),{'__file__':str(script_path),'__name__':'__main__'})
