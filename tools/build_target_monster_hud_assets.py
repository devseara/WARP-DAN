"""Extract the accepted HUD artwork at one uniform 50% scale, without redraw."""
from pathlib import Path
import json,hashlib,struct
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'Assets/TargetMonsterHUD/three-tier-concept.png'
RESOURCE='data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/uirenewal/mobhpbar';OUT=ROOT/RESOURCE;OUT.mkdir(parents=True,exist_ok=True)
W,H=768,232;SCALE=.5
TIERS=[
 ('normal',(430,187,1106,272),66,(600,66,936,113),[(480,211),(1057,211),(1046,230),(1057,247),(480,247),(489,230)],(501,211,704,248),(926,211,1030,248)),
 ('mini',(205,450,1334,590),348,(600,348,936,394),[(343,505),(1198,505),(1180,529),(1198,552),(343,552),(355,529)],(387,505,701,553),(982,505,1153,553)),
 ('mvp',(50,685,1490,947),650,(610,650,926,699),[(247,804),(1290,804),(1274,834),(1290,865),(247,865),(261,834)],(288,804,702,866),(1085,804,1242,866)),
]
im=Image.open(SOURCE).convert('RGB');manifest={'canvas':[W,H],'scale':SCALE,'name_top':28,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'pixel_format':'BGRA32','bmp_header':'BITMAPV4HEADER','alpha':'straight','pixel_offset':122,'resource_root':RESOURCE,'tiers':[]}
def key(image):
 a=np.asarray(image);out=a[:,:,:3].copy();out[a[:,:,3]<80]=(255,0,255);return Image.fromarray(out)
# Keep the native tier font. Only the separator is extracted separately:
# its one-pixel hairline must remain continuous even at the faint endpoints.
DIVIDERS={
 'normal':(606,98,924,112),
 'mini':(594,382,936,396),
 'mvp':(670,688,866,700),
}
def divider_sprite(tier):
 box=DIVIDERS[tier]
 rgb=np.asarray(im.crop(box).resize(((box[2]-box[0])//2,(box[3]-box[1])//2),Image.Resampling.LANCZOS))
 h,w=rgb.shape[:2];cx=round((766-box[0])*SCALE)
 rgba=np.zeros((h,w,4),np.uint8)
 # Estimate the original matte from blank rows above and below the rule.
 # Its contrast against that matte supplies the opacity, rather than baking
 # the olive backdrop into the faded endpoints.
 matte=(rgb[0].astype(float)+rgb[-1].astype(float))*.5
 matte=cv2.GaussianBlur(matte[None,:,:],(9,1),0)[0]
 center=np.asarray(im.crop((760,box[1],773,box[3]))).reshape(-1,3)
 gold=np.median(center[np.argsort(center[:,0])[-8:]],axis=0)
 direction=gold-matte
 opacity=np.clip(np.sum((rgb[3].astype(float)-matte)*direction,axis=1)/np.maximum(np.sum(direction*direction,axis=1),1),0,1)
 # Smooth each arm toward the center without joining the diamond's gaps.
 for indices in (np.arange(cx-4),np.arange(w-1,cx+3,-1)):
  values=opacity[indices]
  values=np.convolve(np.pad(values,(2,2),mode='edge'),np.array([1,2,3,2,1])/9,mode='valid')
  values=np.maximum.accumulate(np.maximum(values-values[0],0))
  rgba[3,indices,:3]=np.rint(gold).astype(np.uint8)
  rgba[3,indices,3]=np.rint(values*255).astype(np.uint8)
 signed=rgb.astype(np.int16);diamond=(signed[:,:,0]-signed[:,:,1]>2)&(signed[:,:,0]>140)
 for x in range(cx-4,cx+4):
  rgba[:,x,:3]=rgb[:,x];rgba[:,x,3]=diamond[:,x]*255
 rgba[rgba[:,:,3]==0]=0
 return Image.fromarray(rgba,'RGBA')

def save_bmp_alpha(image,path):
 # V4 explicitly declares all four masks; BI_RGB alone is ambiguous about
 # whether the fourth byte is padding. Store straight BGRA, bottom-up.
 width,height=image.size;pixels=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')
 header=struct.pack('<IiiHHIIiiII',108,width,height,1,32,3,len(pixels),2835,2835,0,0)
 header+=struct.pack('<IIIII',0x00ff0000,0x0000ff00,0x000000ff,0xff000000,0x73524742)+bytes(48)
 assert len(header)==108
 path.write_bytes(struct.pack('<2sIHHI',b'BM',122+len(pixels),0,0,122)+header+pixels)
 assert np.array_equal(np.asarray(Image.open(path).convert('RGBA')),np.asarray(image))

for tier,box,origin,labelbox,poly,redbox,darkbox in TIERS:
 arr=np.asarray(im.crop(box)).copy();h,w=arr.shape[:2];r,g,b=[arr[:,:,i].astype(np.int16) for i in range(3)]
 # Remove only the olive backdrop, retaining the original dark chrome edges.
 background=(np.abs(r-g)<=9)&(g-b>=9)&(np.max(arr,2)<170)
 alpha=np.where(background,0,255).astype(np.uint8)
 alpha[:2]=0;alpha[-2:]=0;alpha[:,:2]=0;alpha[:,-2:]=0
 if tier=='mvp':alpha[:88,250:1190]=0
 alpha=cv2.morphologyEx(alpha,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
 n,lab,stats,_=cv2.connectedComponentsWithStats(alpha);alpha=np.where(lab==1+int(np.argmax(stats[1:,4])),255,0).astype(np.uint8)
 contours,_=cv2.findContours(alpha,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(alpha,contours,-1,255,cv2.FILLED)
 art=Image.fromarray(np.dstack((arr,alpha)),'RGBA');fillmask=Image.new('L',(w,h))
 ImageDraw.Draw(fillmask).polygon([(x-box[0],y-box[1]) for x,y in poly],fill=255)
 art.putalpha(Image.fromarray(np.maximum(np.asarray(art.getchannel('A')),np.asarray(fillmask))))
 x0,y0,x1,y1=fillmask.getbbox();dx=round(box[0]*SCALE);dy=round((box[1]-origin)*SCALE)
 # Labels, flourishes and rules are copied from the accepted reference itself.
 label=np.asarray(im.crop(labelbox));lr,lg,lb=[label[:,:,i].astype(int) for i in range(3)]
 la=np.where((lr-lg>3)&(lr>125),255,0).astype(np.uint8)
 # Preserve original flourishes/rules, replace damaged baked lettering natively.
 tx0,ty0,tx1,ty1={'normal':(698,73,829,97),'mini':(680,358,839,382),'mvp':(723,663,800,689)}[tier]
 la[ty0-labelbox[1]:ty1-labelbox[1],tx0-labelbox[0]:tx1-labelbox[0]]=0
 label=Image.fromarray(np.dstack((label,la)),'RGBA')
 label=key(label.resize((round(label.width*SCALE),round(label.height*SCALE)),Image.Resampling.LANCZOS))
 divider_box=DIVIDERS[tier]
 # Erase only the previous damaged divider; flourishes and native text stay.
 ImageDraw.Draw(label).rectangle((0,round((divider_box[1]-labelbox[1])*SCALE),label.width,label.height),fill=(255,0,255))
 divider=divider_sprite(tier)
 # Preserve the original red pattern at its original scale. Remove only the
 # baked percentage, then mirror-extend the unpictured right-hand portion.
 red_end={'normal':891,'mini':918,'mvp':963}[tier]
 red_source=np.asarray(im.crop((x0+box[0],y0+box[1],red_end,y1+box[1]))).copy()
 # The reference's centered lettering overlaps the crest in this rectangular
 # sample. Replace its full-height column with clean source texture, including
 # boundary pixels, so mirror-extension cannot reproduce gold/black notches.
 px0=max(0,720-(x0+box[0]));px1=min(red_source.shape[1],823-(x0+box[0]))
 clean=np.asarray(im.crop((redbox[0],y0+box[1],redbox[0]+px1-px0,y1+box[1]))).copy()
 weights=np.ones((1,px1-px0,1),np.float32)
 edge=min(10,(px1-px0)//3)
 weights[0,:edge,0]=np.linspace(0,1,edge)
 weights[0,-edge:,0]=np.linspace(1,0,edge)
 red_source[:,px0:px1]=np.rint(clean*weights+red_source[:,px0:px1]*(1-weights)).astype(np.uint8)
 red_source=Image.fromarray(red_source)
 def tiled(sample,target_width,target_height):
  if sample.height!=target_height:sample=sample.resize((sample.width,target_height),Image.Resampling.LANCZOS)
  target=Image.new('RGB',(target_width,target_height));x=0;index=0
  while x<target_width:
   tile=sample if index%2==0 else sample.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
   target.paste(tile,(x,0));x+=sample.width;index+=1
  return target
 variants=[]
 for mode,sample in [('empty',darkbox),('full',redbox)]:
  painted=art.copy();texture=tiled(red_source if mode=='full' else im.crop(sample),x1-x0,y1-y0)
  layer=Image.new('RGBA',(w,h));layer.paste(texture,(x0,y0));painted.paste(layer,(0,0),fillmask)
  canvas=Image.new('RGB',(W,H),(255,0,255))
  canvas.paste(key(painted.resize((round(w*SCALE),round(h*SCALE)),Image.Resampling.LANCZOS)),(dx,dy))
  canvas.paste(label,(round(labelbox[0]*SCALE),round((labelbox[1]-origin)*SCALE)))
  # Preserve all accepted opaque artwork; only the divider gets partial alpha.
  pixels=np.asarray(canvas);a=np.where(np.all(pixels==(255,0,255),2),0,255).astype(np.uint8)
  rgba=np.dstack((pixels,a));rgba[a==0]=0;canvas=Image.fromarray(rgba,'RGBA')
  canvas.paste(divider,(round(divider_box[0]*SCALE),round((divider_box[1]-origin)*SCALE)))
  filename=f'target_mob_{tier}_{mode}.bmp';save_bmp_alpha(canvas,OUT/filename);variants.append(canvas)
 yy,xx=np.where(np.any(np.asarray(variants[0])!=np.asarray(variants[1]),2));clip=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
 pcttop=round(((y0+y1)/2+box[1]-origin)*SCALE)-7
 manifest['tiers'].append({'name':tier,'label':{'normal':'NORMAL','mini':'MINI BOSS','mvp':'MVP'}[tier],'empty':f'target_mob_{tier}_empty.bmp','full':f'target_mob_{tier}_full.bmp','fill':clip,'percent_top':pcttop,'label_top':{'normal':2,'mini':3,'mvp':5}[tier],'divider_source_crop':list(divider_box),'divider_bounds':[round(divider_box[0]*SCALE),round((divider_box[1]-origin)*SCALE),round(divider_box[2]*SCALE),round((divider_box[3]-origin)*SCALE)]})
(ROOT/'Assets/TargetMonsterHUD/assets.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(f'Wrote six {W}x{H} alpha BMPs to {OUT}')
