"""Deterministic small brushed-aluminium maps; uses the bundled Pillow runtime.
No external artwork: the shield and Chinese wordmark are drawn locally.
"""
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'assets'
OUT.mkdir(exist_ok=True)
FONT=OUT/'brand_subset.ttf'
rng=random.Random(37);size=1024
image=Image.new('RGB',(size,size));rough=Image.new('RGB',(size,size));metal=Image.new('RGB',(size,size),(199,199,199))
d=ImageDraw.Draw(image);rd=ImageDraw.Draw(rough)
for y in range(size):
    value=194+rng.choice([-2,-1,0,0,0,1,2]);r=100+rng.choice([-5,-3,-1,0,0,2,4])
    d.line((0,y,size,y),fill=(value,value+1,value+2))
    rd.line((0,y,size,y),fill=(r,r,r))
for _ in range(360):
    y=rng.randrange(size);x=rng.randrange(size);length=rng.randrange(50,360)
    d.line((x,y,min(size,x+length),y),fill=(192,194,196))
# Small original identity, flush with the surface through the colour texture.
ink=(48,58,67);cx,cy=425,512
d.line([(cx-17,cy-23),(cx+17,cy-23),(cx+16,cy+3),(cx,cy+23),(cx-16,cy+3),(cx-17,cy-23)],fill=ink,width=2)
d.ellipse((cx-4,cy-5,cx+4,cy+3),fill=ink);d.polygon([(cx-2,cy+1),(cx+2,cy+1),(cx+3,cy+10),(cx-3,cy+10)],fill=ink)
font=ImageFont.truetype(str(FONT),36)
try:font.set_variation_by_axes([450])
except (OSError,AttributeError):pass
d.text((cx+31,cy),'中技安全',font=font,fill=ink,anchor='lm',stroke_width=0)
md=ImageDraw.Draw(metal)
md.line([(cx-17,cy-23),(cx+17,cy-23),(cx+16,cy+3),(cx,cy+23),(cx-16,cy+3),(cx-17,cy-23)],fill=(5,5,5),width=2)
md.ellipse((cx-4,cy-5,cx+4,cy+3),fill=(5,5,5));md.polygon([(cx-2,cy+1),(cx+2,cy+1),(cx+3,cy+10),(cx-3,cy+10)],fill=(5,5,5))
md.text((cx+31,cy),'中技安全',font=font,fill=(5,5,5),anchor='lm',stroke_width=0)
metal.save(OUT/'brushed_metallic.png',optimize=True)
Image.merge('RGB',(Image.new('L',(size,size),255),rough.getchannel('G'),metal.getchannel('B'))).save(OUT/'brushed_orm.png',optimize=True)
image.save(OUT/'brushed_silver.png',optimize=True)
rough.save(OUT/'brushed_roughness.png',optimize=True)
print(OUT)
