import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# sfondo: fotogramma pulito (senza scritte) a 26,3 s, salvato in cover/c_26.30.png
bg=Image.open('cover/c_26.30.png').convert('RGB')
bg=ImageEnhance.Contrast(bg).enhance(1.12); bg=ImageEnhance.Color(bg).enhance(1.1)
W,H=bg.size
# darken top for legibility
grad=Image.new('L',(W,H),0); g=ImageDraw.Draw(grad)
for y in range(H): g.line([(0,y),(W,y)],fill=int(185*min(1,max(0,(y-900)/700))))
bg=Image.composite(Image.new('RGB',(W,H),(0,0,0)),bg,grad)
BLACK='/usr/share/fonts/opentype/inter/Inter-Black.otf'
try: ImageFont.truetype(BLACK,10)
except Exception: BLACK='/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
MONO='/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf'
def font(p,s):
    try: return ImageFont.truetype(p,s)
    except Exception: return ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf',s)
d=ImageDraw.Draw(bg)
def centered(y,text,size,fill=(255,255,255),box=None):
    f=font(BLACK,size); w=d.textlength(text,font=f); x=(W-w)/2
    if box:
        pad=22; bb=d.textbbox((x,y),text,font=f); d.rounded_rectangle([bb[0]-pad,bb[1]-pad*0.6,bb[2]+pad,bb[3]+pad*0.6],radius=18,fill=box)
        d.text((x,y),text,font=f,fill=(17,17,17))
    else:
        d.text((x,y),text,font=f,fill=fill,stroke_width=14,stroke_fill=(0,0,0))
lang=sys.argv[1]
if lang=='it':
    centered(1190,'E SE LA TERRA',118); centered(1340,'SI FERMASSE?',124,box=(255,214,10))
    tag='WHAT IF · EP. 04'; out='cover_it.jpg'

f=font(MONO,34); w=d.textlength(tag,font=f); d.rounded_rectangle([(W-w)/2-28,1060,(W+w)/2+28,1124],radius=32,outline=(255,255,255),width=4,fill=(0,0,0))
d.text(((W-w)/2,1070),tag,font=f,fill=(255,255,255))
bg.save(out,quality=94); print(out)
