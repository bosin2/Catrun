import bpy,sys,json
from pathlib import Path
p=Path('C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalSeated20261125/create_revision.py');__file__=str(p);exec(compile(p.read_text().split('cam=preview_setup()')[0],__file__,'exec'))
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check
structural=qa_check.run(objects=[body.name],profile='game',eps=.0001,tol=.002);(O/'QA_Surface'/'body_structural_final.json').write_text(json.dumps(structural,indent=2,default=str));print('STRUCTURAL',json.dumps({'pass':structural['pass'],'errors':structural['errors'],'warnings':structural['warnings']}),flush=True)
