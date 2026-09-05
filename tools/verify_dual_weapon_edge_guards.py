"""Off-only seam, same-image ownership, and rejection gates for the edge build."""
import sys,json,math,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'.venv/Lib/site-packages'));sys.dont_write_bytecode=True
from verify_dual_weapon_pixel_grips import GripResources,GripMachine,CLIENT,point
from verify_dual_weapon_native_basis import invoke_native
from verify_dual_weapon_native_projection import NativeProjector

PAYLOAD=ROOT/'Outputs/dual_weapon_edge_contacts/compositor.dwcp'
EXE=ROOT/'Outputs/dual_weapon_edge_contacts/client-old-motion-edge-contacts.exe'

def main():
    r=GripResources(CLIENT);m=GripMachine(r,PAYLOAD);p=NativeProjector(EXE)
    inv=json.loads((ROOT/'Outputs/dual_weapon_pixel_audit/inventory.json').read_text(encoding='utf-8'))
    records=json.loads((ROOT/'Outputs/dual_weapon_edge_contacts/contacts.json').read_text(encoding='utf-8'))['records']
    contacts={(v['view'],v['direction'],v['frame'],v['role']):v for v in records}
    weapons={v['view']:m.load(v['stem'].rsplit('어세신_여_',1)[1]) for v in inv['weapons']}
    types={v['view']:v['type'] for v in inv['weapons']};off_cases=0;same_cases=0;max_error=0.;body_cache={}
    def error(draw,v,d,f,hand,unit,extra):
        c=contacts[v,d,f,hand];resource=weapons[v];im=resource['images'][tuple(draw['image'])][1]
        assert draw['image'][1]==c['weapon_index']
        key=d,f,unit,extra
        if key not in body_cache:
            l=m.native_layer(m.body,32+d,f);bi=m.body['images'][l[8],l[2]][1]
            bp=p.project(l,(bi.width,bi.height,0,0),unit,origin=(960,495),actor_angle=extra)
            body_cache[key]=([*bp[:4],bp[7]],(bi.width,bi.height))
        bg,dimensions=body_cache[key]
        a=point(bg,dimensions,[x-.5 for x in c['body_contact']])
        b=point(draw['geometry'],(im.width,im.height),[x-.5 for x in c['weapon_contact']])
        return math.dist(a,b)
    for v,w in weapons.items():
        for carrier in ('단검','검','도끼'):
            stock,trail=m.equip_views(w,w,types[v],types[v],v,v,carrier,True)
            for d in range(8):
                hand=0 if d in (2,3,6,7) else 1
                for f in range(6):
                    for unit,extra in ((1.,0),(2.3423,15)):
                        draws=[]
                        for ch,res in ((5,stock),(6,trail)):
                            result=invoke_native(m,p,res,32+d,f,unit,ch,extra)
                            if result:
                                assert result['handled']==1
                                draws+=result['draws']
                        assert len(draws)==1 and draws[0]['resource']==w['name']
                        e=error(draws[0],v,d,f,hand,unit,extra);assert e<.001
                        max_error=max(max_error,e);off_cases+=1
        stock,trail=m.equip_views(w,w,types[v],types[v],v,v)
        for d in range(8):
            result=invoke_native(m,p,stock,32+d,0,1.,5)
            assert result['handled']==1 and len(result['draws'])==2
            matching=[min(range(2),key=lambda h:error(draw,v,d,0,h,1.,0)) for draw in result['draws']]
            assert set(matching)=={0,1}
            assert all(error(draw,v,d,0,h,1.,0)<.001 for draw,h in zip(result['draws'],matching))
            same_cases+=1
    accepted=rejected=0
    for a in range(1,24):
        for b in range(1,24):
            stock,_=m.equip_views(weapons[45],weapons[34],a,b,45,34)
            actual=m.invoke(stock,32,0);expected=a in (1,2,6) and b in (1,2,6)
            assert actual==int(expected)
            accepted+=expected;rejected+=not expected
    stock,_=m.equip_views(weapons[45],weapons[34],2,1,45,34);guards=[]
    def reject(label,address,data):
        original=bytes(m.u.mem_read(address,len(data)));m.u.mem_write(address,data)
        try:assert m.invoke(stock,32,0)==0 and not m.calls,label
        finally:m.u.mem_write(address,original)
        guards.append(label)
    reject('Drake excluded',m.viewrow,struct.pack('<I',600))
    reject('Unknown view excluded',m.viewrow,struct.pack('<I',500))
    reject('Male does not borrow female contacts',m.row+56,struct.pack('<I',1))
    reject('Body ACT mismatch',m.body['act']+0x14,b'X')
    reject('Body SPR mismatch',m.body['spr']+0x14,b'X')
    reject('Stale body image',m.body['layers'][32,0][0]+8,struct.pack('<I',9999))
    reject('Stale selected original image',weapons[45]['layers'][32,0][0]+8,struct.pack('<I',1))
    reject('Nonidentity original angle',weapons[45]['layers'][32,0][0]+28,struct.pack('<I',5))
    result=dict(schema='dual_weapon_edge_guards/v1',payload_sha256=hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),
        exe_sha256=p.sha256,off_only_cases=off_cases,same_image_dual_cases=same_cases,
        accepted_class_pairs=accepted,rejected_class_pairs=rejected,max_contact_error=max_error,guards=guards,passed=True)
    (ROOT/'docs/evidence/dual-weapon-edge-contacts-guards-20260905.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
