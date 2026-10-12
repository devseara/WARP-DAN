"""Extract real native wing SPR/ACT pairs and show every direction."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from audit_clan_wing_attachment import ROOT,ART,load
from grf_reader import GrfFile
from spr_reader import Spr
from sprite_formats import read_act
from catalog_clan_wing_references import OUT,ARCHIVE

FAMILIES=['천사날개','wing_of_angel_move','wings_of_michael','wings_of_raphael',
          'wings_of_raguel','c_wings_of_gabriel','우리엘의날개','c_valkyrie_wing',
          'c_seraphim_wing_tw','c_guardian_angelwing']
NAMES=['Angel Wings','Animated Angel Wings','Michael','Raphael','Raguel',
       'Gabriel','Uriel','Valkyrie','Seraphim','Guardian Angel']

def rgba(spr,index,kind):
    i=index if kind==0 else spr.n_indexed8+index
    img=spr.images[i]
    if img.is_indexed:return Image.frombytes('RGBA',(img.width,img.height),spr.get_rgba(index,kind)[0])
    a=np.frombuffer(img.pixels,np.uint8).reshape(img.height,img.width,4)
    return Image.fromarray(a[::-1,:,[3,2,1,0]].copy())

def draw_frame(spr,frame,zoom=1):
    pieces=[]
    for l in frame.layers:
        if l.index<0:continue
        im=rgba(spr,l.index,l.kind)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im=im.resize((max(1,round(im.width*l.sx*zoom)),max(1,round(im.height*l.sy*zoom))),Image.Resampling.NEAREST)
        if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
        pieces.append((im,round(l.x*zoom)-im.width//2,round(l.y*zoom)-im.height//2))
    left=min(x for _,x,_ in pieces);top=min(y for _,_,y in pieces)
    right=max(x+i.width for i,x,_ in pieces);bottom=max(y+i.height for i,_,y in pieces)
    canvas=Image.new('RGBA',(right-left,bottom-top))
    for im,x,y in pieces:canvas.alpha_composite(im,(x-left,y-top))
    return canvas,(left,top)

def main():
    OUT.mkdir(parents=True,exist_ok=True);grf=GrfFile(ARCHIVE);records=[]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    font_small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',11)
    pages=[]
    try:
        for n,(family,name) in enumerate(zip(FAMILIES,NAMES)):
            keys=[k for k in grf.entries if k.startswith(f'data/sprite/로브/{family}/') and k.endswith('.spr')]
            preferred=f'data/sprite/로브/{family}/남/검사_남.spr'
            key=preferred if preferred in keys else next((k for k in keys if k.endswith('/'+family+'.spr')),keys[0] if keys else None)
            if not key:continue
            data=grf.read(key);ad=grf.read(key[:-4]+'.act')
            if not ad:continue
            source=OUT/'source'/family;source.mkdir(parents=True,exist_ok=True)
            (source/'male.spr').write_bytes(data);(source/'male.act').write_bytes(ad)
            female_key=f'data/sprite/로브/{family}/여/검사_여.spr'
            if female_key in grf.entries:
                (source/'female.spr').write_bytes(grf.read(female_key));(source/'female.act').write_bytes(grf.read(female_key[:-4]+'.act'))
            spr=Spr(data);act=read_act(ad)
            if n%5==0:pages.append(Image.new('RGB',(1200,1100),'#283746'))
            board=pages[-1];pen=ImageDraw.Draw(board);y=n%5*220
            for d in range(5):
                f=act.actions[d][0];im,xy=draw_frame(spr,f,1)
                factor=min(2,210/max(im.width,im.height))
                im=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.NEAREST)
                board.paste(im,(d*240+(240-im.width)//2,y+35),im)
                pen.text((d*240+8,y+5),f'{name} / direction {d}',font=font,fill='white')
                pen.text((d*240+8,y+202),f'ACT sprites: '+str([(l.index,l.mirror) for l in f.layers if l.index>=0]),font=font_small,fill='#c6d7e6')
            sheet=Image.new('RGB',(1600,460),'#283746');p=ImageDraw.Draw(sheet)
            for d in range(8):
                im,xy=draw_frame(spr,act.actions[d][0],2)
                limit=min(1,180/im.width,360/im.height)
                im=im.resize((round(im.width*limit),round(im.height*limit)),Image.Resampling.NEAREST)
                sheet.paste(im,(d*200+(200-im.width)//2,60),im)
                p.text((d*200+8,10),f'{name} / {d}',font=font,fill='white')
                p.text((d*200+8,420),f'frame 0',font=font_small,fill='white')
            sheet.save(source/'eight-directions.png')
            record=dict(name=name,family=family,archive_path=key,spr_sha256=hashlib.sha256(data).hexdigest(),act_sha256=hashlib.sha256(ad).hexdigest(),
                        actions=len(act.actions),frames=sum(map(len,act.actions)),images=len(spr.images),
                        idle=[dict(direction=d,layers=[vars(l) for l in act.actions[d][0].layers]) for d in range(8)])
            records.append(record)
        for i,page in enumerate(pages):page.save(OUT/f'native-wing-catalog-{i+1}.png')
        (OUT/'native-wing-references.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf8')
        print(json.dumps([dict(name=r['name'],actions=r['actions'],frames=r['frames'],images=r['images'],path=r['archive_path']) for r in records],ensure_ascii=False))
    finally:grf.close()

if __name__=='__main__':main()
