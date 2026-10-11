"""Emitted-code regressions for paired description ownership and movement."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_item_description_native import VM,WIN,ITEM,PIXELS,HITS,LINES
from verify_item_description_edges import long_response
from generate_item_description_data import inline_grade_effects,grade_integer

COMP=0x50102000;COMP_SURFACE=0x50201000;COMP_PIXELS=0x50480000;GAP=8
class DualVM(VM):
    def __init__(self,pe,m):
        self.paint_ids=[]
        super().__init__(pe,m)
        self.comparison=m['comparisonState']['vir'];self.second_bar=self.comparison+119344
        self.write32(COMP,0x1032c5c);self.write32(COMP+0x1f8,0xea);self.u.mem_write(COMP+0x28,b'\1')
        head=0x50120000;first=head+32;second=head+64
        for a,v in [(head,[first,second,0]),(first,[second,head,0x50120200]),(second,[head,first,0x50120400])]:self.u.mem_write(a,struct.pack('<3I',*v))
        self.write32(COMP+0x50,head)
        for child in [0x50120200,0x50120400]:self.write32(child+0x10,COMP);self.u.mem_write(child+0x28,b'\1')
        self.write32(COMP+0x208,0x50120400);self.set_size(COMP,[280,144])
        self.stub(0x874af0,8,self.position)
        for slot,addr in enumerate(m['comparisonOriginal']):
            if slot in [0,4,19,20,25,28,31,32,35,37]:self.stub(addr,{0:4,4:8,19:0,20:0,25:8,28:8,31:8,32:8,35:4,37:24}[slot],self.original(slot))
    def c(self,offset):return self.read32(self.comparison+offset)
    def original(self,slot):
        base=super().original(slot)
        def call(ecx,args):
            if slot==20:self.paint_ids.append((ecx,self.read32(ecx+0x1f8)))
            if slot==4 and ecx==WIN:
                self.position(ecx,args)
                # Exact stock defect: native main SetPos subtracts its own width.
                if hasattr(self,'comparison') and self.read32(self.comparison):self.position(COMP,[args[0]-self.read32(WIN+0x14),args[1]])
            return base(ecx,args)
        return call
    def position(self,ecx,args):self.write32(ecx+0x1c,args[0]);self.write32(ecx+0x20,args[1]);return 0
    def with_scroll(self,ecx,args,fn):
        old=(self.scrollbar,self.scroll_surface,self.scroll_pixels)
        if ecx==getattr(self,'second_bar',0):self.scrollbar,self.scroll_surface,self.scroll_pixels=self.second_bar,0x50708000,0x50709000
        try:return fn(ecx,args)
        finally:self.scrollbar,self.scroll_surface,self.scroll_pixels=old
    def scroll_ctor(self,ecx,args):return self.with_scroll(ecx,args,super().scroll_ctor)
    def scroll_dtor(self,ecx,args):return self.with_scroll(ecx,args,super().scroll_dtor)
    def scroll_clear(self,ecx,args):return self.with_scroll(ecx,args,super().scroll_clear)
    def scroll_fill(self,ecx,args):return self.with_scroll(ecx,args,super().scroll_fill)
    def scroll_blit(self,ecx,args):return self.with_scroll(ecx,args,super().scroll_blit)
    def set_size(self,ecx,args):
        if ecx==getattr(self,'second_bar',0):return self.with_scroll(ecx,args,super().set_size)
        if ecx==COMP:
            w,h=args;self.write32(ecx+0x14,w);self.write32(ecx+0x18,h);self.write32(ecx+0x24,COMP_SURFACE)
            self.write32(COMP_SURFACE+4,w);self.write32(COMP_SURFACE+0x18,COMP_PIXELS)
            self.u.mem_write(COMP_PIXELS,b'\xff'*(w*h*4)+b'\xcd'*64);return 0
        return super().set_size(ecx,args)
    def open_pair(self):
        self.open(itemid=2315,index=7);right=self.response()
        # Comparison factory receives an equipped CItem from native inventory lookup.
        self.u.mem_write(ITEM+0x2c,b'2301\0');self.write32(ITEM+4,9)
        self.u.mem_write(ITEM+0x88,struct.pack('<H',3))
        self.run('Message',[0,24,ITEM,1,0,0],ecx=COMP);left=self.response()
        assert struct.unpack_from('<I',right,12)[0]&0x80000000==0
        assert struct.unpack_from('<I',left,12)[0]&0x80000000
        return right,left
def long_for(v,request):
    saved=v.sent;v.sent=[request]
    try:return long_response(v)
    finally:v.sent=saved
def set_text(data,row,text):
    off=128+row*192+64;data[off:off+128]=text.encode().ljust(128,b'\0')

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    v=DualVM(pe,m);right,left=v.open_pair()
    # Both panes take their final geometry in the opening frame, before any reply.
    assert v.s('ready') and v.c(12) and v.read32(WIN+0x14)==360 and v.read32(COMP+0x14)==360
    set_text(left,0,'30');assert v.receive(left)==1 and v.receive(right)==1
    assert v.s('ready') and v.c(12) and not v.s('loading') and not v.c(119528)
    assert v.read32(v.state+176+24)==2315 and v.read32(v.comparison+176+24)==2301
    for x,y in [(600,80),(10,90),(5000,5000),(-500,-500)]:
        v.run('Position',[x,y]);lx=v.read32(COMP+0x1c);rx=v.read32(WIN+0x1c)
        assert lx+v.read32(COMP+0x14)+GAP==rx and v.read32(COMP+0x20)==v.read32(WIN+0x20)
        assert rx+v.read32(WIN+0x14)<=1024 and lx>=0
    v.draws=[];v.run('Draw');main_draws=list(v.draws);v.run('Draw',ecx=COMP)
    assert (COMP,12) in v.paint_ids and v.read32(COMP+0x1f8)==0xea
    assert any(text=='(-13)' for _,_,text,*_ in main_draws),'candidate Base ATK delta against the equipped pane'
    assert not any(text.startswith('(') for _,_,text,*_ in v.draws[len(main_draws):]),'equipped pane carries no delta'
    checks=['independent candidate/equipped requests, out-of-order snapshots, final geometry in the opening frame',
        'paired panes keep an 8px gap with viewport clamping; candidate stat deltas compare against the equipped pane',
        'comparison uses normal header skin branch and restores native ID']
    # Long bodies: each pane owns its native scrollbar and scroll state.
    v=DualVM(pe,m);v.open_pair();main_request,comparison_request=v.sent[-2],v.sent[-1]
    left,right=long_for(v,comparison_request),long_for(v,main_request)
    assert v.receive(left)==1 and v.receive(right)==1;v.run('Draw');v.run('Draw',ecx=COMP)
    assert v.read32(v.scrollbar)==0x102aef4 and v.read32(v.second_bar)==0x102aef4
    before=v.s('scroll');v.run('Wheel',[-120],ecx=COMP);assert v.s('scroll')==before and v.c(36)>0
    # A stale equipped-item notice reinspects that pane only; the candidate is untouched.
    sent=len(v.sent);stale=bytearray(left);struct.pack_into('<I',stale,20,2);struct.pack_into('<H',stale,38,0)
    assert v.receive(stale)==1 and v.c(12) and v.c(119528) and v.s('ready') and not v.s('loading')
    v.now+=200;v.run('Process',ecx=COMP);assert len(v.sent)==sent+1 and struct.unpack_from('<I',v.sent[-1],12)[0]&0x80000000
    v.run('Position',[700,50]);assert v.read32(COMP+0x1c)+360+GAP==v.read32(WIN+0x1c)
    # Closing the candidate leaves the equipped pane intact.
    v.run('Message',[0,5,0,0,0,0]);assert not v.s('ready') and not v.s('owner') and v.c(12)
    assert v.read32(WIN+0x14)==280 and v.read32(COMP+0x14)==360
    # New comparison response after close is rejected without accessing its window.
    v.run('Destroy',[0],ecx=COMP);assert not v.c(0);assert v.receive(left)==0
    checks.append('per-pane scrollbars, stale reinspection, independent close, destructor and stale-reply safety')
    v=DualVM(pe,m);right,left=v.open_pair();v.receive(right);v.receive(left)
    v.run('Draw');v.run('Draw',ecx=COMP)
    for w,pixels in [(WIN,PIXELS),(COMP,COMP_PIXELS)]:
        assert bytes(v.u.mem_read(pixels+v.read32(w+0x14)*v.read32(w+0x18)*4,64))==b'\xcd'*64
    # Slot-by-slot layout: each effect stays inside its own card panel.
    t=VM(pe,m);t.open();data=t.response();data[128:]=bytes(len(data)-128)
    rows=[(8,2,4001,1,'Slot 1','Installed card'),(8,1,0,1,'','LUK +2; Perfect Dodge +1'),
          (8,2,4002,2,'Slot 2','Installed card'),(8,1,0,2,'','DEX +1'),(8,2,0,3,'Slot 3','Empty')]
    for i,(section,kind,id,slot,label,text) in enumerate(rows):
        off=128+i*192;struct.pack_into('<HHIHH',data,off,section,kind,id,8 if kind==2 and not id else 0,slot)
        data[off+16:off+16+len(label)]=label.encode();data[off+64:off+64+len(text)]=text.encode()
    struct.pack_into('<H',data,38,len(rows));struct.pack_into('<H',data,40,2)
    assert t.receive(data)==1;t.run('Draw');assert t.s('hits')==2
    lines=[struct.unpack('<iiBBh192s',t.u.mem_read(t.state+LINES+i*204,204)) for i in range(t.s('lines'))]
    plain=[(y,row,kind,text.split(b'\0')[0].decode()) for y,row,kind,style,x,text in lines]
    assert [x[3] for x in plain if x[2]==3]==['Item','Item']
    subs=[x[3] for x in plain if x[2]==2]
    assert 'Slot 1  -  Installed card' in subs and 'Slot 2  -  Installed card' in subs and 'Slot 3  Empty' in subs
    hits=[struct.unpack('<5i',t.u.mem_read(t.state+HITS+i*20,20)) for i in range(2)]
    effect1=next(x for x in plain if 'LUK +2' in x[3]);effect2=next(x for x in plain if x[3]=='DEX +1')
    assert effect1[2]==effect2[2]==2
    assert hits[0][1]<effect1[0]<hits[0][1]+hits[0][3] and hits[1][1]<effect2[0]<hits[1][1]+hits[1][3]
    stock=DualVM(pe,m);stock.run('Message',[0,34,0,0,0,0],ecx=COMP)
    assert any(slot==37 and receiver==COMP and args[1]==34 for slot,receiver,args in stock.native_calls)
    checks.append('both surfaces stay in bounds; each slot has one card panel holding its own effects')
    # Formula translation is intentionally restricted; no dynamic script evaluation.
    script='bonus bDex,3;\n.@g = getenchantgrade();\nif (.@g > 0) bonus bLongAtkRate, .@g;'
    effects,remaining=inline_grade_effects(script,{})
    assert [e['Text'] for e in effects]==[f'Ranged physical damage +{n}%' for n in range(1,6)]
    assert 'bonus bDex,3;' in remaining and 'if (' not in remaining
    assert grade_integer('-.@g/2',3)==-1
    for expr in ['getrefine()','__import__("os")','2**8','.@g << 2']:
        try:grade_integer(expr,3)
        except (ValueError,SyntaxError):pass
        else:raise AssertionError('Unsafe formula accepted')
    checks.append('Apple of Archer grade formula translated without executing scripts')
    report={'passed':True,'checks':checks,'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'comparison-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
