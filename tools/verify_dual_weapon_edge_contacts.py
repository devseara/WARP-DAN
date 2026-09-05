"""Execute the candidate: old attack geometry and visible held-pixel seams.

The old compiled C payload is the trajectory oracle. Hand roles are explicitly
assigned to anatomical equipment slots. Held checks project the original alpha
pixels and test rectangle separation, not equality to a copied C formula.
"""
from __future__ import annotations
import sys,json,hashlib,math,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'.venv/Lib/site-packages'));sys.dont_write_bytecode=True
import numpy as np
from verify_dual_weapon_pixel_grips import GripResources,GripMachine,CLIENT
from verify_dual_weapon_native_basis import invoke_native
from verify_dual_weapon_native_projection import NativeProjector
from dual_weapon_formats.spr_reader import Spr
from build_dual_weapon_edge_contacts import affine

OLD=ROOT/'Outputs/dual_weapon_supported_types/compositor.dwcp'
PAYLOAD=ROOT/'Outputs/dual_weapon_edge_contacts/compositor.dwcp'
EXE=ROOT/'Outputs/dual_weapon_grip_placement/client-pixel-grips.exe'
CONTACTS=ROOT/'Outputs/dual_weapon_edge_contacts/contacts.json'

def penetration(a,am,b,bm):
    normals=np.array([v/np.linalg.norm(v) for v in (am[:,0],am[:,1],bm[:,0],bm[:,1])])
    half=(np.abs(normals@am).sum(axis=1)+np.abs(normals@bm).sum(axis=1))/2
    delta=np.abs((a@normals.T)[:,None,:]-(b@normals.T)[None,:,:])
    return float(np.maximum(0,np.min(half-delta,axis=2)).max())

def run(payload,exe):
    res=GripResources(CLIENT);new=GripMachine(res,payload);old=GripMachine(res,OLD)
    proj=NativeProjector(exe);raw=json.loads(CONTACTS.read_text(encoding='utf-8'))
    contacts={(r['view'],r['direction'],r['frame'],r['role']):r for r in raw['records']}
    inv=json.loads((ROOT/'Outputs/dual_weapon_pixel_audit/inventory.json').read_text(encoding='utf-8'))
    entries={r['view']:r for r in inv['weapons']}
    names={v:r['stem'].rsplit('어세신_여_',1)[1] for v,r in entries.items()}
    nw={v:new.load(n) for v,n in names.items()};ow={v:old.load(n) for v,n in names.items()}
    cache={};body_cache={};cases=0;attacks=0;held=0;max_error=0.;max_pen=0.;worst=[]
    def pixels(name,index):
        key=name,index
        if key not in cache:
            rgba,w,h=Spr(res.read(name+'.spr')).get_rgba(index,0)
            alpha=np.frombuffer(rgba,dtype=np.uint8).reshape(h,w,4)[:,:,3]
            ys,xs=np.where(alpha>0);cache[key]=(np.stack([xs,ys],axis=1),(w,h))
        return cache[key]
    def body(d,f,unit,extra):
        key=d,f,unit,extra
        if key not in body_cache:
            l=new.native_layer(new.body,32+d,f);p,dimensions=pixels('@body',l[2])
            packet=proj.project(l,(*dimensions,0,0),unit,origin=(960,495),actor_angle=extra)
            body_cache[key]=affine([*packet[:4],packet[7]],dimensions)
        return body_cache[key]
    for v in entries:
        partner=45 if v!=45 else 34
        for logical in (0,1):
            mv,ov=(v,partner) if logical==0 else (partner,v)
            stock,trail=new.equip_views(nw[mv],nw[ov],entries[mv]['type'],entries[ov]['type'],mv,ov)
            for d in range(8):
                main_hand=1 if d in (2,3,6,7) else 0
                rv0,rv1=(mv,ov) if main_hand==0 else (ov,mv)
                # The old wrapper sorts by class; supply role-ordered resources
                # and unsorted admitted fixture classes, isolating geometry.
                os,ot=old.equip_views(ow[rv0],ow[rv1],2,1,500,501)
                for phase,count in ((0,6),(1,8)):
                    for f in range(count):
                        for unit,extra in ((1.,0),(2.3423,0),(2.3423,15),(2.3423,-90)):
                            action=(32 if phase==0 else 88)+d
                            actual=[];reference=[]
                            for ch,nr,orr in ((5,stock,os),(6,trail,ot)):
                                n=invoke_native(new,proj,nr,action,f,unit,ch,extra)
                                o=invoke_native(old,proj,orr,action,f,unit,ch,extra)
                                if n:
                                    assert n['handled']==1
                                    actual+=n['draws']
                                if o:
                                    assert o['handled']==1
                                    reference+=o['draws']
                            expected={x['resource']:x for x in reference}
                            assert len(actual)==len(reference)
                            for draw in actual:
                                name=draw['resource'];e=expected[name]
                                assert draw['image']==e['image']
                                angle_error=abs((draw['geometry'][4]-e['geometry'][4]+180)%360-180)
                                assert angle_error<.001
                                if phase:
                                    error=max(abs(a-b) for a,b in zip(draw['geometry'],e['geometry']))
                                    assert error<.001,('attack_changed',v,logical,d,f,error)
                                    max_error=max(max_error,error);attacks+=1
                                    continue
                                view=mv if name==names[mv] else ov
                                role=main_hand if view==mv else 1-main_hand
                                c=contacts[view,d,f,role]
                                assert c['weapon_index']==draw['image'][1]
                                pp,dim=pixels(name,draw['image'][1]);wo,wm=affine(draw['geometry'],dim)
                                bo,bm=body(d,f,unit,extra)
                                a=bo+bm@c['body_contact'];b=wo+wm@c['weapon_contact']
                                error=float(np.linalg.norm(a-b));assert error<.001
                                bp=bo+(np.array(c['hand_mask'])+.5)@bm.T
                                wp=wo+(pp+.5)@wm.T
                                overlap=penetration(bp,bm,wp,wm)
                                max_error=max(max_error,error);held+=1
                                if overlap>max_pen:
                                    max_pen=overlap;worst=[view,d,f,role,unit,extra,overlap]
                            cases+=1
    assert max_pen<.001, ('visible_hand_penetration',worst)
    report=dict(schema='dual_weapon_edge_contact_execution/v1',payload_sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
        native_pe_sha256=proj.sha256,cases=cases,attack_draws=attacks,held_draws=held,
        maximum_geometry_or_contact_error=max_error,maximum_local_pixel_penetration=max_pen,worst_penetration=worst,
        live_acceptance=False,limits=['Fist masks are local opaque pixels within three texels of manually reviewed palm points.',
            'Held contact constraints do not replace native GPU depth/occlusion.',
            'Old reference role geometry is retained with anatomical slot ownership; class-based slot sorting is not restored.'])
    out=ROOT/'Outputs/dual_weapon_edge_contacts/execution.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--payload',type=Path,default=PAYLOAD);ap.add_argument('--exe',type=Path,default=EXE)
    a=ap.parse_args();run(a.payload,a.exe)
