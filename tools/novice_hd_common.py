"""Native registration, codecs and review helpers for the accepted Novice workflow."""
from pathlib import Path
from functools import lru_cache
import hashlib,json,math,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/dual_weapon_formats'))
from hd_job_ui_assets import read_spr as decode_spr
from sprite_formats import read_act,write_act,write_spr,Layer,anchor
from spr_reader import Spr
WORK=ROOT/'Assets/HDNovice/idle-collar-v5'
REVISION='v5'
STANDING=ROOT/'Assets/HDNovice/standing-v1'
SEXES=['male','female']
CANVAS=(416,448)
ORIGIN=(208,328)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def load(p):return json.loads(Path(p).read_text(encoding='utf8'))


def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')


@lru_cache(maxsize=2)
def context(sex):
 p=STANDING/'native'/sex
 ims,ni,pal=decode_spr((p/'body.spr').read_bytes());a=read_act((p/'body.act').read_bytes())
 heads,hn,_=decode_spr((p/'head.spr').read_bytes());ha=read_act((p/'head.act').read_bytes())
 return [im.convert('RGBA') for im in ims],a,[im.convert('RGBA') for im in heads],ha


def native_body(ims,frame,zoom=4):
 c=Image.new('RGBA',(CANVAS[0]*zoom//4,CANVAS[1]*zoom//4));origin=np.array(ORIGIN)*zoom//4
 for l in frame.layers:
  if l.index<0:continue
  im=ims[l.index];assert l.kind==0 and l.sx==l.sy==1 and l.angle==0
  if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
  xy=origin+np.array([l.x-im.width//2,l.y-im.height//2])*zoom
  c.alpha_composite(im.resize((im.width*zoom,im.height*zoom),Image.Resampling.NEAREST),tuple(xy.tolist()))
 return c


def native_head(sex,ai,fi,zoom=2,pad=0):
 ims,a,heads,ha=context(sex);frame=a.actions[ai][fi];hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
 bx,by=anchor(frame);hx,hy=anchor(hf)
 c=Image.new('RGBA',(CANVAS[0]*zoom//4+2*pad,CANVAS[1]*zoom//4+2*pad));ox,oy=np.array(ORIGIN)*zoom//4+pad
 for l in hf.layers:
  if l.index<0:continue
  im=heads[l.index]
  if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
  im=im.resize((im.width*zoom,im.height*zoom),Image.Resampling.NEAREST)
  if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
  c.alpha_composite(im,(int(ox+(l.x+bx-hx)*zoom-im.width//2),int(oy+(l.y+by-hy)*zoom-im.height//2)))
 return c


def bake(image):
 b=image.getbbox();assert b
 x,y=(b[0]//2)*2,(b[1]//2)*2
 w=math.ceil((b[2]-x)/4)*4;h=math.ceil((b[3]-y)/4)*4
 crop=image.crop((x,y,x+w,y+h))
 lx=(x+w//2-ORIGIN[0]//2)//2;ly=(y+h//2-ORIGIN[1]//2)//2
 assert ORIGIN[0]//2+2*lx-w//2==x and ORIGIN[1]//2+2*ly-h//2==y
 return crop,lx,ly


def rendered_export(images,frame):
 c=Image.new('RGBA',(CANVAS[0]//2,CANVAS[1]//2))
 for l in frame.layers:
  assert l.kind==1 and l.sx==l.sy==.5 and not l.mirror and not l.angle
  im=images[l.index];c.alpha_composite(im,(ORIGIN[0]//2+l.x*2-im.width//2,ORIGIN[1]//2+l.y*2-im.height//2))
 return c


def review(comparison_baseline, template_path):
 import io
 from sprite_review_animation import save_review_animation
 out=WORK/'review/images';out.mkdir(parents=True,exist_ok=True);data={};coverage=[]
 def put(im):
  buf=io.BytesIO();im.save(buf,format='PNG');raw=buf.getvalue();p=out/(sha(raw)+'.png')
  if not p.exists():p.write_bytes(raw)
  return p.relative_to(WORK).as_posix()
 for sex in SEXES:
  ims,native,_,_=context(sex);hd,_,_=decode_spr((WORK/'assets'/f'novice-{sex}-hd-2x-{REVISION}.spr').read_bytes());act=read_act((WORK/'assets'/f'novice-{sex}-hd-2x-{REVISION}.act').read_bytes())
  data[sex]=[]
  for ai,frames in enumerate(act.actions):
   rows=[];sequence=[]
   for fi,f in enumerate(frames):
    original=native_body(ims,native.actions[ai][fi],2);new=rendered_export(hd,f);head=native_head(sex,ai,fi,pad=64)
    hm=np.asarray(head)[:,:,3];assert not np.any(hm[[0,-1],:]) and not np.any(hm[:,[0,-1]]),(sex,ai,fi,'Head review clips')
    bodies=[]
    compare_bodies=[original,new] if comparison_baseline is None else [original,rendered_export(comparison_baseline[sex][0],comparison_baseline[sex][1].actions[ai][fi]),new]
    for body in compare_bodies:
     c=Image.new('RGBA',(336,352));c.alpha_composite(body,(64,64));bodies.append(c)
    rows.append([put(body) for body in bodies]+[put(head)])
    if ai in [8,9,10,11,12,32,40,80,88]:
     canvas=Image.new('RGB',(416,224),'#273442')
     for side,body in enumerate([original,new]):
      body=body.copy();body.alpha_composite(native_head(sex,ai,fi));canvas.paste(body,(side*208,0),body)
     sequence.append(canvas)
   data[sex].append(dict(action=ai,ms=round(native.speeds[ai]*25),frames=rows))
   if sequence:
    folder=WORK/'review/loops';folder.mkdir(exist_ok=True)
    packed=[];durations=[];ms=round(native.speeds[ai]*25)
    for image in sequence:
     if packed and image.tobytes()==packed[-1].tobytes():durations[-1]+=ms
     else:packed.append(image);durations.append(ms)
    save_review_animation(packed,folder/f'{sex}-a{ai}.gif',durations,apng=folder/f'{sex}-a{ai}.png')
    with Image.open(folder/f'{sex}-a{ai}.png') as decoded:
     total=0
     for idx in range(decoded.n_frames):decoded.seek(idx);total+=decoded.info['duration']
     assert abs(total-ms*len(sequence))<.01,'Preview hold timing changed'
    strip=Image.new('RGB',(208*len(sequence),472),'#273442');pen=ImageDraw.Draw(strip)
    for fi,c in enumerate(sequence):
     strip.paste(c.crop((0,0,208,224)),(fi*208,24));strip.paste(c.crop((208,0,416,224)),(fi*208,248));pen.text((fi*208+5,5),f'{sex} A{ai} F{fi} | top native / bottom HD',fill='white')
    strip.save(folder/f'{sex}-a{ai}-strip.png')
  coverage.append(dict(sex=sex,actions=len(data[sex]),frame_uses=sum(len(a['frames']) for a in data[sex]),reopened_exports=True))
 html=Path(template_path).read_text(encoding='utf8').replace('-v1.',f'-{REVISION}.').replace('__DATA__',json.dumps(data,separators=(',',':')))
 (WORK/'full-action-review.html').write_text(html,encoding='utf8')
 save(WORK/'review-coverage.json',dict(coverage=coverage,body_and_head_origins_shared=True,unique_pngs=len(list(out.glob('*.png'))),lossless_animation_reopen_verified=True))
 print(json.dumps(dict(coverage=coverage,review=str(WORK/'full-action-review.html'))))


def write_documentation_pointer(work):
    """Keep generated artifact directories linked to the one maintained guide."""
    from os.path import relpath
    work = Path(work).resolve()
    guide = ROOT / 'docs/novice-hd-sprites.md'
    assert work.is_relative_to(ROOT.resolve()) and guide.is_file()
    link = Path(relpath(guide, work)).as_posix()
    (work / 'README.md').write_text(
        '# Novice HD sprites\n\n'
        'This directory is a versioned artifact snapshot. Current acceptance, history,\n'
        'rebuild, GRF deployment and recovery instructions are maintained only in\n'
        f'[Novice HD sprites]({link}).\n', encoding='utf8')
