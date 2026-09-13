"""Closed ivory/gold female gorget beneath the native sword-stance chin."""
import numpy as np
from PIL import Image,ImageDraw
from sprite_formats import anchor

ARMOR_COLORS={
    'outline':'#71503d','gold':'#c39350','gold_light':'#ffe9ad',
    'ivory':'#eeddbd','highlight':'#fff5dd','shadow':'#c5b196',
}


def close_collars(images,native,body_act,heads,head_act,sex,apertures):
    if sex!='female':return images,[]
    result=list(images);records=[]
    pockets={r['body']:r['apertures'][0] for r in apertures}
    for fi in range(6):
        f=body_act.actions[32][fi];body=next(l for l in f.layers if 0<=l.index<len(native.images))
        hf=head_act.actions[32][fi];h=next(l for l in hf.layers if l.index>=0)
        assert body.mirror==h.mirror==0
        hi=heads.images[h.index];indices=np.frombuffer(hi.pixels,np.uint8).reshape(hi.height,hi.width)
        face=(indices>=130)&(indices<=135);ys,xs=np.where(face);bottom=int(ys.max());chin=np.flatnonzero(face[bottom])
        bx,by=anchor(f);hx,hy=anchor(hf)
        center=h.x+bx-hx-hi.width//2+float(chin.mean())+.5
        chin_y=h.y+by-hy-hi.height//2+bottom+1
        image=images[body.index];left=body.x-image.width/8;top_body=body.y-image.height/8
        cx=round((center-left)*4);top=round((chin_y-2-top_body)*4)
        hole=pockets[body.index];base=round((hole[0]+hole[2])/2);lower=hole[3]-1
        # A broad flared plate connects jaw-level armor to the breastplate.
        # The face covers the upper overlap; no flesh-colored neck is added.
        shape=[(cx-11,top+2),(cx-6,top),(cx+9,top),(cx+13,top+3),
               (cx+14,top+9),(base+24,lower+3),(base+16,lower+10),
               (base-17,lower+9),(base-25,lower+1),(cx-14,top+9)]
        layer=Image.new('RGBA',image.size);d=ImageDraw.Draw(layer)
        d.polygon(shape,fill=ARMOR_COLORS['gold'],outline=ARMOR_COLORS['outline'],width=2)
        panel=[(cx-8,top+5),(cx+8,top+5),(cx+10,top+11),(base+18,lower+3),
               (base+12,lower+7),(base-14,lower+6),(base-20,lower),(cx-10,top+10)]
        d.polygon(panel,fill=ARMOR_COLORS['ivory'])
        d.polygon([(cx-8,top+6),(cx-3,top+6),(base-5,lower+4),(base-15,lower+3),(base-19,lower)],fill=ARMOR_COLORS['highlight'])
        d.polygon([(cx+5,top+7),(cx+9,top+8),(base+18,lower+3),(base+12,lower+7),(base+5,lower+5)],fill=ARMOR_COLORS['shadow'])
        d.line([(cx-8,top+3),(cx+8,top+3)],fill=ARMOR_COLORS['gold_light'],width=2)
        d.line([(base-17,lower+6),(base-5,lower+9),(base+13,lower+7)],fill=ARMOR_COLORS['gold_light'],width=2)
        before=np.asarray(image);after=before.copy();mask=np.asarray(layer)[:,:,3]>0
        after[mask]=np.asarray(layer)[mask]
        assert np.array_equal(before[~mask],after[~mask])
        result[body.index]=Image.fromarray(after)
        records.append(dict(body=body.index,chin_world=[center,chin_y],closed_plate_polygon_4x=shape,
                            colors=ARMOR_COLORS,changed_pixels=int(np.count_nonzero(np.any(before!=after,axis=2))),
                            outside_collar_unchanged=True))
    return result,records
