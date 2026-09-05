"""Measure contact between opaque weapon pixels and the local fist silhouette.

Uses actual held packets from the offline old-angle, palm-centered measurement
payload. Moving from the grip toward the opaque weapon centroid, solve
separating-axis intervals for real pixel squares. Store the touching edge
coordinates in the two original textures; no sprite is edited.
The fist mask is explicitly bounded to three source texels around the reviewed
palm annotation. This is a local seam contract, not whole-body occlusion.
"""
from __future__ import annotations
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'.venv/Lib/site-packages'));sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
from verify_dual_weapon_pixel_grips import GripResources,GripMachine,CLIENT,INPUT,point
from verify_dual_weapon_native_projection import NativeProjector
from verify_dual_weapon_native_basis import invoke_native
from dual_weapon_formats.spr_reader import Spr

OUT=ROOT/'Outputs/dual_weapon_edge_contacts'
PAYLOAD=ROOT/'Outputs/dual_weapon_edge_contacts/old-angle-center-reference.dwcp'
EXE=ROOT/'Outputs/dual_weapon_grip_placement/client-pixel-grips.exe'

def affine(geometry, dimensions):
    top,left,bottom,right,angle=geometry;w,h=dimensions;a=math.radians(angle)
    rotation=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    matrix=rotation@np.diag([(right-left)/w,(bottom-top)/h])
    center=np.array([(left+right)/2,(top+bottom)/2])
    origin=center-matrix@np.array([w/2,h/2])
    return origin,matrix

def vertices(center,matrix):
    return center+np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])@matrix.T

def solve(body_points,body_matrix,weapon_points,weapon_matrix,axis):
    # Pixel rectangles have just four distinct separating axes.
    normals=np.array([[1.,0.],[0.,1.],weapon_matrix[:,0]/np.linalg.norm(weapon_matrix[:,0]),
                      weapon_matrix[:,1]/np.linalg.norm(weapon_matrix[:,1])])
    aa=body_points@normals.T;bb=weapon_points@normals.T
    ah=np.abs(normals@body_matrix).sum(axis=1)/2
    bh=np.abs(normals@weapon_matrix).sum(axis=1)/2
    delta=aa[:,None,:]-bb[None,:,:];extent=ah+bh
    speed=normals@axis
    lows=np.full(delta.shape,-np.inf);highs=np.full(delta.shape,np.inf)
    for n,s in enumerate(speed):
        if abs(s)<1e-10:
            invalid=np.abs(delta[:,:,n])>=extent[n]-1e-9
            lows[:,:,n][invalid]=np.inf;highs[:,:,n][invalid]=-np.inf
        else:
            x=(delta[:,:,n]-extent[n])/s;y=(delta[:,:,n]+extent[n])/s
            lows[:,:,n]=np.minimum(x,y);highs[:,:,n]=np.maximum(x,y)
    low=lows.max(axis=2);high=highs.min(axis=2)
    valid=(high>np.maximum(low,0)+1e-8)
    overlap=((low<0)&(high>0)&valid)
    assert overlap.any(), 'Expected current palm/weapon overlap for this contact measurement'
    # End of the collision interval connected to the initial overlapping pose.
    end=0.;chosen=None
    while True:
        connected=valid&(low<=end+1e-8)
        index=np.unravel_index(np.argmax(np.where(connected,high,-np.inf)),high.shape)
        candidate=float(high[index])
        if candidate<=end+1e-8:break
        end=candidate;chosen=index
    ai,bi=chosen;ni=int(np.argmin(highs[ai,bi]));normal=normals[ni]
    if speed[ni]<0:normal=-normal
    av=vertices(body_points[ai],body_matrix)
    bv=vertices(weapon_points[bi]+axis*end,weapon_matrix)
    plane=float((av@normal).max());plane2=float((bv@normal).min())
    assert abs(plane-plane2)<1e-5
    tangent=np.array([-normal[1],normal[0]])
    sa=av[np.abs(av@normal-plane)<1e-5]@tangent
    sb=bv[np.abs(bv@normal-plane2)<1e-5]@tangent
    lo=max(sa.min(),sb.min());hi=min(sa.max(),sb.max())
    assert lo<=hi+1e-5
    contact=normal*plane+tangent*((lo+hi)/2)
    assert not np.any(valid&(low<end-1e-6)&(high>end+1e-6))
    return contact,end,dict(initial_intersecting_pixel_pairs=int(overlap.sum()),
                            boundary_body_pixel=int(ai),boundary_weapon_pixel=int(bi),
                            body_normal=normal.tolist())

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    res=GripResources(CLIENT);m=GripMachine(res,PAYLOAD);proj=NativeProjector(EXE)
    ann=json.loads(INPUT.read_text(encoding='utf-8'))
    inv=json.loads((ROOT/'Outputs/dual_weapon_pixel_audit/inventory.json').read_text(encoding='utf-8'))
    decl={r['view']:r for r in inv['weapons']};records=[];cache={};solved={}
    def pixels(resource,index):
        key=resource['name'],index
        if key not in cache:
            rgba,w,h=Spr(res.read(resource['name']+'.spr')).get_rgba(index,0)
            alpha=np.frombuffer(rgba,dtype=np.uint8).reshape(h,w,4)[:,:,3]
            ys,xs=np.where(alpha>0);cache[key]=(np.stack([xs,ys],axis=1).astype(float),(w,h))
        return cache[key]
    for view,entry in decl.items():
        target=m.load(entry['stem'].rsplit('어세신_여_',1)[1]);partner=m.load('13412' if view!=45 else '1238')
        for d in range(8):
            main_role=1 if d in (2,3,6,7) else 0
            for f in range(6):
                action=32+d;bl=m.native_layer(m.body,action,f);bp,bs=pixels(m.body,bl[2])
                bg=proj.project(bl,(*bs,0,0),origin=(960,495));bo,bm=affine([*bg[:4],bg[7]],bs)
                for role in (0,1):
                    logical=0 if main_role==role else 1
                    args=(target,partner,entry['type'],2 if view!=45 else 1,view,45 if view!=45 else 34) if logical==0 else (partner,target,2 if view!=45 else 1,entry['type'],45 if view!=45 else 34,view)
                    stock,trail=m.equip_views(*args)
                    result=invoke_native(m,proj,stock,action,f,1.,5)
                    draw=next(x for x in result['draws'] if x['resource']==target['name'])
                    assert draw['image'][0]==0
                    wp,ws=pixels(target,draw['image'][1]);wo,wm=affine(draw['geometry'],ws)
                    palm=np.array(ann['body_pixels'][str(bl[2])][role])
                    local=bp[np.max(np.abs(bp-palm),axis=1)<=3]
                    assert len(local)>3
                    body_world=bo+(local+.5)@bm.T;weapon_world=wo+(wp+.5)@wm.T
                    grip,tip=ann['weapon_pixels'][str(view)][str(draw['image'][1])]
                    axis=wm@(wp.mean(axis=0)-grip);axis=axis/np.linalg.norm(axis)
                    key=(view,d,bl[2],role,draw['image'][1],tuple(draw['geometry']))
                    if key not in solved:
                        contact,distance,detail=solve(body_world,bm,weapon_world,wm,axis)
                        bc=np.linalg.solve(bm,contact-bo)
                        wc=np.linalg.solve(wm,contact-axis*distance-wo)
                        solved[key]=(bc,wc,distance,detail)
                    bc,wc,distance,detail=solved[key]
                    assert distance<32,(view,d,f,role,distance)
                    records.append(dict(view=view,direction=d,frame=f,role=role,body_index=bl[2],
                        weapon_index=draw['image'][1],body_contact=bc.tolist(),weapon_contact=wc.tolist(),
                        shift_source_units=distance,axis=axis.tolist(),hand_mask=local.astype(int).tolist(),**detail))
    assert len(records)==17*8*6*2
    report=dict(schema='dual_weapon_held_pixel_edge_contacts/v1',base_exe_sha256=proj.sha256,
        base_payload_sha256=hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),
        annotations_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        method='Opaque source pixel squares; first separating contact toward the opaque weapon centroid from the measured grip. Local fist mask: opaque pixels within Chebyshev radius 3 of the reviewed palm point.',
        records=records,live_acceptance=False)
    (OUT/'contacts.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    lines=['/* Measured held pixel-boundary contacts. Generated by build_dual_weapon_edge_contacts.py. */',
           '#ifndef DW_HELD_EDGE_CONTACTS_H','#define DW_HELD_EDGE_CONTACTS_H',
           'typedef struct { unsigned short index; float bx,by,wx,wy; } DWHeldContact;',
           'static const unsigned short DW_CONTACT_VIEWS[17] = {'+','.join(map(str,decl))+'};',
           'static const DWHeldContact DW_HELD_CONTACTS[17][8][6][2] = {']
    lookup={(r['view'],r['direction'],r['frame'],r['role']):r for r in records}
    for view in decl:
        lines.append('\t{')
        for d in range(8):
            lines.append('\t\t{')
            for f in range(6):
                rows=[]
                for role in (0,1):
                    r=lookup[view,d,f,role];values=r['body_contact']+r['weapon_contact']
                    rows.append('{'+str(r['weapon_index'])+','+','.join(f'{v:.9f}f' for v in values)+'}')
                lines.append('\t\t\t{'+','.join(rows)+'},')
            lines.append('\t\t},')
        lines.append('\t},')
    lines+=['};','#endif','']
    (OUT/'held_edge_contacts.h').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(records=len(records),min_shift=min(r['shift_source_units'] for r in records),
                         max_shift=max(r['shift_source_units'] for r in records),output=str(OUT))))

if __name__=='__main__':main()
