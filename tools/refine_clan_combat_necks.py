"""Replace residual hollow female combat collar interiors with native skin.

Only dark, horizontally enclosed aperture pixels near the native neck-contact
region are recolored. Gold edges, sprite alpha, all coordinates, wings and
accepted idle/walk body drawings are preserved.
"""
import numpy as np
from PIL import Image,ImageDraw


def components(mask):
    seen=np.zeros_like(mask);result=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        todo=[(int(y),int(x))];seen[y,x]=True;points=[]
        while todo:
            cy,cx=todo.pop();points.append((cy,cx))
            for dy,dx in [(0,-1),(0,1),(-1,0),(1,0),(-1,-1),(-1,1),(1,-1),(1,1)]:
                ny,nx=cy+dy,cx+dx
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;todo.append((ny,nx))
        result.append(np.array(points))
    return result


def refine(images,native,masks,sex,out=None):
    if sex!='female':return images,[]
    revised=list(images);records=[]
    skin=np.asarray(native.palette,dtype=np.uint8)[168:176]
    for index in range(56,62):
        image=images[index];a=np.array(image);rgb=a[:,:,:3].astype(int)
        # Reviewed apertures in the six front-facing sword-stance drawings.
        # B57's generated ring lies left of the old native contact mask, which
        # is why the earlier collar pass failed to cover that frame.
        bounds={56:(52,10,84,27),57:(54,9,87,27),58:(59,12,84,28),
                59:(56,15,82,27),60:(49,13,81,28),61:(56,15,84,28)}
        l,t,r,b=bounds[index]
        region=np.zeros(a.shape[:2],bool)
        region[t:b,l:r]=True
        luminance=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722
        aperture=region&(a[:,:,3]>=128)&(luminance<115)&(rgb[:,:,2]+10>=rgb[:,:,0])
        selected=np.zeros_like(aperture);holes=[]
        for pts in components(aperture):
            yy,xx=pts[:,0],pts[:,1]
            w,h=int(np.ptp(xx))+1,int(np.ptp(yy))+1
            # A collar opening is a shallow horizontal pocket. This excludes
            # vertical navy sleeve folds and isolated jewel/shadow pixels.
            if len(pts)<32 or h>32 or w<1.25*h:continue
            if abs(float(xx.mean())-(l+r)/2)>(r-l)/2+4:continue
            selected[yy,xx]=True;holes.append([int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1])
            tones=np.ones(len(pts),int)
            tones[(yy-yy.min())>=h*.4]=2
            tones[(yy-yy.min())>=h*.8]=3
            tones[(xx-xx.min())>=w*.82]=np.maximum(tones[(xx-xx.min())>=w*.82],3)
            indices=np.frombuffer(native.images[index].pixels,np.uint8).reshape(native.images[index].height,native.images[index].width)
            at=indices[yy//4,xx//4]
            native_skin=(at>=168)&(at<176)
            tones[native_skin]=np.clip(at[native_skin].astype(int)-168,1,4)
            a[yy,xx,:3]=skin[tones,:3]
        assert np.array_equal(a[:,:,3],np.array(image)[:,:,3])
        assert np.array_equal(a[~selected],np.array(image)[~selected])
        if selected.any():
            revised[index]=Image.fromarray(a)
            records.append(dict(body=index,pixels=int(selected.sum()),apertures=holes,alpha_unchanged=True,outside_aperture_unchanged=True))
            if out:
                out.mkdir(parents=True,exist_ok=True)
                revised[index].save(out/f'female-body-{index:03}-neck.png')
    return revised,records
