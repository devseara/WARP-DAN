"""Execute actual stock-balloon icon x86 with explicit native boundary doubles."""
import argparse
from pathlib import Path
import re
import struct
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_chat_ui import Machine, pack

class StockMachine(Machine):
    def __init__(self, exe):
        self.stubs={}
        super().__init__(exe,Path('.'))
        data=self.pe.__data__
        pos=data.find(b'AnnouncementItemIcons.v1\0');assert pos>=0
        va=self.base+self.pe.get_rva_from_offset(pos)
        record=data.find(pack(va));assert record>=0
        _,self.payload,self.api,self.measure,self.height,self.draw,self.split=struct.unpack_from('<7I',data,record)
        self.rendered=[];self.requests=[];self.measures=[];self.lines=[];self.missing=False
        self.stub(0xA21A50,self.native_measure)
        self.stub(0xA21880,lambda:self.ret(24,12))
        self.stub(0xA27C20,self.native_draw)
        self.stub(self.r(self.api+8),self.resource)
        self.stub(0xA8D4A0,self.item_texture)
        self.stub(0x97A0B0,self.append)
        self.stub(0x979F10,lambda:self.forward('stock_split',0))
        self.obj=self.alloc(0xB4)
        self.setsize(self.obj,640,128)
        pix,w,h=self.pixels(self.obj)
        self.u.mem_write(pix,pack(0xFF5C5C5C)*(w*h))
        self.out=self.alloc(8)
        self.last_path=None

    def stub(self,address,fn):
        if address in self.stubs:self.u.hook_del(self.stubs[address])
        self.stubs[address]=self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:fn(),begin=address,end=address)

    def cstr(self,p):
        return bytes(self.u.mem_read(p,1024)).split(b'\0')[0].decode('latin1') if p else ''

    def string(self,s):
        p=self.alloc(len(s)+16);self.u.mem_write(p,s+b'\0');return p

    def span(self,p,n):
        return bytes(self.u.mem_read(p,n)).decode('latin1') if n else self.cstr(p)

    def native_measure(self):
        out,s,n,font,height,bold,italic=self.args(7)
        text=self.span(s,n);self.measures.append((text,font,height,bold,italic))
        self.w(out,len(text)*6);self.w(out+4,height or 12);self.ret(28,out)

    def native_draw(self):
        x,y,s,n,color,shadow,font,height,bold=self.args(9)
        self.rendered.append((self.span(s,n),x,y,color,shadow,font,height,bold))
        self.ret(36)

    def resource(self):
        item,identified=self.args(2);self.requests.append((item,identified))
        self.ret(8,0 if self.missing else self.string(b'known' if identified else b'unknown'))

    def item_texture(self):
        self.last_path=self.cstr(self.args(1)[0])
        tex=self.alloc(0x130);pix=self.alloc(24*24*4)
        self.u.mem_write(pix,pack(0xFF00FF)*(24*24))
        for y in range(2,22):
            for x in range(2,22):self.w(pix+(y*24+x)*4,0x00CC33)
        self.w(tex+0x114,24);self.w(tex+0x118,24);self.w(tex+0x11C,pix);self.ret(4,tex)

    def append(self):
        vector,start,end=self.args(3)
        self.lines.append(bytes(self.u.mem_read(start,end-start)));self.ret(0)

    def split_text(self,s,budget=72):
        self.lines=[]
        p=self.string(s);code=self.alloc(64)
        # cdecl adapter leaves the original caller responsible for 12 bytes.
        b=b'\x68'+pack(budget)+b'\x68'+pack(0)+b'\x68'+pack(p)+b'\xE8'+pack((self.split-code-20)&0xFFFFFFFF)+b'\x83\xC4\x0C\xC3'
        self.u.mem_write(code,b);self.invoke(code,0);return self.lines

    def show(self,s,x=5,y=7,height=12,color=0xFFFF):
        p=self.string(s)
        self.invoke(self.measure,self.obj,(self.out,p,0,0,height,0,0))
        size=(self.r(self.out),self.r(self.out+4))
        self.invoke(self.height,self.obj,(p,0,0,height,0,0))
        # Stub height is native 12 for plain cases. Tagged paths must agree.
        if b'^i[' in s:assert self.u.reg_read(UC_X86_REG_EAX)==size[1]
        self.invoke(self.draw,self.obj,(x&0xFFFFFFFF,y&0xFFFFFFFF,p,0,color,0x102030,0,height,0))
        return size

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');args=ap.parse_args()
    m=StockMachine(args.exe)
    # Producer calls, vtable, background, expiry and original queue untouched.
    for site in (0xCB8621,0xCB7943):assert m.r(site+1)+site+5 & 0xFFFFFFFF==0x788ED0
    for slot,target in [(19,0x789590),(20,0x789430),(41,0xA1CE10),(43,0x789320)]:
        assert m.r(0x101ADA4+slot*4)==target
    for site,target in [(0x7890DE,m.measure),(0x78922E,m.measure),(0x7894E2,m.draw),(0x789500,m.height),(0xCB84ED,m.split)]:
        assert (m.r(site+1)+site+5)&0xFFFFFFFF==target
    assert m.show(b'^i[909]Jellopy')==(20+7*6,18)
    assert m.requests==[(909,1)]
    assert m.rendered==[('Jellopy',25,10,0xFFFF,0x102030,0,12,0)]
    pix,w,h=m.pixels(m.obj)
    assert m.r(pix+(10*w+8)*4)==0xFF00CC33
    assert m.r(pix+(7*w+5)*4)==0xFF5C5C5C,'magenta transparency must retain stock background'
    assert m.last_path.endswith('item\\known.bmp')
    print('PASS: icon immediately before name; native font/color/shadow; measurement, alignment, transparency and x86 ABI')
    for s,expected in [(b'Plain broadcast',[]),(b'^i[1201,0]Dagger',[(1201,0)]),
                       (b'^i[1201,1]Knife',[(1201,1)]),(b'^i[501]Red ^i[502]Orange',[(501,1),(502,1)]),
                       (b'^i[0]bad ^i[10000000]bad ^i[42,2]bad ^i[',[])]:
        n=StockMachine(args.exe);n.show(s);assert n.requests==expected
        assert ''.join(t[0] for t in n.rendered)==re.sub(rb'\^i\[[1-9][0-9]{0,6}(?:,[01])?\]',b'',s).decode('latin1')
    n=StockMachine(args.exe);n.missing=True;n.show(b'^i[909]Jellopy')
    assert n.rendered[0][0]=='Jellopy'
    n=StockMachine(args.exe);assert n.show(b'^i[909]Jellopy',height=24)[1]==24
    n.show(b'^i[909]Jellopy',x=-10,y=-10)
    n.show(b'^i[909]Jellopy',x=638,y=127)
    print('PASS: missing art, multiple items, malformed IDs, identification, tall fonts and surface-edge clipping')
    n=StockMachine(args.exe)
    for pad in range(55,80):
        lines=n.split_text(b'A'*pad+b'^i[909]Jellopy tail')
        assert sum(line.count(b'^i[909]') for line in lines)==1
        assert b''.join(lines).replace(b' ',b'')==b'A'*pad+b'^i[909]Jellopytail'
        for line in lines:assert len(re.sub(rb'\^i\[[0-9]+\]',b'XXX',line))<=72
    assert n.split_text(b'^i[909]Jellopy\nsecond')==[b'^i[909]Jellopy',b'second']
    n.split_text(b'untagged');assert n.forwards[-1][0]=='stock_split'
    # Native locale character step must never cut a DBCS pair at a boundary.
    locale=n.alloc(32);vt=n.alloc(32);nextfn=n.alloc(16)
    n.w(0x159B80C,locale);n.w(locale,vt);n.w(vt+20,nextfn)
    n.stub(nextfn,lambda:n.ret(8,n.args(2)[0]+2))
    lines=n.split_text(b'^i[909]'+b'\xB0\xA1'*40)
    assert b''.join(lines)==b'^i[909]'+b'\xB0\xA1'*40
    assert all(len(line.replace(b'^i[909]',b''))%2==0 for line in lines)
    for i in range(100):
        n.split_text(b"Player got Monster's ^i[909]Jellopy (chance: 0.55%)")
    assert n.show(b'A'*1016+b'^i[909]')[1]==18
    # Over-limit/explicit partial counts use native fallback or bounded parsing.
    p=n.string(b'^i[909]Jellopy')
    n.requests=[];n.invoke(n.draw,n.obj,(0,0,p,4,1,2,0,12,0));assert not n.requests
    n.invoke(n.draw,n.obj,(0,0,n.string(b'X'*1024),0,1,2,0,12,0))
    print('PASS: tag-atomic wrapping, newlines, multibyte boundaries, bursts, long input and bounded explicit spans')
    # Execute real private resolver with native item lookup as the sole double.
    n=StockMachine(args.exe);resolver=n.r(n.api+8);n.u.hook_del(n.stubs.pop(resolver))
    manager=n.alloc(32);node=n.alloc(160);n.w(0x159C088,manager)
    n.stub(0xA7E780,lambda:n.ret(4,node))
    n.u.mem_write(node+0x1C,b'unknown\0');n.w(node+0x1C+20,15)
    name=n.string(b'long_identified_resource');n.w(node+0x58,name);n.w(node+0x58+20,31)
    n.invoke(resolver,0,(1201,0));assert n.cstr(n.u.reg_read(UC_X86_REG_EAX))=='unknown'
    n.invoke(resolver,0,(1201,1));assert n.cstr(n.u.reg_read(UC_X86_REG_EAX))=='long_identified_resource'
    n.w(0x159C088,0);n.invoke(resolver,0,(1201,1));assert n.u.reg_read(UC_X86_REG_EAX)==0
    print('PASS: real numeric item resolver, SSO/heap resources, stock producers/queue/timer/vtable retained')
    n=StockMachine(args.exe)
    # Execute the real stock balloon draw over its actual native rb-tree/list
    # structure, not just standalone render helpers. Two tagged rows must retain
    # the stock centered background, line gaps, and identical redraw positions.
    tree=n.alloc(32);group=n.alloc(32);messages=n.alloc(8);message=n.alloc(48)
    lines=n.alloc(8);first=n.alloc(40);second=n.alloc(40)
    n.w(n.obj+0x7C,tree);n.w(tree,group);n.u.mem_write(tree+13,b'\1')
    n.w(group,tree);n.w(group+4,tree);n.w(group+8,tree);n.w(group+20,messages)
    n.w(messages,message);n.w(message,messages);n.w(message+8,lines);n.w(message+12,2)
    n.w(message+32,12);n.w(message+40,94);n.w(message+44,48)
    n.w(lines,first);n.w(first,second);n.w(second,lines)
    for node,text in [(first,b'^i[909]Jellopy'),(second,b'^i[501]Red Potion')]:
        if len(text)<16:n.u.mem_write(node+8,text+b'\0');n.w(node+28,15)
        else:n.w(node+8,n.string(text));n.w(node+28,31)
        n.w(node+24,len(text));n.w(node+32,0xFFFF);n.w(node+36,0)
    boxes=[]
    def box():boxes.append(tuple(n.args(5)));n.ret(20)
    n.stub(0xA1D760,box)
    n.invoke(0x789430,n.obj)
    assert boxes==[(273,0,94,48,0xFF5C5C5C)]
    assert [(t[0],t[1],t[2]) for t in n.rendered]==[('Jellopy',299,7),('Red Potion',299,29)]
    before=list(n.rendered);n.rendered=[];n.invoke(0x789430,n.obj)
    assert n.rendered==before,'Original announcements must stay stationary'
    print('PASS: actual stock balloon draw, centered native background, two icon rows without overlap, stationary redraw')
    print('Offline tests passed. Native in-game appearance still needs user acceptance.')

if __name__=='__main__':main()
