"""Execute TradeUI x86, stock trade messages and real native input insertion.

Graphics/font/database/OS boundaries are explicit doubles. PNG pixels come from
the shipped assets. This is offline evidence, not live two-player acceptance.
"""
import argparse,struct,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_EDX,UC_X86_REG_ECX
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine
from test_shop_ui import ShopMachine,NAMES
from test_vending_ui import VendingMachine

ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state construct create process draw down up move right drop destroy event editdraw editevent numeric format hit'.split()
class TradeMachine(Machine):
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    measure=ShopMachine.measure
    inputText=VendingMachine.inputText
    copy_bytes=VendingMachine.copy_bytes
    def __init__(self,exe,open_window=True):
        self.text_colors=[];super().__init__(exe,ROOT/'Assets/TradeUI')
        data=self.pe.get_memory_mapped_image();marker=data.index(b'TradeUI.v1\0');record=data.index(pack(self.base+marker))
        self.c={n:self.r(self.base+record+4+i*4) for i,n in enumerate(FIELDS)}
        self.mode=self.alloc(0x400);self.modeTable=self.alloc(80);self.modeHandler=self.alloc(16);self.w(self.mode,self.modeTable);self.w(self.modeTable+24,self.modeHandler)
        self.messages=[];self.drops=[];self.native_items=[];self.png_calls=[];self.missing=set();self.stockfallback=0
        self.stub(self.modeHandler,lambda:(self.messages.append(tuple(self.args(5))),self.ret(20)))
        self.stub(0xA75340,lambda:self.ret(0,self.mode));self.w(0x121333C,self.mode)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0xDBBC7F,lambda:self.ret(0));self.stub(0xDBBBD4,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_EAX)))
        # Run the original frame/exchange/control constructors and OnCreate.
        # Only resource pixels, surfaces, OS/font and external game state are doubles.
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:setattr(self,'stockfallback',self.stockfallback+1),begin=0x9cd970,end=0x9cd970)
        self.stub(0xA21C90,self.measure)
        self.stub(0x874AF0,self.position)
        self.stub(0xE07D7B,self.copy_bytes);self.stub(0xE07D4B,self.copy_bytes)
        self.stub(0xA4B760,self.focus);self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19c,self.args(1)[0]),self.ret(4)))
        self.stub(0xA482E0,self.release_capture)
        # Keep native GetText, OnDraw and slot55 text/caret layout executable.
        self.u.hook_del(self._machine_stubs.pop(0x824FC0))
        self.stub(0x529850,self.sprintf)
        self.stub(0xD589F0,lambda:self.ret(4,1))
        fn=self.alloc(16);self.w(0xFC1840,fn);self.stub(fn,self.atoll)
        self.stub(0xA33100,lambda:self.ret(0,self.r(0x131F4E8+0x1a0)))
        self.stub(0xA47B90,lambda:self.ret(4,self.obj if self.args(1)[0]==0x271b else 0))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        mode_state=self.alloc(32);self.stub(0xB1FAC0,lambda:self.ret(0,mode_state));self.stub(0xDBA744,lambda:self.ret(4,0))
        self.input=self.alloc(512);self.w(0x159B80C,self.input);self.inputText('')
        self.stub(0x8711A0,self.native_icon);self.stub(0x8972C0,self.native_name)
        self.stub(0x8BA250,lambda:(self.drops.append(('hover',tuple(self.args(2)))),self.ret(8)))
        self.stub(0x8BB400,lambda:(self.drops.append(('right',tuple(self.args(2)))),self.ret(8)))
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.png_calls.append(tuple(self.args(4))),begin=self.r(self.c['api']+16),end=self.r(self.c['api']+16))
        NAMES[1752]='Fire Arrow';self.real_icons={};ShopMachine.load_icons(self)
        self.obj=0
        if open_window:self.open_factory()
    def open_factory(self):
        # Real CUI factory, registration lookup and exchange allocation/constructor.
        # Calling Construct/Create directly missed the modern-only slot 53 call.
        factory=self.alloc(32);head=self.alloc(64);node=self.alloc(64)
        for off in (0,4,8):self.w(head+off,node);self.w(node+off,head)
        self.u.mem_write(head+13,b'\1');self.w(node+16,0x271b);self.w(factory+4,head)
        callback=self.alloc(16);table=self.alloc(16);self.w(callback,table);self.w(table+8,0x9c8f60);self.w(node+0x3c,callback)
        # Native display dimensions; texture/surface allocation remains a boundary.
        screen=self.alloc(64);self.w(screen+0x28,1024);self.w(screen+0x2c,768);self.w(0x12515f8,screen)
        self.factory=factory;self.factory_node=node
        self.invoke(0x9a8a20,factory,(0x271b,));self.obj=self.u.reg_read(UC_X86_REG_EAX)
        self.editor=self.r(self.obj+0xc0)
        assert self.obj and self.r(self.obj+0x2c)==0x271b
        assert self.r(self.c['state'])==self.obj and self.r(self.c['state']+20)==2
        assert (self.r(self.obj+20),self.r(self.obj+24))==(548,428)
        assert (self.r(self.obj+0x1c),self.r(self.obj+0x20))==(238,170)
        assert self.r(self.editor+0x10)==self.obj and self.r(0x131f4e8+0x1a0)==self.editor
        assert all(self.r(self.r(self.obj+off)+0x28)==0 for off in (0xb4,0xb8,0xbc,0x118))
    def load_texture(self,name):
        if name in self.missing:return 0
        # Original hidden BMP controls still need resource dimensions at creation.
        if name.endswith('.bmp'):
            if name not in self.textures:
                t=self.alloc(0x130);self.w(t+0x114,44);self.w(t+0x118,18);self.textures[name]=t
            return self.textures[name]
        old=self.assets;self.assets=old/('genericsui' if name.startswith(('ok_','cancel_')) else 'tradeui')
        try:return super().load_texture(name)
        finally:self.assets=old
    def setsize(self,obj,w,h):
        super().setsize(obj,w,h)
        if not hasattr(self,'surface_vtable'):
            self.surface_vtable=self.alloc(16);destroy=self.alloc(16);self.w(self.surface_vtable,destroy)
            self.stub(destroy,lambda:self.ret(4))
        self.w(self.r(obj+0x24),self.surface_vtable)
    def sprintf(self):
        dest,fmt,p=self.args(3);value=self.cstr(p).encode();self.u.mem_write(dest,value+b'\0');self.ret(0,len(value))
    def atoll(self):
        value=int(self.cstr(self.args(1)[0]) or 0);self.ret(0,value&0xffffffff);self.u.reg_write(UC_X86_REG_EDX,value>>32)
    def native_icon(self):
        x,y,item,_,_=self.args(5);obj=self.u.reg_read(UC_X86_REG_ECX);self.native_items.append((x,y,item));id=int(self.cstr(item+0x2c))
        pix,w,h=self.pixels(obj);im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        if id in self.real_icons:
            icon=self.real_icons[id].copy();px=icon.load()
            for yy in range(icon.height):
                for xx in range(icon.width):
                    if px[xx,yy][:3]==(255,0,255):px[xx,yy]=(0,0,0,0)
            im.alpha_composite(icon,(x+(32-icon.width)//2,y+(32-icon.height)//2))
        ImageDraw.Draw(im).text((x+19,y+20),str(self.r(item+0x10)),font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',10),fill='#627d96')
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(20)
    def native_name(self):
        x,y,item,_,_,_,_=self.args(7);obj=self.u.reg_read(UC_X86_REG_ECX);value=NAMES.get(int(self.cstr(item+0x2c)),'Fire Arrow')
        pix,w,h=self.pixels(obj);im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');ImageDraw.Draw(im).text((x,y-2),value,font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11),fill='#333333')
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(28)
    def rows(self,side,rows):
        head=self.r(self.obj+side);prev=head
        for id,amount in rows:
            p=self.alloc(0x100);self.w(prev,p);self.w(p+4,prev);self.w(p,head);item=p+8
            value=str(id).encode();self.u.mem_write(item+0x2c,value+b'\0');self.w(item+0x3c,len(value));self.w(item+0x40,15);self.w(item+0x10,amount);self.u.mem_write(item+0x5c,b'\1');prev=p
        self.w(head+4,prev);self.w(self.obj+side+4,len(rows))
    def click(self,x,y):self.invoke(self.c['down'],self.obj,(x,y));self.invoke(self.c['up'],self.obj,(x,y))
    def edited(self):
        self.invoke(self.c['process'],self.obj);p=self.input+0x34 if self.r(self.input+0x48)<16 else self.r(self.input+0x34);return self.cstr(p)
    def stock_factory(self):
        # Missing-artwork fallback executes the real modern constructor and the
        # stock factory continuation: SetID, slot53, persisted position/size and
        # child-theme propagation. Modern artwork setup alone is a boundary here.
        calls=[]
        def modern_init():
            w=self.u.reg_read(UC_X86_REG_ECX);calls.append(w);self.setsize(w,50,50)
            self.u.mem_write(w+0xb4,b'\1\1\0');self.u.mem_write(w+0xd4,b'\1');self.ret(0)
        self.stub(0x9c9090,modern_init)
        for offset,xy in [(12,(51,61)),(20,(80,90))]:
            head=self.alloc(32);node=self.alloc(32)
            for off in (0,4,8):self.w(head+off,node);self.w(node+off,head)
            self.u.mem_write(head+13,b'\1');self.w(node+16,0x271b)
            self.w(node+20,xy[0]);self.w(node+24,xy[1]);self.w(self.factory+offset,head)
        pt=self.alloc(16);self.w(0xfc1668,pt);self.stub(pt,lambda:self.ret(12,1))
        self.missing.add('bg.png');self.invoke(0x9a8a20,self.factory,(0x271b,));w=self.u.reg_read(UC_X86_REG_EAX)
        assert calls==[w] and self.stockfallback==1 and self.r(w)==0x10457d8
        assert self.r(w+0x2c)==0x271b and (self.r(w+0x1c),self.r(w+0x20))==(51,61)
        assert (self.r(w+20),self.r(w+24))==(80,90)
        # A different registered window must also take the stock branch, even
        # while a custom trade window exists. Dispatch keys on private vtable.
        self.w(self.factory_node+16,0x2701);self.invoke(0x9a8a20,self.factory,(0x2701,))
        other=self.u.reg_read(UC_X86_REG_EAX)
        assert calls==[w,other] and self.r(other+0x2c)==0x2701
        assert (self.r(other+20),self.r(other+24))==(50,50)
        assert self.r(self.c['state'])==self.obj
    def preview(self,path):
        self.texts=[];self.text_colors=[];self.png_calls=[];self.invoke(self.c['draw'],self.obj);pix,w,h=self.pixels(self.obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB')
        if not self.r(self.obj+0xcc) and not self.r(self.obj+0xd4):
            # Execute the editor renderer, then compose its actual child surface.
            # Do not hand-draw a number that could mask a native layout failure.
            self.invoke(self.c['editdraw'],self.editor);p,ew,eh=self.pixels(self.editor)
            child=Image.frombytes('RGBA',(ew,eh),bytes(self.u.mem_read(p,ew*eh*4)),'raw','BGRA').convert('RGB')
            im.paste(child,(self.r(self.editor+0x1c),self.r(self.editor+0x20)))
        im.save(path);return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=TradeMachine(args.exe);c=m.c;w=m.obj;s=c['state'];assert m.r(w)==m.r(c['api']+4) and (m.r(w+20),m.r(w+24))==(548,428)
    assert m.r(m.editor)==m.r(c['api']+8);m.w(0x15fba90,1000000000)
    for raw,expected in [('1000','1,000'),('10000','10,000'),('1000000','1,000,000'),('5555','5,555'),('1000000001','1,000,000,000'),('',''),('12a','')]:
        m.inputText(raw);assert m.edited()==expected,(raw,m.edited());assert m.edited()==expected,'duplicate insertion'
    m.inputText('12345');m.w(m.input+0x50,2);m.w(m.input+0x54,2);assert m.edited()=='12,345' and m.r(m.input+0x50)==2
    m.rows(0xe0,[(1752,15),(509,1)]);m.u.mem_write(w+0xf0,b'MANOKE\0');m.w(w+0x100,6);m.w(w+0x104,15);m.w(w+0x108,1);m.u.mem_write(w+0x10c,struct.pack('<h',255))
    m.inputText('1000000');m.preview(args.output/'trade-offering.png');assert len(m.native_items)==2
    # Native UIManager Enter -> private UIEdit event -> stock exchange message,
    # stock validation/clamp -> original GameMode actions 0x33 and 0x34.
    m.invoke(0xA2E270,0x131f4e8);assert m.messages[-2:]==[(0x33,0,1000000,0,0),(0x34,0,0,0,0)],m.messages
    before=len(m.messages);m.invoke(c['editevent'],m.editor,(0,0,0,0,0,0));m.click(30,393);m.click(270,393);assert len(m.messages)==before,'repeated confirmation/early Trade'
    # Execute the original incoming 0x00EC server-ready arm and its virtual
    # dispatch for both players, rather than simulating ready bits locally.
    m.u.mem_write(0x15e8198,struct.pack('<HB',0xec,0));m.invoke(0xca1d39,0);assert m.r(w+0xcc)==1 and m.r(w+0xc0)==0
    m.u.mem_write(0x15e8198,struct.pack('<HB',0xec,1));m.invoke(0xca1d39,0);assert m.r(w+0xd0)==1
    m.w(0x15ff5b0,1000000);m.w(0x15ff5b4,10000);m.preview(args.output/'trade-confirmed.png')
    assert any(p[2]==m.textures['bg_send_ok.png'] for p in m.png_calls);assert any(p[2]==m.textures['bg_receive_ok.png'] for p in m.png_calls)
    m.click(270,393);assert m.messages[-1]==(0x36,0,0,0,0);before=len(m.messages);m.click(270,393);assert len(m.messages)==before
    m.click(510,393);assert m.messages[-1]==(0x35,0,0,0,0)
    # Both columns, every row, native pointer identity and relocated hit mapping.
    for row in range(10):
        for x,expected in [(30,30),(310,310)]:
            m.invoke(c['right'],w,(x,30+32*row));assert m.drops[-1]==('right',(expected,21+30*row))
    m.invoke(c['right'],w,(300,380));assert m.drops[-1]==('right',(0,0))
    # Single-item native drop enters original GameMode offer path. Stack drops
    # still open stock amount dialog through UIManager (explicit boundary).
    m.w(w+0xcc,0);m.w(w+0xd4,0);payload=m.alloc(32);m.w(payload,1);m.w(payload+16,1);m.w(m.mode+0x30c,7);m.w(m.mode+0x318,1)
    m.invoke(c['drop'],w,(60,70,payload));assert m.messages[-2:]==[(0x33,7,1,0,0),(0x12,0,0,0,0)]
    before=len(m.messages);m.invoke(c['drop'],w,(300,70,payload));assert len(m.messages)==before
    amount=m.alloc(0x100);vt=m.alloc(160);handler=m.alloc(16);m.w(amount,vt);m.w(vt+148,handler);opened=[]
    m.stub(0xA4BF30,lambda:(opened.append(tuple(m.args(2))),m.ret(8)));m.w(0x131f6d4,amount);m.stub(handler,lambda:(opened.append(tuple(m.args(6))),m.ret(24)))
    m.w(payload+16,15);m.invoke(c['drop'],w,(60,70,payload));assert opened==[(15,1),(0,13,5,0,0,0)],opened
    # Execute real background, GetText and slot55 text/caret placement. +B4 is Y.
    # Final GDI rendering remains a boundary that asserts text is inside surface.
    m.inputText('12345');m.w(w+0xc0,m.editor);m.w(0x131f4e8+0x1a0,m.editor);m.invoke(c['editdraw'],m.editor)
    assert m.r(m.editor+0xb4)==2 and any(t[0]=='12,345' and t[2]==2 for t in m.texts)
    m.stock_factory()
    lifecycle=TradeMachine(args.exe)
    for cycle in range(3):
        if cycle:lifecycle.open_factory()
        lifecycle.invoke(lifecycle.c['destroy'],lifecycle.obj,(1,))
        assert lifecycle.r(lifecycle.c['state'])==0 and lifecycle.r(lifecycle.c['state']+20)==0
    print('PASS TradeUI real factory/registration/allocation/frame/control initialization and repeated destruction/reopen, stock factory fallback/other-window isolation, native numeric Enter/OK actions, two-stage/repeat gates, server-ready overlays, native single/stack drag, all-row hit mapping, comma insertion/caret, 548x428 assets, stack/callee-save ABI. Live acceptance pending.')

if __name__=='__main__':main()
