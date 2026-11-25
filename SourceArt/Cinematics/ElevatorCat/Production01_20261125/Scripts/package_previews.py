import json,pathlib,subprocess,math
from PIL import Image,ImageDraw,ImageFont
OUT=pathlib.Path(__file__).resolve().parents[1];m=json.loads((OUT/'manifest.json').read_text());font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
views=['front','side','oblique'];concat=[]
for clip in m['clips']:
 cid=clip['id'];name=clip['action'].replace('AN_BlackCat_Elevator_','');base=OUT/'Previews'/'Frames'/cid
 expected=math.ceil(clip['frames'][1]/2)
 assert all(len(list((base/v).glob('*.png')))==expected for v in views),(cid,'incomplete render')
 panels=OUT/'Previews'/'Panels'/cid;panels.mkdir(parents=True,exist_ok=True)
 for i in range(expected):
  panel=Image.new('RGB',(1536,552),(23,26,32));d=ImageDraw.Draw(panel)
  for vi,v in enumerate(views):
   panel.paste(Image.open(base/v/f'{i:04d}.png').convert('RGB'),(vi*512,40));d.text((vi*512+12,10),f'{cid} {name} | {v.upper()} | f{i*2+1}',font=font,fill=(235,235,235))
  panel.save(panels/f'{i:04d}.jpg',quality=90)
 video=OUT/'Previews'/f'{cid}_{name}.mp4'
 subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','15','-i',str(panels/'%04d.jpg'),'-t',str(clip['seconds']),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
 # Every rendered frame, all three views; consecutive pages preserve temporal order.
 sheets=OUT/'QA'/'TemporalSheets';sheets.mkdir(exist_ok=True)
 for start in range(0,expected,20):
  sheet=Image.new('RGB',(1920,865),(15,18,22))
  for k in range(start,min(start+20,expected)):
   im=Image.open(panels/f'{k:04d}.jpg').resize((480,173));sheet.paste(im,(((k-start)%4)*480,((k-start)//4)*173))
  sheet.save(sheets/f'{cid}_{start:03d}.jpg',quality=93)
 concat.append("file '"+video.as_posix()+"'")
 print('PACKAGED',cid,flush=True)
(OUT/'Previews/concat.txt').write_text('\n'.join(concat))
subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(OUT/'Previews/concat.txt'),'-c','copy',str(OUT/'Previews/ALL_09_ThreeViews.mp4')],check=True)
cards=''.join(f'<section><h2>{c["id"]} · {c["action"].replace("AN_BlackCat_Elevator_","")}</h2><video controls loop preload="metadata" src="{c["id"]}_{c["action"].replace("AN_BlackCat_Elevator_","")}.mp4"></video><p>30fps action · {c["frames"][1]} frames · {c["seconds"]:.3f}s · 15fps Blender preview</p></section>' for c in m['clips'])
(OUT/'Previews/index.html').write_text('<!doctype html><meta charset="utf-8"><title>Elevator Cat · 9 Animations</title><style>body{background:#11151c;color:#e3e9f0;font:16px sans-serif;margin:32px}video{width:100%;max-width:1536px}section{margin:36px 0}p{color:#aab8c8}</style><h1>Elevator Cat · 9 Animations</h1><p>Original BlackCat mesh / 78 bones preserved. FRONT · SIDE · OBLIQUE. Silent Blender renders; reference elevator cutaway. Unreal playback not tested.</p><video controls src="ALL_09_ThreeViews.mp4"></video>'+cards,encoding='utf-8')
