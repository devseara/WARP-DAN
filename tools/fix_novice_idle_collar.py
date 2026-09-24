"""Correct only the male idle collar's registration, preserving accepted v4 movement."""
from pathlib import Path
import copy,json,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import novice_hd_common as b
ROOT=b.ROOT;WORK=ROOT/'Assets/HDNovice/idle-collar-v5';DIRECTIONS=[0,1,2,6,7]

def baseline(sex):
 return b.decode_spr((WORK/f'baseline/{sex}/body.spr').read_bytes())[0],b.read_act((WORK/f'baseline/{sex}/body.act').read_bytes())

def falloff(distance,inner,outer):
 t=np.clip((distance-inner)/(outer-inner),0,1);return (1+np.cos(np.pi*t))/2

def move_collar(im,source,target):
 # Only vertical sampling changes. The horizontal coordinate is exactly identity,
 # so shoulder/body widths cannot be narrowed by this registration adjustment.
 assert source[0]==target[0];cx,cy=target;shift=target[1]-source[1]
 yy,xx=np.mgrid[:im.height,:im.width]
 weight=falloff(np.abs(xx-cx),10,18)*falloff(np.abs(yy-cy),8,20)
 mapped_y=yy-shift*weight;jac=np.gradient(mapped_y,axis=0);assert jac.min()>.45
 old=np.array(im);a=old.astype(float);a[:,:,:3]*=a[:,:,3:4]/255
 y=np.clip(mapped_y,0,im.height-1);iy=y.astype(int);ny=np.minimum(iy+1,im.height-1);f=(y-iy)[:,:,None]
 out=a[iy,xx]*(1-f)+a[ny,xx]*f
 out[:,:,:3]=np.divide(out[:,:,:3]*255,out[:,:,3:4],out=np.zeros_like(out[:,:,:3]),where=out[:,:,3:4]>0)
 result=np.clip(np.rint(out),0,255).astype(np.uint8);result[weight==0]=old[weight==0];result[result[:,:,3]==0,:3]=0
 assert np.array_equal(result[weight==0],old[weight==0]);assert np.array_equal(result[80:],old[80:]);assert np.array_equal(result[:, :cx-18],old[:, :cx-18]);assert np.array_equal(result[:,cx+19:],old[:,cx+19:])
 assert np.array_equal(result[target[1],target[0]],old[source[1],source[0]])
 return Image.fromarray(result),Image.fromarray(np.rint(weight*255).astype(np.uint8)),dict(source=source,target=target,vertical_shift_hd=shift,minimum_vertical_jacobian=float(jac.min()),horizontal_coordinates_identical=True,outside_support_pixels_identical=True,below_y80_pixels_identical=True,landmark_pixel_identical=True,support=[cx-18,cy-20,cx+19,cy+21])

def paint():
 ims,act=baseline('male');outdir=WORK/'idle/male';outdir.mkdir(parents=True,exist_ok=True);proof=[]
 for direction,source,target in [(0,[104,54],[104,58]),(1,[99,56],[99,59]),(2,[97,55],[97,58])]:
  im=b.rendered_export(ims,act.actions[direction][0]);out,mask,p=move_collar(im,source,target);file=outdir/f'{direction}.png';out.save(file);mask.save(outdir/f'{direction}-support.png');proof.append(dict(direction=direction,source_render_sha256=b.sha(im.tobytes()),result_sha256=b.sha(file.read_bytes()),**p))
 for row in b.load(WORK/'mirror-registration.json'):
  source,target=row['source'],row['target'];im=Image.open(outdir/f'{source}.png').convert('RGBA').transpose(Image.Transpose.FLIP_LEFT_RIGHT);out=Image.new('RGBA',im.size);out.alpha_composite(im,tuple(row['mirror_translation']));file=outdir/f'{target}.png';out.save(file)
  proof.append(dict(direction=target,mirror_of=source,translation=row['mirror_translation'],mirrored_baseline_pixel_identical=True,result_sha256=b.sha(file.read_bytes())))
 b.save(WORK/'collar-corrections.json',proof);print(json.dumps(proof))

def preview():
 ims,act=baseline('male');out=Image.new('RGB',(1248,len(DIRECTIONS)*480),'#263340');d=ImageDraw.Draw(out)
 for row,direction in enumerate(DIRECTIONS):
  for col,(name,ai,im) in enumerate([('V4 idle',direction,b.rendered_export(ims,act.actions[direction][0])),('V5 idle',direction,Image.open(WORK/f'idle/male/{direction}.png').convert('RGBA')),('V4 walking F1',direction+8,b.rendered_export(ims,act.actions[direction+8][0]))]):
   im.alpha_composite(b.native_head('male',ai,0));im=im.resize((416,448),Image.Resampling.NEAREST);out.paste(im,(col*416,row*480+25),im);d.text((col*416+8,row*480+4),f'Direction {direction}: {name}',fill='white')
 out.save(WORK/'idle-collar-comparison.png')



def build():
 pins=b.load(WORK/'baseline.json')['baseline'];files=[];coverage=[];frame_checks=[];proof=b.load(WORK/'collar-corrections.json');marks={r['direction']:r for r in proof};outdir=WORK/'assets';outdir.mkdir(exist_ok=True)
 for sex in ['male','female']:
  old,oa=baseline(sex);images=[im.copy() for im in old];act=copy.deepcopy(oa);_,native,_,_=b.context(sex);changed=0
  for pin in pins:
   if ('/남/' in pin['entry'])==(sex=='male'):assert b.sha((WORK/f'baseline/{sex}/body{Path(pin["entry"]).suffix}').read_bytes())==pin['sha256']
  if sex=='male':
   for direction in DIRECTIONS:
    path=WORK/f'idle/male/{direction}.png';assert b.sha(path.read_bytes())==marks[direction]['result_sha256'];canonical=Image.open(path).convert('RGBA');before=b.rendered_export(old,oa.actions[direction][0]);first=native.actions[direction][0].layers[0];dedup={}
    for fi,f in enumerate(act.actions[direction]):
     l=native.actions[direction][fi].layers[0];delta=(2*(l.x-first.x),2*(l.y-first.y));check=Image.new('RGBA',before.size);check.alpha_composite(before,delta);assert check.tobytes()==b.rendered_export(old,oa.actions[direction][fi]).tobytes()
     expected=Image.new('RGBA',canonical.size);expected.alpha_composite(canonical,delta);sprite,x,y=b.bake(expected);key=(sprite.size,b.sha(sprite.tobytes()))
     if key not in dedup:dedup[key]=len(images);images.append(sprite)
     f.layers=[b.Layer(x,y,dedup[key],sx=.5,sy=.5)];assert b.rendered_export(images,f).tobytes()==expected.tobytes()
   sb,ab=b.write_spr(images),b.write_act(act)
  else:sb=(WORK/'baseline/female/body.spr').read_bytes();ab=(WORK/'baseline/female/body.act').read_bytes()
  decoded=b.decode_spr(sb)[0];independent=b.Spr(sb);aa=b.read_act(ab)
  for im,other in zip(decoded,independent.images):
   x=np.frombuffer(other.pixels,np.uint8).reshape(other.height,other.width,4);assert im.tobytes()==x[::-1,:,[3,2,1,0]].copy().tobytes()
  contacts=[]
  for ai,fs in enumerate(aa.actions):
   for fi,f in enumerate(fs):
    before=b.rendered_export(old,oa.actions[ai][fi]);after=b.rendered_export(decoded,f);same=before.tobytes()==after.tobytes();selected=sex=='male' and ai in DIRECTIONS
    assert same!=selected,(sex,ai,fi,'Unexpected changed frame');assert (f.anchors,f.ranges,f.sound)==(native.actions[ai][fi].anchors,native.actions[ai][fi].ranges,native.actions[ai][fi].sound)
    if not selected:assert f==oa.actions[ai][fi],(sex,ai,fi,'Unchanged ACT frame differs')
    if selected:
     head=np.asarray(b.native_head(sex,ai,fi))[:,:,3]>128;mask=np.asarray(after)[:,:,3]>128;contact=int(np.count_nonzero(head&mask));assert contact>0,(ai,fi,'Lost collar/head connection');contacts.append(dict(action=ai,frame=fi,head_body_contact_pixels=contact))
     assert np.array_equal(np.asarray(before)[80:],np.asarray(after)[80:]),(ai,fi,'Lower body changed')
    changed+=not same;frame_checks.append(dict(sex=sex,action=ai,frame=fi,pixel_identical_to_v4=same,native_head_anchors_identical=True))
  assert aa.speeds==native.speeds and aa.tail==native.tail
  assert len(aa.actions)==104 and sum(map(len,aa.actions))==456
  for ext,raw in [('spr',sb),('act',ab)]:
   path=outdir/f'novice-{sex}-hd-2x-v5.{ext}';path.write_bytes(raw);files.append(dict(sex=sex,path=path.relative_to(WORK).as_posix(),sha256=b.sha(raw),bytes=len(raw)))
  coverage.append(dict(sex=sex,actions=104,frame_uses=456,changed_frames=changed,unchanged_frames=456-changed,native_metadata_preserved=True,independent_sprite_decode=True,reopened_render_pixel_identical=456,head_contact_review=contacts))
 b.save(WORK/'verification.json',dict(status='exports_verified_pending_visual_review',files=files,coverage=coverage,frames=frame_checks,native_head_anchors_preserved=912,walking_combat_and_female_unchanged=True,changes='Only male idle collar regions in directions 0,1,2,6,7; all other frames and ACT motion remain v4.',live_client_acceptance=False));print(json.dumps(dict(coverage=coverage,files=files)))

def review():
 b.WORK=WORK;b.REVISION='v5';old={sex:baseline(sex) for sex in ['male','female']};b.review(comparison_baseline=old,template_path=ROOT/'tools/novice_hd_idle_collar_review.html');preview();font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',11);dest=WORK/'grids';dest.mkdir(exist_ok=True);items=[]
 ims,native,_,_=b.context('male');new=b.decode_spr((WORK/'assets/novice-male-hd-2x-v5.spr').read_bytes())[0];act=b.read_act((WORK/'assets/novice-male-hd-2x-v5.act').read_bytes())
 for direction in DIRECTIONS:
  box=(72,34,136,82);cw,ch=432,336;out=Image.new('RGB',(cw*4,ch*2),'#263340');d=ImageDraw.Draw(out)
  rows=[('Native idle',direction,b.native_body(ims,native.actions[direction][0],2)),('V4 idle',direction,b.rendered_export(old['male'][0],old['male'][1].actions[direction][0])),('V5 idle',direction,b.rendered_export(new,act.actions[direction][0])),('V4 walking',8+direction,b.rendered_export(old['male'][0],old['male'][1].actions[8+direction][0]))]
  for col,(name,ai,body) in enumerate(rows):
   for row in range(2):
    image=body.copy()
    if row:image.alpha_composite(b.native_head('male',ai,0))
    image=image.crop(box).resize((384,288),Image.Resampling.NEAREST);x=col*cw+36;y=row*ch+32;out.paste(image,(x,y),image);d.text((col*cw+4,row*ch+2),name+(' + head' if row else ' body'),font=font,fill='white')
    for t in range(65):
     d.line((x+t*6,y,x+t*6,y+288),fill='#425565' if t%2==0 else '#304050')
     if t%4==0:d.text((x+t*6,y-16),str(t+72),font=font,fill='white')
    for t in range(49):
     d.line((x,y+t*6,x+384,y+t*6),fill='#425565' if t%2==0 else '#304050')
     if t%4==0:d.text((col*cw+4,y+t*6),str(t+34),font=font,fill='white')
  path=dest/f'male-idle-{direction}.png';out.save(path);items.append(dict(direction=direction,path=path.relative_to(WORK).as_posix()))
 # All idle head frames are shown before/after; full bodies keep foot registration visible.
 for direction in DIRECTIONS:
  out=Image.new('RGB',(624,476),'#263340');d=ImageDraw.Draw(out)
  for fi in range(3):
   for row,image in enumerate([b.rendered_export(old['male'][0],old['male'][1].actions[direction][fi]),b.rendered_export(new,act.actions[direction][fi])]):
    image.alpha_composite(b.native_head('male',direction,fi));out.paste(image,(fi*208,row*238+14),image);d.text((fi*208+4,row*238+1),f'D{direction} F{fi+1} '+['V4','V5'][row],fill='white')
  out.save(WORK/f'idle-sequence-{direction}.png')
 html='''<!doctype html><meta charset="utf-8"><title>Novice idle collar pixels</title><style>body{background:#17232e;color:#dbeaf3;font:15px Segoe UI;margin:24px}a{color:#8ddfc4}select,button{background:#263746;color:white;padding:8px;font:inherit;border:1px solid #708da1}img{display:block;image-rendering:pixelated;margin:20px 0;max-width:100%}</style><h1>Idle collar correction</h1><p>The male idle front collar moves down by two native pixels; the diagonal and side collars move down by one and a half native pixels. The head, body width, lower body and every walking/combat frame stay fixed. Female and rear idle views are unchanged.</p><p><a href="full-action-review.html">All-action comparison</a> · <a href="idle-walk-review.html">Idle versus walking</a> · <a href="verification.json">Verification</a></p><select id="direction"></select><img id="pixels"><img id="sequence"><script>const rows=__ITEMS__,s=document.querySelector('#direction');rows.forEach((r,i)=>s.add(new Option('Direction '+r.direction,i)));function draw(){const r=rows[+s.value];document.querySelector('#pixels').src=r.path;document.querySelector('#sequence').src='idle-sequence-'+r.direction+'.png'}s.onchange=draw;draw();</script>'''.replace('__ITEMS__',json.dumps(items));(WORK/'pixel-review.html').write_text(html,encoding='utf8');b.save(WORK/'pixel-review-index.json',items)



def transition_review():
 html=(WORK/'full-action-review.html').read_text(encoding='utf8');data=json.loads(html.split('const data=',1)[1].split(',labels=',1)[0])['male'][:16]
 template=(ROOT/'tools/novice_hd_idle_walk_review.html').read_text(encoding='utf8');(WORK/'idle-walk-review.html').write_text(template.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf8')

if __name__=='__main__':globals()[sys.argv[1]]()
