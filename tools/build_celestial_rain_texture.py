"""Generate the prototype's private additive rain streak; shared textures stay intact."""
from pathlib import Path
import hashlib
from PIL import Image
import math
ROOT=Path(__file__).resolve().parents[1]
im=Image.new('RGB',(32,128))
for y in range(12,116):
    fade=(min(y-11,116-y)*255)//52
    for x in range(13,19):
        # A fine neutral streak with a dim edge; the native emitter supplies motion.
        value=fade*([15,55,150,150,55,15][x-13])//255
        im.putpixel((x,y),(value,value,min(255,value+value//12)))
path=ROOT/'Inputs/CelestialDial/boh_rain_prototype.bmp'
im.save(path)
print(path,hashlib.sha256(path.read_bytes()).hexdigest())
for name in ['boh_rain_ripple.bmp','boh_rain_wet.bmp']:
    im=Image.new('RGB',(128,128))
    for y in range(128):
        for x in range(128):
            nx=(x-63.5)/63.5;ny=(y-63.5)/63.5;r=math.hypot(nx,ny)
            if name=='boh_rain_ripple.bmp':
                edge=math.exp(-((r-.72)/.028)**2)
                inner=.35*math.exp(-((r-.47)/.025)**2)
                value=int(220*min(1,edge+inner))
            else:
                # Diffuse overlapping lobes create a soft irregular reflection.
                # No narrow center stripe, hard outline, or repeating S curve.
                radius=math.hypot(nx*.88,ny*1.12)
                boundary=.80+.045*math.sin(nx*5+ny*3)+.035*math.cos(ny*6-nx*4)
                mask=max(0,min(1,(boundary-radius)*3.2))
                lobe=math.exp(-(((nx+.24)/.63)**2+((ny+.18)/.40)**2))
                secondary=math.exp(-(((nx-.30)/.40)**2+((ny-.22)/.52)**2))
                grain=.5+.5*math.sin(nx*7+ny*5)*math.cos(ny*8-nx*3)
                value=int(mask*(10+43*lobe+19*secondary+4*grain))
            im.putpixel((x,y),(value,value,value))
    path=ROOT/'Inputs/CelestialDial'/name;im.save(path)
    print(path,hashlib.sha256(path.read_bytes()).hexdigest())
