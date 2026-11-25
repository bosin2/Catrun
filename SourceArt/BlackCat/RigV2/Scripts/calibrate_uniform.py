from pathlib import Path
code=Path(__file__).with_name('review_uniform.py').read_text(encoding='utf-8-sig')
exec(compile(code.split("cam=bpy.data.objects.new")[0],__file__,'exec'))
