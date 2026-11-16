# Mappa altitudine + batimetria (km) usata per simulare la migrazione degli oceani verso i poli.
# Terre: texture topografica; oceani: profondità stimata dalla distanza dalla costa. Scrive assets/textures/earth-height.png
import os, numpy as np
from PIL import Image
from scipy import ndimage
T=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','assets','textures')
topo=np.asarray(Image.open(os.path.join(T,'earth-topology.png')).convert('L').resize((2048,1024),Image.BILINEAR)).astype(np.float32)/255
wat=np.asarray(Image.open(os.path.join(T,'earth-water.png')).convert('L').resize((2048,1024),Image.BILINEAR)).astype(np.float32)/255>0.5
d=ndimage.distance_transform_edt(wat)
H=np.where(wat,-(0.15+5.2*(1-np.exp(-d/55.0))),np.clip(topo,0,1)**1.15*6.5)
H=ndimage.gaussian_filter(H,0.8)
Image.fromarray((np.clip((H+6.0)/15.0,0,1)*255).astype(np.uint8)).save(os.path.join(T,'earth-height.png'))
# Senza rotazione il livello del mare diventa S(lat) = A*(sin^2(lat) - 2/3), con A = 21 km (rigonfiamento equatoriale):
# -14 km all'equatore, +7 km ai poli -> oceani polari e un supercontinente equatoriale.
