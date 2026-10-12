"""Inspect wing registration against original Swordman neck anchors."""
from pathlib import Path
import sys
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'Outputs/angel-clan-swordman-20260908'
sys.path[:0] = [str(ART/'production-v02'), str(ROOT/'tools/dual_weapon_formats')]
from sprite_formats import read_spr, read_act, anchor
from spr_reader import Spr
from rebuild_angel_pose_collars import rebuild_pose_collars
from bake_clan_body_frames import composite

OUT = ROOT/'Outputs/clan-body-skins/wing-attachment-v9'


def load(sex, include_masks=False):
    source = ART/('production-v06-corrections/sprites/male/angel_swordman_male_DETAIL_V06' if sex=='male' else 'female-wing-repair-v08/sprites/angel_swordman_female_WING_V08')
    images = read_spr(source.with_suffix('.spr').read_bytes())
    act = read_act(source.with_suffix('.act').read_bytes())
    native = Spr((ART/f'production-v02/source/{sex}-body.spr').read_bytes())
    native_act = read_act((ART/f'production-v02/source/{sex}-body.act').read_bytes())
    heads_dir = ROOT/'Outputs/clan-body-skins/original-job-audit'
    heads = Spr((heads_dir/f'{sex}-head.spr').read_bytes())
    ha = read_act((heads_dir/f'{sex}-head.act').read_bytes())
    images, masks, _ = rebuild_pose_collars(images,native,native_act,heads,ha,sex)
    return (images, act, native, heads, ha, masks) if include_masks else (images, act, native, heads, ha)


def draw_body(images, frame, size=(240,280), zoom=3):
    merged,x,y = composite(images,frame)
    view = merged.resize((round(merged.width*zoom/4),round(merged.height*zoom/4)),Image.Resampling.NEAREST)
    canvas = Image.new('RGBA',size)
    origin = (size[0]//2,size[1]-35)
    canvas.alpha_composite(view,(origin[0]+x*zoom-view.width//2,origin[1]+y*zoom-view.height//2))
    return canvas


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    reports = {}
    for sex in ('male','female'):
        images,act,native,_,_ = load(sex)
        count = len(native.images)
        atlas = Image.new('RGB',(1100,560),'#364451')
        pen = ImageDraw.Draw(atlas)
        for slot in range(count,len(images)):
            im=images[slot]; col=(slot-count)%6;row=(slot-count)//6
            pen.text((col*180+5,row*280+8),f'{sex} slot {slot} / {im.width}x{im.height}',fill='white')
            atlas.paste(im,(col*180+20,row*280+35),im)
        atlas.save(OUT/f'{sex}-wing-slots.png')
        board = Image.new('RGB',(8*180,8*250),'#364451')
        pen = ImageDraw.Draw(board)
        rows=[]
        for direction in range(8):
            frames=act.actions[8+direction]
            for fi,frame in enumerate(frames):
                tile=draw_body(images,frame,(180,250),3)
                board.paste(tile,(fi*180,direction*250),tile)
                bx,by=anchor(frame)
                wing=next(l for l in frame.layers if count<=l.index<count+9 or l.index==count+10)
                body=next(l for l in frame.layers if 0<=l.index<count)
                row=dict(action=8+direction,frame=fi,body=body.index,anchor=[bx,by],wing=vars(wing),wing_center_from_neck=[wing.x-bx,wing.y-by])
                rows.append(row)
                pen.text((fi*180+5,direction*250+5),f'A{8+direction} F{fi} B{body.index} W{wing.index}',fill='white')
        board.save(OUT/f'{sex}-walk-before.png')
        reports[sex]=rows
        print(sex)
        for ai in (0,1,2,3,4,8,9,10,11,12):
            print(ai,[(fi,anchor(f),[(l.index,l.x,l.y,l.mirror,l.angle) for l in f.layers]) for fi,f in enumerate(act.actions[ai])])
    (OUT/'original-walk-registration.json').write_text(json.dumps(reports,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
