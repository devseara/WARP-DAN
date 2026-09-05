"""Execute the emitted x86 compositor against native-layout snapshots of real GRF resources.
This proves packet/resource selection and ABI behavior, not in-game visual acceptance.
"""
from __future__ import annotations
import argparse, configparser, hashlib, json, struct, sys, zlib
from pathlib import Path
sys.dont_write_bytecode=True
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr
from dual_weapon_formats.grf_reader import GrfFile

ROOT=Path(__file__).resolve().parents[1]
PREFIX="data/sprite/인간족/어세신/어세신_여_"
PAIR_NAMES={25:"단검_단검",26:"검_검",27:"도끼_도끼",28:"단검_검",29:"단검_도끼",30:"검_도끼"}
NAMES={1:("1238",34),2:("13412",45),6:("도끼",6)}
PAIRS=[(25,1,1),(26,2,2),(27,6,6),(28,2,1),(28,1,2),(29,6,1),(29,1,6),(30,6,2),(30,2,6)]

class Resources:
    def __init__(self,client):
        self.client=client; self.grfs=[]; self.evidence={}
        ini=configparser.ConfigParser(); ini.read(client/"DATA.INI")
        self.paths=[client/v for k,v in sorted(ini["Data"].items(),key=lambda kv:int(kv[0]))]
    def read(self,name):
        key=PREFIX+name
        loose=self.client/Path(key)
        source=None; data=None
        if loose.is_file(): data=loose.read_bytes(); source=str(loose)
        else:
            for i,path in enumerate(self.paths):
                if len(self.grfs)<=i: self.grfs.append(GrfFile(path))
                data=self.grfs[i].read(key.lower())
                if data is not None: source=str(path); break
        if data is None: raise FileNotFoundError(key)
        self.evidence[key]={"source":source,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        return data

class Machine:
    def __init__(self,resources,payload=None,native_layout=True):
        self.native_layout=native_layout
        self.u=Uc(UC_ARCH_X86,UC_MODE_32)
        self.u.mem_map(0x100000,0x3000000)
        self.next=0x800000; self.resources=resources; self.loaded={}
        self.draw=0x110000; self.stop=0x110100; self.calls=[]
        self.u.mem_write(self.draw,b"\xC2\x18\x00"); self.u.mem_write(self.stop,b"\xCC")
        blob=(payload or ROOT/"Inputs/DualWeaponRuntime/compositor.dwcp").read_bytes()
        magic,version,size,entry,n,rigsize,gripsize,crc=struct.unpack_from("<8I",blob)
        assert magic==0x50435744 and version==1 and zlib.crc32(blob[32:])==crc
        begin=32+n*4; self.code=0x200000
        data=bytearray(blob[begin:])
        for off in struct.unpack_from("<"+"I"*n,blob,32):
            value,=struct.unpack_from("<I",data,off)
            struct.pack_into("<I",data,off,self.code+value)
        self.u.mem_write(self.code,bytes(data)); self.entry=self.code+entry
        self.actor=self.alloc(0x600); self.registry=self.alloc(60*256); self.views=self.alloc(8*256)
        self.slot=self.alloc(28); self.ctx=self.alloc(21*4); self.packet=self.alloc(64)+4
        self.w(self.actor+0x4ac,self.slot,self.slot+28)
        context=[self.registry,0xdead0000,0,0,0,0x38,0x3c,256,0,0,0,0x440,0x444,0,0,0,0,
                 self.code+size,self.views,0,self.code+size+rigsize]
        self.w(self.ctx,*context)
        self.row=self.registry+((self.actor>>4)&255)*60
        self.viewrow=self.views+((self.actor>>4)&255)*8
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def alloc(self,n):
        addr=self.next; self.next=(addr+n+15)&~15
        assert self.next<0x2000000
        return addr
    def w(self,addr,*v): self.u.mem_write(addr,struct.pack("<"+"I"*len(v),*(x&0xffffffff for x in v)))
    def r(self,addr): return struct.unpack("<I",self.u.mem_read(addr,4))[0]
    def hook(self,uc,address,size,_):
        if address==self.stop: uc.emu_stop()
        elif address==self.draw:
            esp=uc.reg_read(UC_X86_REG_ESP)
            pkt,pal,a3,a4,a5,a6=struct.unpack("<6I",uc.mem_read(esp+4,24))
            self.calls.append({"actor":uc.reg_read(UC_X86_REG_ECX),"palette":pal,
                               "packet":struct.unpack("<6fIf3II",uc.mem_read(pkt,48)),
                               "image":self.r(pkt+44)})
    def load(self,name):
        if name in self.loaded: return self.loaded[name]
        act=parse_act(self.resources.read(name+".act")); spr=Spr(self.resources.read(name+".spr"))
        bitmaps={kind:[im for im in spr.images if im.is_indexed==(kind==0)] for kind in (0,1)}
        sa=self.alloc(0x530); aa=self.alloc(0x140); actions=self.alloc(12*len(act["actions"]))
        # CResource's inline CP949 filename is part of the native family guard.
        for address,extension in ((sa,'.spr'),(aa,'.act')):
            path=(PREFIX.removeprefix('data/').replace('/','\\')+name+extension).encode('cp949')+b'\0'
            assert len(path)<=0xf0
            self.u.mem_write(address+0x14,path)
        self.w(aa+0x110,actions,actions+12*len(act["actions"]))
        layers={}
        for ai,action in enumerate(act["actions"]):
            frames=self.alloc(68*len(action.frames))
            self.w(actions+ai*12,frames,frames+68*len(action.frames),frames+68*len(action.frames))
            for fi,frame in enumerate(action.frames):
                lb=self.alloc(36*len(frame.layers))
                self.w(frames+fi*68+32,lb,lb+36*len(frame.layers),lb+36*len(frame.layers),len(frame.layers))
                for li,l in enumerate(frame.layers):
                    x,y=l.x,l.y
                    if self.native_layout and 0<=l.sprite_index<len(bitmaps[l.sprite_type]):
                        im=bitmaps[l.sprite_type][l.sprite_index]
                        x-=(im.width+1)//2; y-=(im.height+1)//2
                    self.u.mem_write(lb+36*li,struct.pack("<4iI2f2i",x,y,l.sprite_index,l.mirror,
                                    int.from_bytes(bytes(l.color),"little"),l.scale_x,l.scale_y,l.rotation,l.sprite_type))
                if self.native_layout and frame.anchors:
                    ab=self.alloc(12*len(frame.anchors))
                    for ai2,anchor in enumerate(frame.anchors):self.w(ab+ai2*12,*anchor)
                    self.w(frames+fi*68+0x34,ab,ab+12*len(frame.anchors),ab+12*len(frame.anchors),len(frame.anchors))
                if frame.layers: layers[(ai,fi)]=(lb,frame.layers[0])
        images={}; image_addrs=[]
        for kind in [0,1]:
            subset=[im for im in spr.images if im.is_indexed==(kind==0)]
            vec=self.alloc(4*len(subset))
            self.w(sa+0x510+kind*12,vec,vec+4*len(subset),vec+4*len(subset))
            for i,im in enumerate(subset):
                ptr=self.alloc(16)
                self.u.mem_write(ptr,struct.pack("<HHIII",im.width,im.height,0,0,0))
                self.w(vec+i*4,ptr);images[(kind,i)]=(ptr,im);image_addrs.append(ptr)
        result=dict(spr=sa,act=aa,parsed=act,layers=layers,images=images,image_addrs=image_addrs,name=name,native_normalized=self.native_layout)
        self.loaded[name]=result
        return result
    def equip(self,pair,main,off,off_only=False):
        m=self.load(NAMES[main][0]); o=self.load(NAMES[off][0])
        stock_name=PAIR_NAMES[pair] if not off_only else {1:"단검",2:"검",6:"도끼"}[off]
        stock=self.load(stock_name)
        trail=self.load(stock_name+"_검광")
        self.w(self.slot+20,stock["spr"],trail["spr"])
        self.w(self.row,self.actor,0 if off_only else m["spr"],0 if off_only else m["act"],0,0,
               o["spr"],o["act"],0,0,stock["act"],trail["act"],pair,0 if off_only else main,off,0)
        self.w(self.viewrow,0 if off_only else NAMES[main][1],NAMES[off][1])
        self.w(self.actor+0x440,0 if off_only else 1001,1002)
        return m,o,stock,trail
    def invoke(self,resource,action,frame,foreign_palette=False,frame_wrap=False):
        self.calls=[]
        actual_frame=0 if frame_wrap and (action,frame) not in resource["layers"] else frame
        info=resource["layers"].get((action,actual_frame))
        if not info: return None
        _,l=info; image=resource["images"].get((l.sprite_type,l.sprite_index))
        if not image: return None
        ptr,im=image
        if self.native_layout:
            # Verified independently against all C40C20 instructions in
            # verify_dual_weapon_native_projection.py; unit-scale fixture.
            nx,ny=struct.unpack('<2i',self.u.mem_read(info[0],8))
            left=400+(nx+(im.width if l.mirror else 0))*l.scale_x
            right=400+(nx+(0 if l.mirror else im.width))*l.scale_x+1
            top=300+ny*l.scale_y;bottom=300+(ny+im.height)*l.scale_y+1
        else:
            # Historical synthetic fixture, retained only for isolated old
            # regressions. It is not native geometry or placement evidence.
            cx=400+l.x;cy=300+l.y;w=im.width*l.scale_x;h=im.height*l.scale_y
            left=cx-w/2;right=cx+w/2;top=cy-h/2;bottom=cy+h/2
        packet=struct.pack("<6fIf3II",top,left,bottom,right,0.5,0.5,
                           0xffffffff,float(l.rotation),0,0,0,ptr)
        self.u.mem_write(self.packet,packet)
        self.w(self.actor+0x38,action,frame)
        esp=0x2f00000
        args=[self.stop,self.actor,self.packet,resource["spr"]+0x110+(4 if foreign_palette else 0),
              0x123,0,0,0x456,self.ctx,self.draw]
        self.w(esp,*args)
        regs=[UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP]
        for i,reg in enumerate(regs): self.u.reg_write(reg,0x777000+i*16)
        self.u.reg_write(UC_X86_REG_ESP,esp)
        self.u.emu_start(self.entry,self.stop,count=1000000)
        assert self.u.reg_read(UC_X86_REG_EIP)==self.stop,"did not return"
        assert self.u.reg_read(UC_X86_REG_ESP)==esp+40,"stdcall stack"
        for i,reg in enumerate(regs): assert self.u.reg_read(reg)==0x777000+i*16,"callee-save register"
        assert bytes(self.u.mem_read(self.packet,48))==packet,"input packet mutated"
        return self.u.reg_read(UC_X86_REG_EAX)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=ROOT/"docs/evidence/dual-weapon-resource-fix-20260905.json")
    args=parser.parse_args()
    resources=Resources(args.client); m=Machine(resources)
    results=[]; failures=[]; examples=[]
    for pair,mt,ot in PAIRS:
        main,off,stock,trail=m.equip(pair,mt,ot)
        counts={"pair":pair,"main_type":mt,"off_type":ot,"packets":0,"handled":0,"draws":0,"stock":0}
        for actionbase,frames in [(32,6),(88,8)]:
            for d in range(8):
                for frame in range(frames):
                    for channel,res in [(5,stock),(6,trail)]:
                        result=m.invoke(res,actionbase+d,frame,frame_wrap=True)
                        if result is None: continue
                        counts["packets"]+=1;counts["handled"]+=bool(result);counts["draws"]+=len(m.calls)
                        if not result:
                            counts["stock"]+=1; failures.append([pair,mt,ot,actionbase+d,frame,channel])
                        if d==0 and frame==0 and m.calls:
                            example={"pair":pair,"main_type":mt,"off_type":ot,"action":actionbase,"channel":channel,"hands":[]}
                            for call in m.calls:
                                owner=main if call["palette"]==main["spr"]+0x110 else off
                                logical=next(key for key,value in owner["images"].items() if value[0]==call["image"])
                                pkt=call["packet"]
                                example["hands"].append({"sprite_resource":owner["name"],"kind":logical[0],"sprite_index":logical[1],
                                    "center_relative_to_actor":[(pkt[1]+pkt[3])/2-400,(pkt[0]+pkt[2])/2-300],
                                    "rotation_degrees":pkt[7],"mirror":pkt[3]<pkt[1]})
                            examples.append(example)
                        for call in m.calls:
                            assert call["actor"]==m.actor
                            assert call["image"] in main["image_addrs"]+off["image_addrs"],"generic sprite leaked"
                            assert call["palette"] in [main["spr"]+0x110,off["spr"]+0x110],"wrong palette"
        assert counts["stock"]==0 and counts["handled"]==144, counts
        assert counts["draws"]==(208 if pair in (25,28) else 224), counts
        results.append(counts)
    main,off,stock,trail=m.equip(25,1,1,off_only=True)
    off_only=[]
    for d in range(8):
        for frame in range(6):
            result=m.invoke(stock,32+d,frame,frame_wrap=True)
            if result is not None:
                off_only.append([d,frame,result,len(m.calls)])
                if result:
                    assert len(m.calls)==1 and m.calls[0]["image"] in off["image_addrs"]
    assert len(off_only)==48 and all(x[2:]==[1,1] for x in off_only)
    off_attack=0
    for d in range(8):
        for frame in range(9):
            result=m.invoke(stock,80+d,frame,frame_wrap=True)
            if result is not None:
                assert result==1 and len(m.calls)==1
                assert m.calls[0]["image"] in off["image_addrs"]
                off_attack+=1
    # Fail the SECOND hand after the first hand could be prepared. Neither draws.
    main,off,stock,trail=m.equip(28,2,1)
    layer_addr=off["layers"][(32,0)][0]
    old=m.r(layer_addr+8)
    m.w(layer_addr+8,0xffffffff)
    assert m.invoke(stock,32,0)==0 and not m.calls
    m.w(layer_addr+8,old)
    assert m.invoke(stock,32,0)==1 and len(m.calls)==2
    for call in m.calls:
        owner=main if call["palette"]==main["spr"]+0x110 else off
        assert call["image"] in owner["image_addrs"], "image/palette crossed between hands"
    # Same-item duals share resources but must still produce separate hand packets.
    main,off,stock,trail=m.equip(25,1,1)
    assert m.invoke(stock,32,0)==1 and len(m.calls)==2
    assert m.calls[0]["packet"][:4]!=m.calls[1]["packet"][:4], "same-item hands collapsed"
    # Foreign packet ownership and stale capture must never trigger a replacement.
    m.equip(25,1,1)
    stock=m.load(PAIR_NAMES[25])
    assert m.invoke(stock,32,0,foreign_palette=True)==0 and not m.calls
    report={"payload_sha256":hashlib.sha256((ROOT/"Inputs/DualWeaponRuntime/compositor.dwcp").read_bytes()).hexdigest(),
            "method":"Unicorn x86; real GRF SPR/ACT data expanded to profiled native layouts; native draw intercepted",
            "visual_acceptance":False,"examples":examples,"pairs":results,"stock_fallback_cells":failures,
            "off_only":off_only,"off_only_attack_packets":off_attack,"resources":resources.evidence,
            "assertions":["callee-save registers","RET 36 stack balance","input packet unchanged",
                          "emitted image belongs to retained original SPR","palette belongs to same retained SPR",
                          "foreign palette rejected","stale capture pointer never read","second-hand failure emits zero custom draws","same-item resources produce distinct hand packets","image/palette identity remains paired"]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"pairs":results,"off_only_handled":sum(x[2] for x in off_only),"off_only_packets":len(off_only),
                      "fallback_count":len(failures)},indent=2))
if __name__=="__main__": main()
