import unreal,sys,json,difflib
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
for asset,snapshot in [(ARM_BP,'armor-after.json'),(CTX,'context-after.json')]:
 current=dump(AS.load_asset(asset));(OUT/('live-'+snapshot)).write_text(json.dumps(current,indent=2,ensure_ascii=False),encoding='utf8')
 expected=json.loads((OUT/snapshot).read_text(encoding='utf8'))
 delta=''.join(difflib.unified_diff(json.dumps(expected,indent=2,ensure_ascii=False).splitlines(True),json.dumps(current,indent=2,ensure_ascii=False).splitlines(True)))
 (OUT/('compare-'+snapshot+'.diff')).write_text(delta,encoding='utf8');print(asset,len(delta),delta[:3500])
