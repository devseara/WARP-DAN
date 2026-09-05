"""Compile reviewed pixel landmarks; never infer a grip from an ACT center.

Pixel coordinates name texel centers (runtime adds .5). Only the 17 non-Drake
female Assassin weapon views and the female Assassin Cross body are profiled.
Manual annotations are reviewable input, not a claim of live visual acceptance.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_dual_weapon_type_coverage import Corpus, ROOT
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr
from build_dual_weapon_native_basis import build as native_basis

INPUT=ROOT/'Inputs/DualWeaponAuthored/grips/female-assassin-pixel-landmarks.json'
HEADER=ROOT/'CustomDLL/DualWeapon/grip_profile.h'
CLIENT=Path(r'D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes')
BODY='data/sprite/인간족/몸통/여/어쌔신크로스_여'

def build(client=CLIENT):
    authored=json.loads(INPUT.read_text(encoding='utf-8'))
    _,basis_report=native_basis(client)
    basis={(r['phase'],r['direction'],r['frame']):r for r in basis_report['records']}
    corpus=Corpus(client)
    assert not corpus.unreadable
    for name,expected in authored['resource_sha256'].items():
        raw=corpus.read(name)
        assert raw is not None and hashlib.sha256(raw).hexdigest()==expected,('authored_resource_changed',name)
    inventory=json.loads((ROOT/'Outputs/dual_weapon_pixel_audit/inventory.json').read_text(encoding='utf-8'))
    weapons={r['view']:r for r in inventory['weapons'] if r['view']<600}
    assert set(weapons)=={1,2,6,*range(34,48)}
    rows=[]; review=[]
    for key,annotations in authored['weapon_pixels'].items():
        view=int(key); source=weapons[view]; raw=corpus.read(source['stem']+'.spr'); spr=Spr(raw)
        assert hashlib.sha256(raw).hexdigest()==inventory['sources'][(source['stem']+'.spr').lower()]['sha256']
        for n,im in enumerate(spr.images):
            points=annotations.get(str(n)); rgba,w,h=spr.get_rgba(n,0)
            rec=dict(view=view,index=n,width=w,height=h,rgba_sha256=hashlib.sha256(rgba).hexdigest())
            if points is None:
                rec.update(status='inspected_partial_art_not_selected_by_held_or_dual_attack_profile')
            else:
                grip,tip=points
                for x,y in (grip,tip):
                    assert 0<=x<w and 0<=y<h,(view,n,x,y)
                # Ring/loop handles can surround an unpainted grip center.
                # Require local handle pixels, but never move the annotation
                # automatically to a neighboring opaque pixel.
                x,y=grip
                assert sum(bool(rgba[(yy*w+xx)*4+3]) for yy in range(max(0,y-1),min(h,y+2))
                           for xx in range(max(0,x-1),min(w,x+2)))>=2
                x,y=tip
                assert rgba[(y*w+x)*4+3],('tip_on_transparent_pixel',view,n,x,y)
                angle=math.degrees(math.atan2(tip[1]-grip[1],tip[0]-grip[0]))
                rec.update(status='manual_pixel_annotation',grip=grip,tip=tip,axis_angle=angle)
                rows.append([view,n,w,h,*grip,*tip])
            review.append(rec)
    assert len(rows)==68 and len(review)==92
    actraw,sprraw=corpus.read(BODY+'.act'),corpus.read(BODY+'.spr')
    act,spr=parse_act(actraw),Spr(sprraw)
    generic_stem='data/sprite/인간족/어세신/어세신_여_단검_검'
    generic_act=parse_act(corpus.read(generic_stem+'.act'))
    generic_spr=Spr(corpus.read(generic_stem+'.spr'))
    body=[]
    for phase,base,count in ((0,32,6),(1,88,8)):
        for direction in range(8):
            for frame in range(count):
                layers=act['actions'][base+direction].frames[frame].layers
                assert len(layers)==1
                l=layers[0]; rgba,w,h=spr.get_rgba(l.sprite_index,l.sprite_type)
                assert not l.sprite_type and not l.rotation and l.scale_x==l.scale_y==1
                # The annotation is on the UNMIRRORED source bitmap. Native
                # mirroring then carries it to the correct body-frame texel.
                points=authored['body_pixels'][str(l.sprite_index)]
                for x,y in points:
                    assert 0<=x<w and 0<=y<h and rgba[(y*w+x)*4+3],('body_socket_not_opaque',l.sprite_index,x,y)
                axes=[]
                gl=generic_act['actions'][base+direction].frames[frame].layers[0]
                generic_rgba,gw,gh=generic_spr.get_rgba(gl.sprite_index,0)
                assert gl.rotation==0 and gl.scale_x==gl.scale_y==1
                for role,view in enumerate((45,34)):
                    ref=basis[phase,direction,frame]['hands'][role]
                    if ref['hidden']:
                        axes.append([0,0])
                        continue
                    start,end=authored['generic_pair28_blade_axes'][str(gl.sprite_index)][role]
                    assert all(0<=p[0]<gw and 0<=p[1]<gh for p in (start,end))
                    assert all(generic_rgba[(p[1]*gw+p[0])*4+3] for p in (start,end)),('generic_axis_transparent_pixel',gl.sprite_index,role)
                    axes.append([end[0]-start[0],end[1]-start[1]])
                body.append(dict(phase=phase,direction=direction,frame=frame,index=l.sprite_index,
                    x=l.x-(w+1)//2,y=l.y-(h+1)//2,width=w,height=h,mirror=l.mirror,
                    sockets=points,main_reference_hand=1 if direction in (2,3,6,7) else 0,
                    reference_axes=axes,generic_index=gl.sprite_index,generic_width=gw,generic_height=gh,generic_mirror=gl.mirror,
                    rgba_sha256=hashlib.sha256(rgba).hexdigest()))
    text=['/* Generated from explicit sprite-pixel annotations; see docs/dual-weapon-grip-placement-20260905.md. */',
          '#ifndef DW_GRIP_PROFILE_H','#define DW_GRIP_PROFILE_H',
          'typedef struct { unsigned short view,index,width,height; short gx,gy,tx,ty; } DWGripImage;',
          'typedef struct { short index,x,y; unsigned short width,height; unsigned char mirror,mainHand; short grip[2][2]; short axis[2][2]; unsigned short genericWidth,genericHeight; unsigned char genericMirror; } DWBodyGrip;',
          'static const DWGripImage DW_GRIP_IMAGES[] = {']
    for r in rows:text.append('\t{'+','.join(map(str,r))+'},')
    text+=['};','static const DWBodyGrip DW_BODY_GRIPS[2][8][8] = {']
    lookup={(r['phase'],r['direction'],r['frame']):r for r in body}
    for phase in range(2):
        text.append('\t{')
        for d in range(8):
            text.append('\t\t{')
            for f in range(8):
                r=lookup.get((phase,d,f))
                if r:
                    fields=[r[k] for k in ('index','x','y','width','height','mirror','main_reference_hand')]
                    axes='{{'+','.join(map(str,r['reference_axes'][0]))+'},{'+','.join(map(str,r['reference_axes'][1]))+'}}'
                    text.append('\t\t\t{'+','.join(map(str,fields))+',{{'+','.join(map(str,r['sockets'][0]))+'},{'+','.join(map(str,r['sockets'][1]))+'}},'+axes+','+','.join(str(r[k]) for k in ('generic_width','generic_height','generic_mirror'))+'},')
                else:text.append('\t\t\t{-1,0,0,0,0,0,0,{{0,0},{0,0}},{{0,0},{0,0}},0,0,0},')
            text.append('\t\t},')
        text.append('\t},')
    text+=['};','#endif','']
    data='\n'.join(text).encode()
    HEADER.write_bytes(data)
    report=dict(schema='dual_weapon_grip_profile/v1',authored_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                header_sha256=hashlib.sha256(data).hexdigest(),sources=corpus.sources,
                weapon_images=review,body_cells=body,excluded_views=list(range(600,607)),
                live_acceptance=False,annotation_method=authored['annotation_method'])
    out=ROOT/'docs/evidence/dual-weapon-grip-profile-20260905.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    corpus.close()
    print(json.dumps(dict(views=len(weapons),inspected_images=len(review),profiled_images=len(rows),body_cells=len(body))))
    return report

if __name__=='__main__':build()
