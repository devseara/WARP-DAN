"""Execute x86 and measure its original grip texels against native body texels.

The body oracle executes the unchanged PE's C40C20, using separately authored
SPR pixels. It does not copy prepare_gripped or read its generated header.
This proves arithmetic/ownership/ABI, not acceptance of the manual annotation.
"""
from __future__ import annotations
import argparse,hashlib,json,math,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
from verify_dual_weapon_compositor import Machine,Resources,ROOT
from verify_dual_weapon_native_basis import NativeMachine,invoke_native
from verify_dual_weapon_native_projection import NativeProjector
from audit_dual_weapon_type_coverage import Corpus
from build_dual_weapon_native_basis import build
from build_dual_weapon_grip_profile import CLIENT,BODY,INPUT

class GripResources(Resources):
    def __init__(self,client):
        super().__init__(client);self.corpus=Corpus(client)
    def read(self,name):
        if name.startswith('@body.'):
            return self.corpus.read(BODY+name[len('@body'):])
        return super().read(name)

class GripMachine(NativeMachine):
    def __init__(self,resources,payload):
        super().__init__(resources,payload)
        self.body=self.load('@body');self.actslots=self.alloc(4)
        self.w(self.slot,self.body['spr']);self.w(self.actslots,self.body['act'])
        self.w(self.actor+0x4b8,self.actslots,self.actslots+4)
        for field,ext in [('act','.act'),('spr','.spr')]:
            name=(BODY.removeprefix('data/').replace('/','\\')+ext).encode('cp949')+b'\0'
            self.u.mem_write(self.body[field]+0x14,name)
    def equip_views(self,main,off,mt,ot,mv,ov,carrier='단검_검',off_only=False):
        stock,trail=self.load(carrier),self.load(carrier+'_검광')
        self.w(self.slot+20,stock['spr'],trail['spr'])
        self.w(self.row,self.actor,0 if off_only else main['spr'],0 if off_only else main['act'],0,0,
               off['spr'],off['act'],0,0,stock['act'],trail['act'],28,0 if off_only else mt,ot,0)
        self.w(self.viewrow,0 if off_only else mv,ov)
        self.w(self.actor+0x440,0 if off_only else 1001,1002)
        return stock,trail

def point(geometry,dimensions,pixel):
    top,left,bottom,right,angle=geometry;w,h=dimensions
    x=((pixel[0]+.5)/w-.5)*(right-left)
    y=((pixel[1]+.5)/h-.5)*(bottom-top)
    a=math.radians(angle)
    return [(left+right)/2+x*math.cos(a)-y*math.sin(a),
            (top+bottom)/2+x*math.sin(a)+y*math.cos(a)]

def run(payload,exe,output):
    res=GripResources(CLIENT);m=GripMachine(res,payload);proj=NativeProjector(exe)
    ann=json.loads(INPUT.read_text(encoding='utf-8'));_,basis_report=build(CLIENT)
    basis={(b['phase'],b['direction'],b['frame']):b for b in basis_report['records']}
    coverage=json.loads((ROOT/'docs/evidence/dual-weapon-type-coverage.json').read_text(encoding='utf-8'))
    decl={r['view']:r for r in coverage['views'] if str(r['view']) in ann['weapon_pixels']}
    weapons={v:m.load(r['resource_stem']) for v,r in decl.items()}
    assert len(weapons)==17
    cache={};max_error=0;checked=0;draw_count=0;image_keys=set();examples=[]
    matrix=[]
    def expected_body(action,frame,unit,extra):
        key=action,frame,unit,extra
        if key not in cache:
            l=m.native_layer(m.body,action,frame);bitmap=m.body['images'][l[8],l[2]][1]
            p=proj.project(l,(bitmap.width,bitmap.height,0,0),unit,origin=(960,495),actor_angle=extra)
            geom=[*p[:4],p[7]];pts=ann['body_pixels'][str(l[2])]
            cache[key]=[point(geom,(bitmap.width,bitmap.height),p) for p in pts]
        return cache[key]
    def case(main_view,off_view,phase,direction,frame,unit,extra,off_only=False,record=False,carrier='단검_검'):
        nonlocal max_error,checked,draw_count
        main,off=weapons[main_view],weapons[off_view]
        stock,trail=m.equip_views(main,off,decl[main_view]['base_type'],decl[off_view]['base_type'],main_view,off_view,carrier,off_only)
        action=(32 if phase==0 else 88)+direction
        b=basis[phase,direction,frame]
        result={'draws':[]}
        for channel,current in [(5,stock),(6,trail)]:
            native_result=invoke_native(m,proj,current,action,frame,unit,channel,extra)
            if native_result:
                assert native_result['handled']==1,(main_view,off_view,phase,direction,frame,unit,extra,'rejected')
                result['draws'].extend(native_result['draws'])
        assert all(d['resource']!='@body' for d in result['draws'])
        # Anatomy: SW/SE face the viewer; NW/NE face away. Mirroring body
        # art must not exchange the equipment slots. Keep this rule explicit.
        main_hand=1 if direction in (2,3,6,7) else 0
        expected=[]
        for logical,view,resource in [(0,main_view,main),(1,off_view,off)]:
            if off_only and logical==0:continue
            hand=1-main_hand if logical else main_hand;r=b['hands'][hand]
            if r['hidden']:continue
            sa=(80 if r['sourceAttack'] else 32)+direction;sf=r['sourceFrame']
            l=resource['layers'][sa,sf][1];im=resource['images'][l.sprite_type,l.sprite_index][1]
            grip,tip=ann['weapon_pixels'][str(view)][str(l.sprite_index)]
            expected.append(dict(logical=logical,view=view,resource=resource,hand=hand,r=r,
                                 l=l,im=im,grip=grip,tip=tip))
        expected.sort(key=lambda e:(e['r']['order'],e['logical']))
        assert len(result['draws'])==len(expected),(main_view,off_view,phase,direction,frame,off_only,carrier,len(result['draws']),len(expected))
        targets=expected_body(action,frame,unit,extra)
        for draw,e in zip(result['draws'],expected):
            assert draw['resource']==e['resource']['name']
            assert tuple(draw['image'])==(e['l'].sprite_type,e['l'].sprite_index)
            w,h=e['im'].width,e['im'].height
            measured=point(draw['geometry'],(w,h),e['grip']);target=targets[e['hand']]
            error=math.dist(measured,target);max_error=max(max_error,error)
            assert error<.001,('hilt_misses_body_texel',main_view,off_view,phase,direction,frame,error)
            # Match the declared local blade axis to its selected reference
            # before the same actor rotation. This checks per-image angles.
            mirror=draw['geometry'][3]<draw['geometry'][1]
            assert mirror==bool(e['l'].mirror^e['r']['mirrorXor'])
            generic=m.load('단검_검');gl=m.native_layer(generic,action,frame)
            gi=generic['images'][gl[8],gl[2]][1]
            gp=proj.project(gl,(gi.width,gi.height,0,0),unit,origin=(960,495),actor_angle=extra)
            axis_points=ann['generic_pair28_blade_axes'][str(gl[2])][e['hand']]
            ga,gb=[point([*gp[:4],gp[7]],(gi.width,gi.height),p) for p in axis_points]
            tip_world=point(draw['geometry'],(w,h),e['tip'])
            local_axis=math.degrees(math.atan2(tip_world[1]-measured[1],tip_world[0]-measured[0]))
            target_axis=math.degrees(math.atan2(gb[1]-ga[1],gb[0]-ga[0]))
            angular_error=abs((local_axis-target_axis+180)%360-180)
            assert angular_error<.001,('generic_axis_mismatch',main_view,off_view,phase,direction,frame,angular_error)
            image_keys.add((e['view'],e['l'].sprite_index));draw_count+=1
            if record:
                examples.append(dict(main_view=main_view,off_view=off_view,off_only=off_only,phase=phase,
                    direction=direction,frame=frame,unit=unit,actor_angle=extra,logical_hand=e['logical'],
                    reference_hand=e['hand'],resource=draw['resource'],image=draw['image'],geometry=draw['geometry'],
                    body_grip=target,projected_grip=measured,error=error,grip=e['grip'],tip=e['tip']))
        checked+=1
    for view in sorted(weapons):
        start=checked
        for logical in (0,1):
            mv,ov=(view,34 if view!=34 else 45) if logical==0 else (45 if view!=45 else 34,view)
            for phase,count in [(0,6),(1,8)]:
                for d in range(8):
                    for f in range(count):
                        for unit,extra in [(1.,0),(2.3423,0),(2.3423,15),(2.3423,-90)]:
                            case(mv,ov,phase,d,f,unit,extra,record=unit==1.)
        for d in range(8):
            for f in range(6):
                for carrier in ['검','단검','도끼']:
                    case(34,view,0,d,f,2.3423,0,True,False,carrier)
        # Same-image duals must still bind two different logical slots.
        for d in range(8):case(view,view,0,d,0,1.,0)
        matrix.append(dict(view=view,cases=checked-start))
    assert len(image_keys)==68
    guards=[]
    stock,trail=m.equip_views(weapons[45],weapons[34],2,1,45,34)
    def reject(label,address,data):
        original=bytes(m.u.mem_read(address,len(data)));m.u.mem_write(address,data)
        try:assert m.invoke(stock,32,0)==0 and not m.calls,label
        finally:m.u.mem_write(address,original)
        guards.append(label)
    reject('Drake 600 stays outside the new profile',m.viewrow,struct.pack('<I',600))
    reject('foreign body filename',m.body['act']+0x14,b'X')
    reject('foreign body SPR filename',m.body['spr']+0x14,b'X')
    reject('stale body frame image',m.body['layers'][32,0][0]+8,struct.pack('<I',9999))
    reject('changed body placement',m.body['layers'][32,0][0],struct.pack('<i',100))
    reject('missing body vector',m.actor+0x4b8,struct.pack('<I',0))
    reject('unknown view cannot borrow a grip',m.viewrow,struct.pack('<I',500))
    reject('male body cannot use female sockets',m.row+56,struct.pack('<I',1))
    reject('nonidentity source scale',weapons[45]['layers'][32,0][0]+20,struct.pack('<f',1.2))
    reject('source angle outside the profile',weapons[45]['layers'][32,0][0]+28,struct.pack('<I',30))
    # If the old opaque core is called, execution stops with no valid draw.
    sentinel=m.alloc(16);m.u.mem_write(sentinel,b'\xB8\xDE\xC0\xA7\x51\xC2\x24\x00')
    m.w(m.ctx+19*4,sentinel)
    for mv,ov in [(34,45),(45,34)]:case(mv,ov,0,0,0,1.,0)
    m.w(m.ctx+19*4,0);guards.append('both former legacy-bypass pairs use measured grips')
    # Class guards remain independent of valid view/body fixtures.
    accepted=rejected=0
    for mt in range(1,24):
        for ot in range(1,24):
            stock,_=m.equip_views(weapons[45],weapons[34],mt,ot,45,34)
            result=m.invoke(stock,32,0);expected=mt in (1,2,6) and ot in (1,2,6)
            assert result==int(expected) and len(m.calls)==(2 if expected else 0)
            accepted+=expected;rejected+=not expected
    result=dict(schema='dual_weapon_pixel_grip_execution/v1',payload_sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
                exe_sha256=proj.sha256,authored_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                cases=checked,draws=draw_count,profiled_images=len(image_keys),max_grip_distance_pixels=max_error,
                accepted_class_pairs=accepted,rejected_class_pairs=rejected,matrix=matrix,guards=guards,examples=examples,
                native_body_oracle='Unmodified C40C20 executed from the supplied PE; explicit actor origin, current body layer, image and texel annotation.',
                live_acceptance=False,limits=['Manual palm/hilt/tip annotations require live visual acceptance.',
                'Held32 and dual88 only; off-only other native phases remain inherited.',
                'Female Assassin Cross body only; Drake variants explicitly excluded.'])
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('cases','draws','profiled_images','max_grip_distance_pixels','accepted_class_pairs','rejected_class_pairs')}))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--payload',type=Path,default=ROOT/'Outputs/dual_weapon_grip_placement/compositor.dwcp')
    ap.add_argument('--exe',type=Path,default=CLIENT/'2025-07-16_Ragexe_175220998_clientinfo_patched.exe')
    ap.add_argument('--output',type=Path,default=ROOT/'docs/evidence/dual-weapon-pixel-grips-execution-20260905.json')
    args=ap.parse_args();run(args.payload,args.exe,args.output)
