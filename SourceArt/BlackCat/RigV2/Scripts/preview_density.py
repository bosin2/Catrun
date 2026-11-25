from pathlib import Path
code=Path(__file__).with_name('inspect_uniform.py').read_text(encoding='utf-8-sig').replace("parents[1]/'UniformJointRepair'","parents[1]/'UniformJointRepair'/'UniformDensity'")
exec(compile(code,__file__,'exec'))
