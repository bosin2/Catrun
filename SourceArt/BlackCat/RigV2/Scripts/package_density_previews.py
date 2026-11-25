from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]/'UniformJointRepair'/'UniformDensity';p=root/'Previews'
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',23)
labels=['기본 자세','앞다리 60° 굽힘','발목 45° 굽힘']
names=['gray_forearm_L_0.png','gray_forearm_L_60.png','gray_paw_F_L_45.png']
board=Image.new('RGB',(1440,530),(37,39,43));d=ImageDraw.Draw(board)
for j,(label,name) in enumerate(zip(labels,names)):
 board.paste(Image.open(p/name).convert('RGB').resize((480,480),Image.Resampling.LANCZOS),(j*480,50));d.text((j*480+24,13),label,font=font,fill='white')
board.save(p/'uniform_facets_review.png')
kinds=['Body','PawReach','Curl'];labels=['몸 낮추기 + 비틀기','앞발 들기','몸 말기'];frames=[]
for f in range(1,92):
 canvas=Image.new('RGB',(1152,426),(37,39,43));draw=ImageDraw.Draw(canvas)
 for j,(kind,label) in enumerate(zip(kinds,labels)):
  canvas.paste(Image.open(p/'Motion'/kind/f'{f:04d}.png').convert('RGB').resize((384,384),Image.Resampling.LANCZOS),(j*384,42));draw.text((j*384+16,8),label,font=font,fill='white')
 frames.append(canvas)
frames[0].save(p/'uniform_motion_review.gif',save_all=True,append_images=frames[1:],duration=33,loop=0,optimize=False)
contact=Image.new('RGB',(1440,1080),(37,39,43))
for row,kind in enumerate(kinds):
 for col,f in enumerate([1,23,45,69]):contact.paste(Image.open(p/'Motion'/kind/f'{f:04d}.png').convert('RGB').resize((360,360)),(col*360,row*360))
contact.save(p/'motion_keyframes.png')
print(p/'uniform_facets_review.png');print(p/'uniform_motion_review.gif')
