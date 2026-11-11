import numpy as np
from PIL import Image, ImageFilter
W,H=4096,2048
rng=np.random.default_rng(3)
# Genera una Luna 4K con crateri procedurali a partire dalla texture 1K di three.js
import os; os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','assets','textures'))
base=Image.open('moon_1024.jpg').convert('L').resize((W,H),Image.LANCZOS)
col=np.asarray(base).astype(np.float32)/255
# height field: start from base luminance (low freq) as pseudo-height
hgt=np.asarray(base.filter(ImageFilter.GaussianBlur(6))).astype(np.float32)/255*0.5
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
def crater(cx,cy,r,depth):
    # equirect: stretch x by 1/cos(lat)
    lat=(cy/H-0.5)*np.pi; sx=max(1e-3,np.cos(lat))
    x0,x1=int(cx-r/sx*1.6),int(cx+r/sx*1.6); y0,y1=max(0,int(cy-r*1.6)),min(H,int(cy+r*1.6))
    if y1<=y0: return
    xs=np.arange(x0,x1)%W; ys=np.arange(y0,y1)
    dx=((np.arange(x0,x1)-cx)*sx)[None,:]; dy=(ys-cy)[:,None]
    d=np.sqrt(dx*dx+dy*dy)/r
    bowl=-depth*np.clip(1-d*d,0,1)**1.2              # depression
    rim=depth*0.55*np.exp(-((d-1.0)/0.18)**2)        # raised rim
    prof=bowl+rim
    hgt[np.ix_(ys,xs)]+=prof
    alb=1-0.12*depth*np.clip(1-d,0,1)+0.10*depth*np.exp(-((d-1.0)/0.25)**2)
    col[np.ix_(ys,xs)]*=alb
N=[(2600,6,22,0.35),(900,22,60,0.45),(220,60,160,0.5),(40,160,380,0.45)]
for n,r0,r1,dep in N:
    for _ in range(n):
        r=r0+(r1-r0)*rng.random()**2.2; cy=rng.random()*H; cx=rng.random()*W
        crater(cx,cy,r,dep*(0.6+0.8*rng.random()))
# fine noise
noise=rng.standard_normal((H//4,W//4)).astype(np.float32)
noise=np.asarray(Image.fromarray(noise).resize((W,H),Image.BICUBIC))
hgt+=noise*0.025
col*=1+noise*0.05
col=np.clip(col,0,1); hgt=hgt-hgt.min(); hgt/=hgt.max()
Image.fromarray((col*255).astype(np.uint8)).save('moon_color_4k.jpg',quality=92)
Image.fromarray((hgt*255).astype(np.uint8)).save('moon_bump_4k.jpg',quality=92)
print('ok')
