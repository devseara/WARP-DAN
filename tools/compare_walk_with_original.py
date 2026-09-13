"""Always compare the custom walk with the original Swordman SPR/ACT."""
import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

from review_original_job_directions import native_context,OUT
from sprite_formats import read_spr,read_act,anchor
from render_native_wing_anatomy import rgba
from render_clan_all_action_review import render
from sprite_review_animation import save_review_animation

WORK=OUT/'walking-native-reference-v3'


def render_native(sex,ai,fi):
    _,spr,act,heads,ha=native_context('swordman',sex)
    frame=act.actions[ai][fi];canvas=Image.new('RGBA',(300,300));origin=(150,245)
    for layer in frame.layers:
        if layer.index<0:continue
        im=rgba(spr,layer.index,layer.kind)
        if layer.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        assert layer.sx==layer.sy==1 and layer.angle==0
        pos=(origin[0]+(layer.x-im.width//2)*2,origin[1]+(layer.y-im.height//2)*2)
        canvas.alpha_composite(im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST),pos)
    hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
    bx,by=anchor(frame);hx,hy=anchor(hf)
    for layer in hf.layers:
        if layer.index<0:continue
        im=rgba(heads,layer.index,layer.kind)
        if layer.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        canvas.alpha_composite(im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST),
            (origin[0]+(layer.x+bx-hx)*2-im.width,origin[1]+(layer.y+by-hy)*2-im.height))
    return canvas


def compare(candidate,tag):
    WORK.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
    data={sex:(read_spr((candidate/f'assets/{sex}-world.spr').read_bytes()),
               read_act((candidate/f'assets/{sex}-world.act').read_bytes())) for sex in ('male','female')}
    movie=[]
    for d in range(8):
        for repeat in range(2):
            for fi in range(8):
                board=Image.new('RGB',(1000,335),'#283746');p=ImageDraw.Draw(board)
                for row,sex in enumerate(('male','female')):
                    _,_,_,heads,ha=native_context('swordman',sex)
                    native=render_native(sex,8+d,fi)
                    custom=render(*data[sex],heads,ha,8+d,fi)
                    for revision,(image,label) in enumerate(((native,'Original Swordman'),(custom,tag))):
                        column=row*2+revision
                        image=image.crop((25,0,275,300))
                        board.paste(image,(column*250,18),image)
                        p.text((column*250+7,3),sex.title()+' / '+label,font=font,fill='white')
                p.text((8,315),f'Same native action {8+d}, frame {fi} / synchronized comparison',font=font,fill='white')
                movie.append(board)
                if repeat==0 and fi in (0,2,4,6):board.save(WORK/f'{tag}-d{d}-f{fi}.png')
    save_review_animation(movie,WORK/f'original-vs-{tag}.gif',110)
    return WORK/f'original-vs-{tag}.gif'


def guides():
    WORK.mkdir(exist_ok=True)
    for sex in ('male','female'):
        _,spr,act,_,_=native_context('swordman',sex)
        for d in range(5):
            board=Image.new('RGB',(1040,820),'#283746');p=ImageDraw.Draw(board)
            for fi,frame in enumerate(act.actions[8+d]):
                col=fi%4;row=fi//4;ox=col*260+130;oy=row*410+315
                for x in range(-25,26,5):
                    p.line((ox+x*4,row*410+22,ox+x*4,row*410+390),fill='#405365')
                    p.text((ox+x*4,row*410+392),str(x),fill='white')
                for y in range(-70,16,5):
                    p.line((col*260,oy+y*4,(col+1)*260,oy+y*4),fill='#405365')
                    p.text((col*260+2,oy+y*4),str(y),fill='white')
                l=frame.layers[0];im=rgba(spr,l.index,l.kind)
                board.paste(im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST),
                    (ox+(l.x-im.width//2)*4,oy+(l.y-im.height//2)*4),
                    im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST))
                p.text((col*260+8,row*410+4),f'{sex} D{d} F{fi} native SPR {l.index}',fill='white')
            board.save(WORK/f'{sex}-d{d}-native-poses.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',type=Path,
        default=OUT/'walking-pilot-v1');parser.add_argument('--tag',default='rejected-v2')
    args=parser.parse_args();guides();print(compare(args.candidate,args.tag))
