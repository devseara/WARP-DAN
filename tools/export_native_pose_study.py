"""Import the approved whole-pose male action-11 sheet into a native ACT copy.

Only the selected action receives custom art. Every other action is a stock
reference, so Act Editor retains native action numbers and head references.
"""
import copy,hashlib,json,math,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from review_original_job_directions import OUT,native_context
from render_native_wing_anatomy import rgba
from refine_clan_combat_necks import components
from sprite_formats import Layer,anchor,read_spr,read_act,write_spr,write_act
from spr_reader import Spr
from preview_clan_reference_revision import bake
from render_clan_all_action_review import render
from sprite_review_animation import save_review_animation

ROOT=OUT/'native-pose-redraw-v7'
DEST=ROOT/'act11-preview'
ACTION=11


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def extract_frames():
    source=ROOT/'male-action11-generated-study.png'
    assert sha(source)=='9640f38a58850b5cae5957a9e34d63cd786457b1092659f3227997cd9fb973e3'
    sheet=Image.open(source).convert('RGB');frames=[];records=[]
    folder=DEST/'whole-frames';folder.mkdir(parents=True,exist_ok=True)
    board=Image.new('RGBA',sheet.size)
    for fi in range(8):
        box=(round(fi%4*sheet.width/4),round(fi//4*sheet.height/2),
             round((fi%4+1)*sheet.width/4),round((fi//4+1)*sheet.height/2))
        pixels=np.asarray(sheet.crop(box));rgb=pixels.astype(int)
        neutral=(rgb.max(axis=2)-rgb.min(axis=2)<=15)&(rgb.min(axis=2)>=40)
        flood=Image.fromarray((neutral*255).astype('uint8')).copy()
        assert flood.getpixel((0,0))==255
        ImageDraw.floodfill(flood,(0,0),128)
        outside=np.asarray(flood)==128
        groups=sorted(components(~outside),key=len,reverse=True)
        assert groups and len(groups[0])>20000
        assert len(groups)==1 or len(groups[1])<64,(fi,'unexpected second body part')
        keep=np.zeros(outside.shape,bool);g=groups[0];keep[g[:,0],g[:,1]]=True
        data=np.dstack((pixels,keep.astype('uint8')*255));data[~keep]=0
        full=Image.fromarray(data);bounds=full.getbbox();art=full.crop(bounds)
        art.save(folder/f'frame-{fi:02d}.png');board.alpha_composite(full,box[:2])
        assert np.array_equal(np.asarray(full)[keep,:3],pixels[keep])
        assert not np.any(np.asarray(full)[~keep])
        frames.append(art)
        records.append(dict(frame=fi,source_cell=list(box),source_crop=list(bounds),
            outside_checker_pixels=int(outside.sum()),isolated_background_specks=int(sum(map(len,groups[1:]))),
            retained_rgb_unchanged=True,alpha_values=[0,255],size=list(art.size)))
    board.save(DEST/'approved-sheet-transparent.png')
    return frames,records


def collar(image,band):
    alpha=np.asarray(image)[:,:,3]>128
    ys,xs=np.where(alpha);top=int(ys.min())
    _,xs=np.where(alpha[top:top+band])
    return np.array([(float(xs.min())+float(xs.max()))/2,top])


def native_pieces(spr,frame):
    result=[]
    for l in frame.layers:
        if l.index<0:continue
        assert l.sx==l.sy==1 and l.angle==0 and l.color==(255,255,255,255)
        im=rgba(spr,l.index,l.kind)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        x=(l.x-im.width//2)*4;y=(l.y-im.height//2)*4
        im=im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST)
        result.append((im,x,y))
    return result


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    art,imports=extract_frames()
    src,spr,native,heads,ha=native_context('swordman','male')
    first=native.actions[ACTION][0].layers[0];ni=rgba(spr,first.index,first.kind);nb=ni.getbbox()
    # One scalar for the entire approved sequence, registered from its neutral
    # frame. No per-frame stretching or independent limb transformations.
    scale=(nb[3]-nb[1])*4/art[0].height
    act=copy.deepcopy(native);images=[];seen={};registrations=[];native_equivalent=0
    for ai,frames in enumerate(act.actions):
        for fi,f in enumerate(frames):
            if ai==ACTION:
                im=art[fi];point=collar(im,8)
                l=native.actions[ai][fi].layers[0];ref=rgba(spr,l.index,l.kind);npoint=collar(ref,2)
                target=(np.array([l.x-ref.width//2,l.y-ref.height//2])+npoint)*4
                size=(math.ceil(im.width*scale),math.ceil(im.height*scale))
                fitted=im.transform(size,Image.Transform.AFFINE,(1/scale,0,0,0,1/scale,0),resample=Image.Resampling.NEAREST)
                offset=np.rint(target-point*scale).astype(int)
                pieces=[(fitted,int(offset[0]),int(offset[1]))]
                original=native_pieces(spr,native.actions[ai][fi])
                original_bottom=max(y+image.getbbox()[3] for image,x,y in original)
                fitted_bottom=int(offset[1])+fitted.getbbox()[3]
                registrations.append(dict(frame=fi,uniform_scale=scale,source_collar=point.tolist(),
                    target_collar_4x=target.tolist(),placement_4x=offset.tolist(),
                    collar_rounding_error_4x=(offset+point*scale-target).tolist(),
                    lowest_visible_pixel_difference_native=(fitted_bottom-original_bottom)/4,
                    native_head_anchor=list(anchor(native.actions[ai][fi]))))
            else:
                pieces=native_pieces(spr,native.actions[ai][fi]);native_equivalent+=1
            image,x,y=bake(pieces)
            key=(image.size,hashlib.sha256(image.tobytes()).hexdigest())
            if key not in seen:seen[key]=len(images);images.append(image)
            f.layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
    stem=DEST/'male-angel-action11-v7'
    sb,ab=write_spr(images),write_act(act);stem.with_suffix('.spr').write_bytes(sb);stem.with_suffix('.act').write_bytes(ab)
    decoded=read_spr(sb);parsed=read_act(ab);independent=Spr(sb)
    assert len(parsed.actions)==104 and sum(map(len,parsed.actions))==456
    assert parsed.speeds==native.speeds
    assert all(a.tobytes()==b.tobytes() for a,b in zip(images,decoded))
    assert all(a.tobytes()==rgba(independent,i,1).tobytes() for i,a in enumerate(images))
    for ai,frames in enumerate(parsed.actions):
        for fi,f in enumerate(frames):
            ref=native.actions[ai][fi]
            assert (f.anchors,f.sound,f.ranges)==(ref.anchors,ref.sound,ref.ranges)
            if ai!=ACTION:
                expected,x,y=bake(native_pieces(spr,ref));layer=f.layers[0]
                assert (layer.x,layer.y)==(x,y)
                assert decoded[layer.index].tobytes()==expected.tobytes()
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    movie=[];strip=Image.new('RGB',(8*220,635),'#283746');pen=ImageDraw.Draw(strip)
    from compare_walk_with_original import render_native
    for fi in range(8):
        old=render_native('male',ACTION,fi);new=render(decoded,parsed,heads,ha,ACTION,fi)
        panel=Image.new('RGB',(600,335),'#283746');p=ImageDraw.Draw(panel)
        for col,(image,title) in enumerate(((old,'Original Swordman'),(new,'Approved whole-pose art'))):
            panel.paste(image,(col*300,20),image);p.text((col*300+8,4),title,font=font,fill='white')
            tile=image.crop((40,0,260,300));strip.paste(tile,(fi*220,col*310+20),tile)
            pen.text((fi*220+6,col*310+3),f'{title} / F{fi}',fill='white')
        p.text((8,316),f'Action 11 / frame {fi} / 75 ms / unchanged native head anchors',font=font,fill='white')
        movie.append(panel)
    strip.save(DEST/'all-eight-exported-frames.png')
    save_review_animation(movie,DEST/'action11-comparison.gif',round(native.speeds[ACTION]*25),apng=DEST/'action11-comparison.png')
    result=dict(status='Approved male rear-diagonal artwork exported for ACT review; animation acceptance pending',
        sex='male',custom_action=ACTION,custom_frames=8,custom_sprite_indices=[f.layers[0].index for f in parsed.actions[ACTION]],
        action_count=104,total_frame_uses=456,unchanged_stock_reference_frames=native_equivalent,
        all_other_actions='Original Swordman reference, not custom Angel artwork',frame_duration_ms=native.speeds[ACTION]*25,
        world_scale=.25,source_sha256=sha(ROOT/'male-action11-generated-study.png'),source_rgb_preserved_before_uniform_scaling=True,
        native_head_anchors_preserved=True,native_timings_and_sounds_preserved=True,independent_decoder_match=True,
        source_import=imports,registration=registrations,not_for_game_installation=True,installed_files_modified=False,
        files=[dict(path=p.name,sha256=sha(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))])
    (DEST/'export-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ('custom_action','custom_frames','custom_sprite_indices','unchanged_stock_reference_frames','frame_duration_ms','independent_decoder_match')}))
    print(stem.with_suffix('.act'))


if __name__=='__main__':main()
