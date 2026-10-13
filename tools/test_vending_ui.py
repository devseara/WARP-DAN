"""Execute emitted VendingUI x86 and native packet routing at read-only boundaries.

Uses original PNGs to render evidence; never connects to a server or trades items.
"""
import argparse
from io import BytesIO
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack, over
from test_gacha_ui import GachaMachine

FIELDS='api state receive hit draw down up move drag cursor destroy rightdown rightup wheel name resource identified format editdraw describe blockwalk switchshop route'.split()
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(r'D:/AAARAGNAROK/Banquet of Heroes/Eitr Origin')
TEXTURES=GAME/'data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º'
NAMES={611:'Magnifier',1750:'Arrow',501:'Red Potion',502:'Orange Potion',503:'Yellow Potion',506:'Green Potion',645:'Concentration Potion',656:'Awakening Potion',601:'Fly Wing',602:'Butterfly Wing',607:'Yggdrasil Berry',604:'Dead Branch',12214:'Convex Mirror',507:'Red Herb',504:'White Potion',505:'Blue Potion',509:'White Herb',510:'Blue Herb',713:'Empty Bottle',909:'Jellopy',984:'Oridecon',985:'Elunium',756:'Rough Oridecon',757:'Rough Elunium'}

def contract(m):
    b=m.pe.get_memory_mapped_image();marker=b.find(b'VendingUI.v1\0');assert marker>=0
    record=b.find(pack(m.base+marker));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

class VendingMachine(Machine):
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    def __init__(self,exe,assets):
        self.text_colors=[];super().__init__(exe,assets);self.c=contract(self)
        self.now=1000;self.sent=[];self.stock=[];self.described=[];self.key_codes=set();self.missing=set();self.png_calls=[];self.real_icons={}
        self.raised=[]
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.raised.append(self.args(1)[0]),begin=0xA39130,end=0xA39130)
        self.stub(0xA21C90,self.measure)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4));self.stub(0x86E240,lambda:self.ret(4))
        self.head=self.alloc(12);self.w(self.head,self.head);self.w(self.head+4,self.head)
        self.w(0x131F4E8+0x17c,self.head);self.w(0x131F4E8+0x180,0)
        self.stub(0xDBBC7F,lambda:self.ret(0));self.stub(0xA47B90,lambda:self.ret(4,0))
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19c,self.args(1)[0]),self.ret(4)))
        # Execute native drag start/move/release and coordinate conversion.
        self.stub(0xA23470,lambda:self.ret(8));self.stub(0xA764A0,lambda:self.ret(4))
        self.closed=[];self.mode=self.alloc(0x300);self.mode_vtable=self.alloc(64);self.close_handler=self.alloc(16)
        self.w(0x121333C,self.mode);self.w(self.mode,self.mode_vtable);self.w(self.mode_vtable+6*4,self.close_handler)
        self.stub(self.close_handler,lambda:(self.closed.append(tuple(self.args(5))),self.w(self.mode+0x24c,0),self.ret(20)))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        for addr in (0xCA10CA,0xCA10DB):self.stub(addr,lambda addr=addr:(self.stock.append(addr),self.ret(0)))
        api=self.c['api'];self.stub(self.r(api+8),lambda:self.ret(0,0x20200000));self.stub(self.r(api+12),self.send)
        self.stub(self.r(api+20),self.icon)
        self.stub(self.r(api+24),lambda:(self.described.append(self.args(1)[0]),self.ret(4)))
        self.stub(self.r(api+28),self.name)
        # Observe the PNG helper without replacing its emitted alpha compositor.
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.png_calls.append(tuple(self.args(4))),begin=self.r(api+32),end=self.r(api+32))
        keys=self.alloc(16);self.stub(keys,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.key_codes else 0));self.w(self.r(api+36),keys)
        clock=self.alloc(16);self.stub(clock,lambda:self.ret(0,self.now));self.w(0xFC17B0,clock)
        self.inventory([(2,12214,100),(3,604,11),(4,602,8),(5,607,12),(6,504,30),(7,505,18),(8,507,50),(9,1750,350),(10,601,24),(11,503,10),(12,509,15),(13,909,47)])
        self.load_icons()
        self.descriptionItems=[]
        self.stub(0x6A1B20,lambda:(self.u.mem_write(self.u.reg_read(UC_X86_REG_ECX),b'\0'*0xf8),self.ret(0)))
        self.stub(0x6A6570,lambda:(self.w(self.u.reg_read(UC_X86_REG_ECX)+0x2c,self.args(1)[0]),self.ret(4)))
        self.stub(0x5A4300,lambda:self.ret(0))
        self.descriptionWindow=self.alloc(0x100);table=self.alloc(160);self.w(self.descriptionWindow,table);event=self.alloc(16);self.w(table+37*4,event)
        self.stub(0xA39340,lambda:self.ret(4,self.descriptionWindow))
        self.stub(event,self.descriptionEvent)
        self.input=self.alloc(512);self.w(0x159B80C,self.input);self.inputText('')
        self.stub(0x817DA0,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_ECX)))
        self.stub(0xA1B780,lambda:self.ret(4));self.stub(0xA1CB70,lambda:self.ret(8))
        self.stub(0xA4B760,lambda:(self.w(0x131F4E8+0x1a0,self.args(1)[0]),self.ret(4)))
        self.stub(0x8303F0,lambda:(self.inputText(self.cstr(self.args(1)[0])),self.ret(4)))
        # Execute the REAL native selection deletion + insertion + std::string
        # code. The earlier replacement-style mock hid the duplicate-price bug.
        # Only external CRT byte copying remains an explicit boundary.
        self.stub(0xE07D7B,self.copy_bytes);self.stub(0xE07D4B,self.copy_bytes)
        self.stub(0x824FC0,lambda:self.ret(0))
        # Real UIManager Enter dispatch + UIEditCtrl event/clear code. Only
        # loading-state lookup and the external OS IME context are substituted.
        mode_state=self.alloc(32);self.stub(0xB1FAC0,lambda:self.ret(0,mode_state))
        self.stub(0xDBA744,lambda:self.ret(4,0))
        self.native_clears=[]
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.native_clears.append(a),begin=0xA70950,end=0xA70950)
    def copy_bytes(self):
        dest,source,count=self.args(3)
        if count:self.u.mem_write(dest,bytes(self.u.mem_read(source,count)))
        self.ret(0,dest)
    def descriptionEvent(self):
        item=self.args(6)[2];self.described.append(self.r(item+0x2c));self.descriptionItems.append(bytes(self.u.mem_read(item,0xf8)));self.ret(24)
    def inputText(self,text):
        self.u.mem_write(self.input+0x34,b'\0'*24)
        b=text.encode()+b'\0'
        if len(b)<=16:self.u.mem_write(self.input+0x34,b);self.w(self.input+0x48,15)
        else:p=self.alloc(len(b));self.u.mem_write(p,b);self.w(self.input+0x34,p);self.w(self.input+0x48,len(b))
        self.w(self.input+0x44,len(b)-1);self.w(self.input+0x50,len(b)-1);self.w(self.input+0x54,len(b)-1)
    def edited(self):
        self.invoke(self.c['editdraw'],self.r(self.c['state']+4))
        ptr=self.input+0x34 if self.r(self.input+0x48)<16 else self.r(self.input+0x34)
        return self.cstr(ptr)
    def inventory(self,items):
        self.slots={};head=self.alloc(12);previous=head
        for row in items:
            index,id,amount=row[:3];refine=row[3] if len(row)>3 else 0;identified=row[4] if len(row)>4 else 1
            node=self.alloc(0x110);self.w(previous,node);self.w(node+4,previous);self.w(node+12,index);self.w(node+8+0x10,amount);self.w(node+8+0x60,refine);self.u.mem_write(node+8+0x5c,bytes([identified]));self.slots[index]=node+8
            value=str(id).encode();self.u.mem_write(node+8+0x2c,value+b'\0');self.w(node+8+0x3c,len(value));self.w(node+8+0x40,15);previous=node
        self.w(previous,head);self.w(head+4,previous)
        self.w(0x15FA3C0+0x16f0,head);self.w(0x15FA3C0+0x16f4,len(items))
    def load_icons(self):
        import re
        from dual_weapon_formats.grf_reader import GrfFile
        data=(GAME/'SystemEN/itemInfo_iro.lua').read_bytes()
        grf=GrfFile(GAME/'update.grf')
        try:
            for id in NAMES:
                m=re.search(rb'\['+str(id).encode()+rb'\]\s*=\s*\{(.*?)(?=\r?\n\s*\[\d+\])',data,re.S)
                if not m:continue
                resource=re.search(rb'(?<!un)identifiedResourceName\s*=\s*"([^"]*)"',m[1])
                if not resource:continue
                key='data/texture/유저인터페이스/item/'+resource[1].decode('cp949').lower()+'.bmp'
                try:self.real_icons[id]=Image.open(BytesIO(grf.read(key))).convert('RGBA')
                except (KeyError,TypeError):pass
        finally:grf.close()
    def name(self):
        value=NAMES.get(self.args(2)[0],'Example item '+str(self.args(2)[0])).encode()+b'\0';ptr=self.alloc(len(value));self.u.mem_write(ptr,value);self.ret(8,ptr)
    def load_texture(self,name):
        if name in self.missing:return 0
        old=self.assets;self.assets=old/('genericsui' if name.startswith(('cancel_','ok_')) else 'marketui')
        try:return super().load_texture(name)
        finally:self.assets=old
    def measure(self):
        ptr,length,_,height,bold,_=self.args(6);font=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf',height)
        self.ret(24,int(font.getlength(self.cstr(ptr)[:length])))
    def icon(self):
        obj,id,x,y=self.args(4);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        if id in self.real_icons:
            icon=self.real_icons[id].copy();px=icon.load()
            for yy in range(icon.height):
                for xx in range(icon.width):
                    if px[xx,yy][:3]==(255,0,255):px[xx,yy]=(0,0,0,0)
            im.alpha_composite(icon,(x+(32-icon.width)//2,y+(32-icon.height)//2))
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(16)
    def send(self):
        length,ptr=self.args(2);self.sent.append(bytes(self.u.mem_read(ptr,length)));self.ret(8)
    def receive(self,p):
        self.w(self.mode+0x24c,1)
        self.u.mem_write(0x15E8198,bytes(p));op=struct.unpack_from('<H',p)[0]
        self.invoke(self.r(0xCAA2E0+(op-0x73)*4),0)
    def click(self,x,y):
        obj=self.r(self.c['state']);self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def drag_item(self,x,y,dx,dy):
        obj=self.r(self.c['state']);self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['drag'],obj,(dx,dy));self.invoke(self.c['up'],obj,(dx,dy))
    def amount_click(self,x,y):
        obj=self.state(15032);assert obj and self.state(15040)
        self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def enter(self):
        self.invoke(0xA2E270,0x131F4E8)
    def choose(self,x,y,amount=1):
        mode=struct.unpack('<H',self.u.mem_read(self.c['state']+86,2))[0]
        assert mode in (2,4)
        self.drag_item(x,y,100 if mode==2 else 450,160 if mode==2 else 200)
        if self.state(15040):self.inputText(str(amount));self.amount_click(185,154)
    def confirm_click(self,x,y):
        obj=self.state(14220);assert obj and self.state(14212)
        self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def preview(self,path=None):
        self.texts=[];self.text_colors=[];self.png_calls=[];obj=self.r(self.c['state']);self.invoke(self.c['draw'],obj);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB')
        for active,window in [(14212,14220),(15040,15032)]:
            if not self.state(active):continue
            dialog=self.state(window);self.invoke(self.c['draw'],dialog);pix,dw,dh=self.pixels(dialog)
            front=Image.frombytes('RGBA',(dw,dh),bytes(self.u.mem_read(pix,dw*dh*4)),'raw','BGRA')
            im.paste(front,(self.r(dialog+0x1c)-self.r(obj+0x1c),self.r(dialog+0x20)-self.r(obj+0x20)),front)
        if path:im.save(path)
        return im
    def move(self,x,y):self.invoke(self.c['move'],self.r(self.c['state']),(x,y))
    def state(self,offset):return self.r(self.c['state']+offset)


def snapshot(mode=2,count=12,currency=0,nonce=7,history=0,owner=2000001,shop=123):
    import ctypes as ct
    class Header(ct.LittleEndianStructure):
        _pack_=1
        _fields_=[('op',ct.c_uint16),('length',ct.c_uint16),('magic',ct.c_uint32),('version',ct.c_uint16),('mode',ct.c_uint16)]+[(n,ct.c_uint32) for n in ['nonce','owner','shop','currency','balance','max_price']]+[(n,ct.c_uint16) for n in ['max_slots','count','history_count','tax']]+[(n,ct.c_char*l) for n,l in [('title',80),('owner_name',24),('currency_name',48),('message',96)]]
    h=Header(0xbf3,292+64*count+40*history,0x49554e56,1,mode,nonce,owner,shop,currency,2000000000,1000000000,12,count,history,250,b'Eitr Market',b'Test Merchant',b'Zeny' if not currency else b'TCG Card',b'')
    assert ct.sizeof(h)==292
    ids=[12214,1750,509,504,505,985,607,602,501,502,503,645]
    rows=[]
    for i in range(count):
        item,index,amount,price=ids[i%len(ids)],i+2,100,1000*(i+1)
        if mode==1:item,index,amount,price=[(0,0,1000000,0),(0,0xffffffff,5000,0),(7227,7227,20,0)][i]
        rows.append(struct.pack('<IIIIBBBB4I25s3s',item,index,amount,price,1,0,0,0,0,0,0,0,b'',b''))
    hist=[struct.pack('<IIII24s',505,i+1,10000,1777777777,b'Test Buyer') for i in range(history)]
    return bytes(h)+b''.join(rows)+b''.join(hist)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--assets',type=Path,default=ROOT/'Assets/VendingUI');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    m=VendingMachine(a.exe,a.assets);s=m.c['state'];c=m.c;rows=s+76+292;choices=rows+200*64+16*40
    # Both formatter and the native selection/insert routines execute real x86.
    for raw,wanted in [('5555','5,555'),('1000','1,000'),('10000','10,000'),('1000000','1,000,000'),('1,234,567','1,234,567'),('999999999999999999','1,000,000,000'),('',''),('0','0')]:
        p=m.alloc(256);q=m.alloc(256);m.u.mem_write(p,raw.encode()+b'\0');m.invoke(c['format'],0,(p,q,1000000000));assert m.cstr(q)==wanted,(raw,m.cstr(q))
    import re
    stock=int(re.search(r'original!==0x([0-9A-F]+)',(ROOT/'Scripts/Patches/VendingUI.qjs').read_text()).group(1),16)
    m.stub(stock,lambda:(m.stock.append(stock),m.ret(0)))
    m.receive(struct.pack('<HHI',0xbf3,8,0x11223344));assert m.stock==[stock] and not m.state(8);m.stock.clear()
    m.receive(snapshot(1,3));assert m.state(8)==1 and not m.stock;assert m.r(m.r(s)+0x2c)==0x3eb
    m.preview(a.output/'currency.png');surface=m.r(m.r(s)+0x24);assert m.u.mem_read(surface+0x28,1)==b'\x01';pix,_,_=m.pixels(m.r(s));assert m.r(pix)==0,'outside canopy must stay transparent'
    before=len(m.sent);m.click(230,195);assert len(m.sent)==before,'a currency row must only select'
    m.preview(a.output/'currency-selected.png');m.click(318,361)
    assert len(m.sent[-1])==32 and struct.unpack_from('<H',m.sent[-1],10)[0]==1 and struct.unpack_from('<I',m.sent[-1],16)[0]==7227
    # Stale release cannot select or submit twice.
    before=len(m.sent);m.click(318,361);assert len(m.sent)==before
    m.receive(snapshot());m.preview(a.output/'setup-empty.png')
    m.choose(437,185);assert m.state(20)==1
    m.click(80,189);assert m.state(56)==1
    m.inputText('')
    for ch in '5555':
        ptr=m.alloc(2);m.u.mem_write(ptr,ch.encode()+b'\0');m.invoke(0xA6EA10,m.input,(ptr,));m.edited()
    assert m.edited()=='5,555' and m.r(choices+8)==5555
    for _ in range(15):assert m.edited()=='5,555','redraw must not append digits'
    m.w(m.input+0x50,0);m.w(m.input+0x54,5);ptr=m.alloc(16);m.u.mem_write(ptr,b'1000000\0');m.invoke(0xA6EA10,m.input,(ptr,));assert m.edited()=='1,000,000'
    for raw,wanted in [('1000','1,000'),('10000','10,000'),('1000000','1,000,000')]:
        m.inputText(raw);assert m.edited()==wanted
    assert m.r(choices+8)==1000000
    m.inputText('12,345');m.w(m.input+0x50,2);m.w(m.input+0x54,5);assert m.edited()=='12,345';assert m.r(m.input+0x50)==2 and m.r(m.input+0x54)==5
    m.inputText('12345');m.w(m.input+0x50,2);m.w(m.input+0x54,5);assert m.edited()=='12,345';assert m.r(m.input+0x50)==2 and m.r(m.input+0x54)==6
    for i in range(1,10):m.choose(437+(i%4)*34,185+(i//4)*32)
    assert m.state(20)==10 and m.state(24)==70
    m.click(392,137);assert m.state(24)==0
    m.click(150,20);m.inputText('My comma store');m.edited();m.click(380,122)
    m.preview(a.output/'setup-selected.png')
    # Real pane clipping: scrollbar drag can leave cards partly visible. The
    # canopy and fixed footer must remain pixel-identical.
    original=m.preview();m.invoke(c['down'],m.r(s),(392,156));m.invoke(c['drag'],m.r(s),(392,196));m.invoke(c['up'],m.r(s),(392,196))
    assert 0<m.state(24)<=70
    scrolled=m.preview(a.output/'setup-scrolled.png');assert scrolled.crop((0,0,590,133)).tobytes()==original.crop((0,0,590,133)).tobytes()
    assert scrolled.crop((0,424,590,450)).tobytes()==original.crop((0,424,590,450)).tobytes()
    m.click(392,137)
    m.click(285,435);assert struct.unpack_from('<HH',m.sent[-1])==(0x1b2,165);assert m.sent[-1][4:18]==b'My comma store';assert struct.unpack_from('<I',m.sent[-1],89)[0]==12345
    before=len(m.sent);m.click(285,435);assert len(m.sent)==before
    m.receive(snapshot(3,12,history=7));m.click(392,407);assert m.state(24)==70
    m.receive(snapshot(3,1,history=7));assert m.state(24)==70 and m.state(16)==12
    assert m.r(rows+8)==100 and m.r(rows+64+8)==0,'depleted slots retained as sold'
    m.preview(a.output/'owner-sold-scrolled.png')
    assert any(m.r(args[2]+0x114)==170 and m.r(args[2]+0x118)==65 for args in m.png_calls),'tag_sold must be drawn'
    m.click(392,137);m.preview(a.output/'owner-sold.png')
    m.receive(snapshot(3,0,history=7));assert m.state(16)==12 and all(m.r(rows+i*64+8)==0 for i in range(12))
    m.click(490,435);assert m.sent[-1]==b'\x2e\x01' and not m.state(8)
    m.receive(snapshot(3,8,history=7));m.preview(a.output/'owner-history.png')
    assert m.state(16)==8 and all(m.r(rows+i*64+8)==100 for i in range(8)),'close/reopen clears sold cards'
    m.invoke(c['hit'],0,(392,407));assert m.u.reg_read(UC_X86_REG_EAX)==0,'eight listings need no scrollbar'
    m.click(578,408);assert m.state(28)==32
    m.click(490,434);assert m.sent[-1]==b'\x2e\x01' and not m.state(8)
    m.receive(snapshot(1,0)) # independent ordinary-buyer vectors start a fresh session
    m.receive(snapshot(4));m.preview(a.output/'buyer-empty.png')
    for i in range(6):m.choose(70+(i%2)*178,145+(i//2)*70)
    assert m.state(20)==6 and m.state(24)==0 and m.state(32)==104
    for _ in range(4):m.click(578,182)
    m.preview(a.output/'buyer-selected.png')
    m.click(548,210);assert m.r(choices+4)==2
    m.w(choices+4,35);m.move(436,192);m.preview(a.output/'buyer-quantity-tooltip.png')
    assert any(t[0]=='x35' for t in m.texts) and any(t[0]=='Quantity: 35' for t in m.texts)
    m.w(choices+4,2)
    m.move(39,144);m.preview(a.output/'buyer-tooltip.png');assert not any('Right-click' in t[0] for t in m.texts)
    m.invoke(c['rightdown'],m.r(s),(39,144));m.invoke(c['rightup'],m.r(s),(39,144));assert m.described[-1]==12214;assert struct.unpack_from('<I',m.descriptionItems[-1],0x10)[0]==100
    # Real row-to-CItem adapter keeps refine, cards, sparse options and grade.
    instance=bytearray(64);struct.pack_into('<IIIIBBBB4I',instance,0,1201,4,1,1000000,1,9,3,4,4001,4002,0,0);struct.pack_into('<HhB',instance,36,10,-5,2);struct.pack_into('<HhB',instance,46,20,50,1)
    pointer=m.alloc(64);m.u.mem_write(pointer,bytes(instance));m.invoke(c['describe'],0,(pointer,));item=m.descriptionItems[-1]
    assert struct.unpack_from('<I',item,0x60)[0]==9 and struct.unpack_from('<H',item,0x88)[0]==3
    assert struct.unpack_from('<4I',item,0x1c)==(4001,4002,0,0) and struct.unpack_from('<I',item,0x98)[0]==2
    assert item[0x9c:0xa6]==instance[36:41]+instance[46:51]
    before=len(m.sent);m.click(460,435);assert len(m.sent)==before,'Buy first opens confirmation'
    m.preview(a.output/'confirm-deal.png');assert any(t[0]=='Confirm Deal' for t in m.texts) and any(t[0]=='22,000 Zeny' for t in m.texts)
    m.click(548,210);assert m.r(choices+4)==2,'modal blocks underlying quantity controls'
    assert m.raised[-1]==m.state(14220),'a click on the parent must keep confirmation in front'
    m.confirm_click(245,132);assert len(m.sent)==before and m.state(20)==6,'cancel preserves buying choices'
    m.click(460,435);m.key_codes.add(27);m.invoke(c['cursor'],m.r(s),(300,200));m.key_codes.clear();m.invoke(c['cursor'],m.r(s),(300,200));assert m.state(8) and len(m.sent)==before
    m.click(460,435);m.confirm_click(195,132);assert struct.unpack_from('<HHII',m.sent[-1])==(0x801,36,2000001,123);assert struct.unpack_from('<HH',m.sent[-1],12)==(2,2)
    before=len(m.sent);m.click(460,435);assert len(m.sent)==before
    # Oversized, truncated and duplicate-index snapshots cannot replace good state.
    m.receive(snapshot(4,1));saved=bytes(m.u.mem_read(s+76,292));bad=bytearray(snapshot(4,2));struct.pack_into('<I',bad,292+64+4,2)
    m.receive(bad);assert bytes(m.u.mem_read(s+76,292))==saved
    bad=bytearray(snapshot(4,1));struct.pack_into('<H',bad,2,8);m.receive(bad);assert bytes(m.u.mem_read(s+76,292))==saved
    m.move(39,144);m.preview();m.invoke(c['rightdown'],m.r(s),(39,144));before=len(m.described)
    m.receive(snapshot(0,0));assert not m.state(8)
    m.invoke(c['rightup'],m.r(s),(39,144));assert len(m.described)==before,'stale right-click must not inspect old stock'
    # A new quote invalidates any pending confirmation. Item currencies use the
    # same authoritative purchase packet after explicit confirmation.
    m.receive(snapshot(4,1,currency=7227));m.choose(70,145);before=len(m.sent);m.click(460,435)
    m.preview(a.output/'confirm-item-currency.png');assert any(t[0]=='1,000 TCG Card' for t in m.texts)
    m.receive(snapshot(4,1,currency=7227));m.click(330,277);assert len(m.sent)==before
    m.choose(70,145);m.click(460,435);m.confirm_click(195,132);assert len(m.sent)==before+1
    # Native title dragging changes real frame positions (no drag stand-ins).
    def drag(obj,x,y):
        before=(m.r(obj+0x1c),m.r(obj+0x20))
        m.invoke(c['down'],obj,(x,y));m.invoke(c['drag'],obj,(x+40,y+25));m.invoke(c['up'],obj,(x,y))
        assert (m.r(obj+0x1c),m.r(obj+0x20))==(before[0]+40,before[1]+25)
        assert m.r(0x131f4e8+0x19c)==0 and not m.state(52)
    m.receive(snapshot(1,3));drag(m.r(s),220,92)
    m.receive(snapshot());drag(m.r(s),150,20);assert not m.state(56),'dragging sign must not start editing'
    drag(m.r(s),70,100);drag(m.r(s),475,160)
    m.receive(snapshot(4,2));m.choose(70,145);m.click(460,435)
    parent=(m.r(m.r(s)+0x1c),m.r(m.r(s)+0x20));dialog=m.state(14220)
    drag(dialog,70,10);assert (m.r(m.r(s)+0x1c),m.r(m.r(s)+0x20))==parent
    m.confirm_click(245,132);assert m.r(dialog+0x28)==0 and m.state(20)==1
    # Real installed walk-request call; preserve other native window checks.
    gate=0xC8F857+struct.unpack('<i',m.u.mem_read(0xC8F853,4))[0]
    for mode in [1,2,3,4]:
        m.receive(snapshot(1,0)) # each mode starts without an unrelated owner session
        m.receive(snapshot(mode,3));m.invoke(gate,0);assert m.u.reg_read(UC_X86_REG_EAX)&255==1
        m.receive(snapshot(0,0))
    m.receive(snapshot(0,0));m.invoke(gate,0);assert m.u.reg_read(UC_X86_REG_EAX)&255==0
    m.stub(0xA47B90,lambda:m.ret(4,123));m.invoke(gate,0);assert m.u.reg_read(UC_X86_REG_EAX)&255==1
    m.stub(0xA47B90,lambda:m.ret(4,0))
    # Click another store: dispose old quote/confirmation before stock 0130 is
    # sent; preserve its opcode and never send Close Store for another owner.
    m.stub(0xC8E63B,lambda:m.ret(0,m.u.reg_read(UC_X86_REG_EAX)))
    m.receive(snapshot(4,2));m.choose(70,145);m.click(460,435);before=len(m.sent)
    m.invoke(0xC8E636,0);assert m.u.reg_read(UC_X86_REG_EAX)==0x130
    assert not m.state(8) and not m.state(14212) and m.r(dialog+0x28)==0 and len(m.sent)==before
    m.invoke(gate,0);assert m.u.reg_read(UC_X86_REG_EAX)&255==0
    other=bytearray(snapshot(4,1));struct.pack_into('<II',other,16,2000002,124);m.receive(other)
    assert m.state(20)==0 and m.state(16)==1 and m.r(s+76+16)==2000002
    m.click(515,435);m.receive(snapshot(3,2))
    # Three history slots and the original buying plus icons are real pixels.
    m.receive(snapshot(3,2,history=1));m.preview(a.output/'history-one-sale.png')
    assert sum(m.r(args[2]+0x114)==144 and m.r(args[2]+0x118)==80 for args in m.png_calls)==3
    m.click(490,435);m.receive(snapshot(0,0))
    m.receive(snapshot(4,0));empty=m.preview(a.output/'buyer-empty-plus.png')
    for i in range(4):
        asset=Image.open(a.assets/'marketui/bg_buying.png').convert('RGB')
        assert empty.crop((425,184+i*52,450,209+i*52)).tobytes()==asset.crop((425,184+i*52,450,209+i*52)).tobytes()
    # Native cart-info receive handler owns count/capacity and weight units.
    m.w(0x131f7dc,0);m.receive(struct.pack('<HHHII',0x121,12,100,18890,80000))
    m.receive(snapshot());m.preview(a.output/'setup-cart-summary.png')
    assert any(t[0]=='12 / 100' for t in m.texts) and any(t[0]=='1,889 / 8,000' for t in m.texts)
    # A partial sale keeps its card live; only a depleted cart index gets SOLD.
    m.receive(snapshot(3,2));partial=bytearray(snapshot(3,2,history=1));struct.pack_into('<I',partial,300,91)
    m.receive(partial);m.preview();assert not any(m.r(args[2]+0x114)==170 for args in m.png_calls)
    depleted=bytearray(partial[:292]+partial[356:420]+partial[420:]);struct.pack_into('<H',depleted,2,len(depleted));struct.pack_into('<H',depleted,38,1)
    m.receive(depleted);m.preview(a.output/'owner-one-depleted.png')
    assert m.state(16)==2 and m.r(rows+8)==0 and m.r(rows+64+8)==100
    assert sum(m.r(args[2]+0x114)==170 for args in m.png_calls)==1
    test_owner_browsing(a.exe,a.assets,a.output)
    test_escape_and_controls(a.exe,a.assets,a.output)
    test_drag_amount(a.exe,a.assets,a.output)
    test_native_enter(a.exe,a.assets,a.output)
    print('PASS VendingUI: drag-only selection, native amount editor, quantity bounds and modal/stale-drag cancellation, Esc preserves own store and closes only visited shops, non-vendor Esc restores walking and permits the next shop, matching inset button pixels/hits, independent owner/buyer lifecycle and background sales during confirmation, native independent dragging, walk gate/restore, shop-switch quote disposal, exact empty slots/history/footer, real native insertion/selection and 5555 repeated redraw, scroll/clipping, retained SOLD slots, centered title/icons, x35, compact currency list with OK, purchase confirmation/cancel/Escape, authoritative packets, repeat-submit guards, malformed snapshots and isolated routes')

def test_owner_browsing(exe,assets,output):
    m=VendingMachine(exe,assets);s=m.c['state'];c=m.c;rows=s+368;choices=s+13808
    mode=lambda:struct.unpack('<H',m.u.mem_read(s+86,2))[0]
    def escape():
        m.key_codes.add(27);m.invoke(c['cursor'],m.r(s),(300,200))
        m.key_codes.clear();m.invoke(c['cursor'],m.r(s),(300,200))
    def blocked():
        m.invoke(c['blockwalk'],0);return m.u.reg_read(UC_X86_REG_EAX)
    m.stub(0xC8E63B,lambda:m.ret(0,m.u.reg_read(UC_X86_REG_EAX)))
    def switch():
        before=len(m.sent);m.invoke(0xC8E636,0)
        assert m.u.reg_read(UC_X86_REG_EAX)==0x130 and len(m.sent)==before,'browsing must not send Close Store'
    remote=lambda shop=124:snapshot(4,2,currency=7227,owner=2000002,shop=shop)
    own=snapshot(3,12,history=7);sale=snapshot(3,1,history=8)
    m.receive(own);m.click(392,407);m.click(578,408)
    assert m.state(24)==70 and m.state(28)==32
    switch();assert m.state(8) and mode()==3
    m.receive(remote());assert mode()==4 and m.state(24)==m.state(28)==0
    m.choose(70,145);m.click(460,435);assert m.state(14212)
    quote=bytes(m.u.mem_read(s+76,292));cart=bytes(m.u.mem_read(choices,12));dialog=m.state(14220);epoch=m.state(64);raised=len(m.raised)
    # An incoming sale must not change quote, currency, cart, confirmation or z-order.
    m.receive(sale)
    assert bytes(m.u.mem_read(s+76,292))==quote and bytes(m.u.mem_read(choices,12))==cart
    assert m.state(14212) and m.r(dialog+0x28) and m.state(64)==epoch and len(m.raised)==raised
    m.preview(output/'owner-browsing-confirmation.png')
    switch();assert m.state(8) and mode()==3 and not m.state(14212) and blocked()
    # Keep our owner controls available while waiting, including if B has closed.
    m.receive(snapshot(3,0,history=9));assert m.state(8) and mode()==3 and blocked()
    m.receive(remote(125));assert mode()==4 and m.state(20)==0 and m.r(s+96)==125
    m.click(515,435);assert m.state(8) and mode()==3 and blocked()
    assert m.state(16)==12 and all(m.r(rows+i*64+8)==0 for i in range(12))
    assert m.state(24)==70 and m.state(28)==32 and struct.unpack('<H',m.u.mem_read(s+116,2))[0]==9
    assert all(m.r(s+14232+i*4)==100 for i in range(12)),'original offered amounts survive remote quotes'
    m.preview(output/'owner-restored-after-browsing.png')
    assert any(m.r(args[2]+0x114)==170 for args in m.png_calls),'cached sold cards render tag_sold'
    # Escape and successful purchases both restore the owner, without closing it.
    switch();m.receive(remote());escape();assert mode()==3 and m.state(8)
    switch();m.receive(remote());m.choose(70,145);m.click(460,435)
    before=len(m.sent);m.confirm_click(195,132)
    assert len(m.sent)==before+1 and struct.unpack_from('<HHII',m.sent[-1])==(0x801,16,2000002,124)
    assert mode()==3 and m.state(8) and blocked()
    assert not any(p==b'\x2e\x01' for p in m.sent)
    # Failure after switching remote shops restores an actionable owner view.
    switch();m.receive(remote());switch();m.receive(snapshot(5,0))
    assert mode()==3 and m.state(8) and blocked()
    # Only the owner's explicit Close Store sends 012E and releases the lock.
    before=len(m.sent);m.click(490,435)
    assert len(m.sent)==before+1 and m.sent[-1]==b'\x2e\x01' and not m.state(8) and not blocked()
    switch();m.receive(remote());m.choose(70,145);m.click(460,435)
    m.receive(snapshot(0,0,shop=0)) # late acknowledgement of own close
    assert mode()==4 and m.state(14212)
    m.confirm_click(245,132);m.click(515,435);assert not m.state(8) and not blocked()
    # Server-side own closure while browsing also leaves the remote quote intact.
    m.receive(own);switch();m.receive(remote());m.choose(70,145);m.click(460,435)
    m.receive(snapshot(0,0,shop=0));assert mode()==4 and m.state(14212)
    m.confirm_click(245,132);escape();assert not m.state(8) and not blocked()
    # A normal buyer never regains stale owner stock after A -> B -> Cancel.
    switch();m.receive(remote());switch();assert not blocked()
    m.receive(remote(125));m.click(515,435);assert not m.state(8) and not blocked()
    # Frame destruction/map cleanup discards cached ownership without a packet.
    m.receive(own);switch();m.receive(remote());before=len(m.sent)
    m.stub(0x86E240,lambda:m.ret(4,m.u.reg_read(UC_X86_REG_ECX)))
    m.invoke(c['destroy'],m.r(s),(0,));assert not m.state(0) and not blocked() and len(m.sent)==before
    m.receive(remote());m.click(515,435);assert not m.state(8) and not blocked()
def test_escape_and_controls(exe,assets,output):
    m=VendingMachine(exe,assets);s=m.c['state'];c=m.c;choices=s+13808
    def escape(release=True):
        m.key_codes.add(27);m.invoke(c['cursor'],m.r(s),(-50,-50))
        if release:
            m.key_codes.clear();m.invoke(c['cursor'],m.r(s),(-50,-50))
    def blocked():
        m.invoke(c['blockwalk'],0);return m.u.reg_read(UC_X86_REG_EAX)
    def hit(x,y):
        m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
    # Pixel borders and hit regions agree, including all four edges. The old
    # buyer x at 558..570 used to escape its 144px card; it must no longer hit.
    def check_buttons(mode):
        setup=mode==2;m.receive(snapshot(mode,2))
        if setup:m.choose(437,185)
        else:m.choose(70,145)
        image=m.preview(output/('controls-setup.png' if setup else 'controls-buying.png'))
        x,y,w,h=(29,133,175,70) if setup else (421,179,144,52)
        points=[(154,5,13,4000),(128,28,16,6000),(148,28,16,6001)] if setup else [(124,4,13,4000),(97,28,16,6000),(117,28,16,6001)]
        for dx,dy,size,code in points:
            assert dx>=3 and dx+size<=w-3 and dy>=3 and dy+size<=h-3
            for px,py in [(x+dx,y+dy),(x+dx+size-1,y+dy+size-1)]:
                assert hit(px,py)==code,(mode,px,py,code)
                assert image.getpixel((px,py))==(189,206,235),'native mini-button border matches hit bounds'
            for px,py in [(x+dx-1,y+dy),(x+dx+size,y+dy),(x+dx,y+dy-1),(x+dx,y+dy+size)]:
                assert hit(px,py)!=code
        assert hit(568,184)==0 if not setup else True
        minus,plus=points[1],points[2]
        m.click(x+plus[0]+4,y+plus[1]+4);assert m.r(choices+4)==2
        m.click(x+minus[0]+4,y+minus[1]+4);assert m.r(choices+4)==1
        m.click(x+points[0][0]+4,y+points[0][1]+4);assert not m.state(20)
    check_buttons(2);check_buttons(4)
    escape();assert not m.state(8) and not blocked()
    # Esc cancels setup even with native price editing focused; exactly one
    # cancel request is sent while the key is held. Currency Esc also cancels.
    m.receive(snapshot());m.choose(437,185);m.click(80,189);m.inputText('5555')
    assert m.state(56);before=len(m.sent);escape(False)
    assert not m.state(8) and not m.state(56) and m.r(0x131F4E8+0x1A0)==0
    assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==2
    m.invoke(c['cursor'],m.r(s),(-50,-50));assert len(m.sent)==before+1
    m.key_codes.clear();m.invoke(c['cursor'],m.r(s),(-50,-50))
    m.receive(snapshot(1,3));before=len(m.sent);escape();assert not m.state(8) and len(m.sent)==before+1
    # The server excludes the owner from the shop-title broadcast. Esc must
    # never hide their only management window or depend on clicking that title.
    assert bytes(m.u.mem_read(0xC8E5F9,12))==bytes.fromhex('3B 15 A4 B9 5F 01 0F 84 D7 AC FF FF')
    own=snapshot(3,12,history=7);m.receive(own);m.click(392,407);m.click(578,408)
    before=len(m.sent);escape(False);assert m.state(8) and m.r(m.r(s)+0x28) and blocked()
    assert len(m.sent)==before,'Esc owner must not send 012E or Cancel'
    m.invoke(c['cursor'],m.r(s),(-50,-50));assert m.state(8) and len(m.sent)==before
    assert m.state(24)==70 and m.state(28)==32,'Esc leaves own view and scroll unchanged'
    m.key_codes.clear();m.invoke(c['cursor'],m.r(s),(-50,-50))
    m.preview(output/'esc-own-store-preserved.png')
    # Visit someone else while vending. A background sale and the first Esc
    # preserve the remote quote; the second Esc returns to the updated own view.
    m.receive(snapshot(4,2,owner=2000002,shop=124));m.choose(70,145);m.click(460,435)
    m.receive(snapshot(3,1,history=8));assert m.state(14212)
    escape();assert m.state(8) and not m.state(14212),'first Esc dismisses confirmation'
    assert struct.unpack('<H',m.u.mem_read(s+86,2))[0]==4
    escape();assert m.state(8) and blocked() and len(m.sent)==before
    assert struct.unpack('<H',m.u.mem_read(s+86,2))[0]==3 and m.state(16)==12
    assert m.state(24)==70 and m.state(28)==32 and m.r(s+368+64+8)==0
    m.preview(output/'esc-return-to-own-store.png')
    escape();assert m.state(8) and len(m.sent)==before,'Esc again cannot strand the owner'
    m.receive(snapshot(3,0,history=9));escape()
    assert m.state(8) and struct.unpack('<H',m.u.mem_read(s+116,2))[0]==9
    m.click(490,435);assert m.sent[-1]==b'\x2e\x01' and not m.state(8) and not blocked()
    m.receive(snapshot(0,0,shop=0));before=len(m.sent)
    # A non-vendor dismisses the visited shop entirely, can walk, and can open
    # the next shop without a stale own-store cache or request left behind.
    for owner,shop in [(2000002,124),(2000003,125)]:
        m.receive(snapshot(4,2,owner=owner,shop=shop));assert m.state(8) and blocked()
        escape();assert not m.state(8) and not m.r(m.r(s)+0x28) and not blocked()
        assert len(m.sent)==before
    m.receive(own);escape();assert m.state(8)
    m.receive(snapshot(0,0,shop=0));assert not m.state(8) and not blocked()

def test_drag_amount(exe,assets,output):
    m=VendingMachine(exe,assets);s=m.c['state'];c=m.c;choices=s+13808
    mode=lambda:struct.unpack('<H',m.u.mem_read(s+86,2))[0]
    def key(code,obj=None):
        obj=obj or m.r(s);m.key_codes.add(code)
        if code==13:m.enter()
        m.invoke(c['cursor'],obj,(-50,-50))
        m.key_codes.clear();m.invoke(c['cursor'],obj,(-50,-50))
    for view in [2,4]:
        start=(437,185) if view==2 else (70,145);dest=(100,160) if view==2 else (450,200)
        def begin():
            m.invoke(c['down'],m.r(s),start);m.invoke(c['drag'],m.r(s),dest)
        def drop():m.drag_item(*start,*dest)
        def release():m.invoke(c['up'],m.r(s),dest)
        m.receive(snapshot(view,2));before=len(m.sent)
        m.click(*start);assert not m.state(20) and not m.state(15040),'item clicks cannot add'
        m.drag_item(*start,start[0]+2,start[1]+2)
        assert not m.state(20) and not m.state(15040),'click jitter cannot add'
        m.drag_item(*start,300,100);assert not m.state(20) and not m.state(15040)
        assert not m.r(0x131f4e8+0x19c) and not m.state(52)
        frame=m.r(s);position=(m.r(frame+0x1c),m.r(frame+0x20))
        begin();assert m.state(52)==7 and m.r(0x131f4e8+0x19c)==frame
        m.preview(output/('drag-setup.png' if view==2 else 'drag-buying.png'))
        assert (m.r(frame+0x1c),m.r(frame+0x20))==position,'item drag must not move the window'
        release();assert m.state(15040) and not m.state(20) and len(m.sent)==before
        dialog=m.state(15032);editor=m.state(15036)
        assert m.r(dialog+0x2c)==0x3ed and (m.r(dialog+0x14),m.r(dialog+0x18))==(280,173)
        assert m.r(0x131f4e8+0x1a0)==editor and m.r(m.input+0x50)==0 and m.r(m.input+0x54)==1
        # The same native insertion routine used by typing/paste replaces the
        # initial selected value. An amount prompt sends no trade packet.
        ptr=m.alloc(4);m.u.mem_write(ptr,b'35\0');m.invoke(0xA6EA10,m.input,(ptr,))
        m.preview(output/('amount-to-vend.png' if view==2 else 'amount-to-buy.png'))
        assert any(t[0]=='Available: 100' for t in m.texts)
        m.click(460,435);assert m.state(15040) and not m.state(14212) and len(m.sent)==before
        assert m.raised[-1]==dialog,'underlying controls cannot bypass amount dialog'
        for invalid in ['', '0', '-1', '101', '9999999999', '1e2', '1.5']:
            m.inputText(invalid);m.amount_click(185,154)
            assert m.state(15040) and not m.state(20) and len(m.sent)==before
        m.inputText('35');m.amount_click(185,154)
        assert not m.state(15040) and m.state(20)==1 and m.r(choices+4)==35
        assert not m.r(0x131f4e8+0x1a0) and not m.r(0x131f4e8+0x19c)
        # Repeated drags add to the same row using only its unselected stock.
        drop();m.preview();assert any(t[0]=='Available: 65' for t in m.texts)
        m.inputText('65');key(13,dialog)
        assert m.r(choices+4)==100 and m.state(20)==1 and not m.state(15040)
        drop();assert m.r(choices+4)==100 and not m.state(15040)
        assert len(m.sent)==before
        # Cancelling with either button or Esc preserves the existing view.
        m.receive(snapshot(view,2));drop();m.amount_click(235,154)
        assert m.state(8) and not m.state(20) and not m.state(15040)
        drop();key(27,dialog);assert m.state(8) and not m.state(20) and not m.state(15040)
        begin();key(27);release();assert m.state(8) and not m.state(15040) and not m.state(20)
        # Changed snapshots and stolen capture invalidate a drag or quantity quote.
        begin();m.receive(snapshot(view,2,nonce=8));release()
        assert not m.state(20) and not m.state(15040)
        begin();m.w(0x131f4e8+0x19c,0);release();assert not m.state(15040)
        drop();m.inputText('35');m.receive(snapshot(view,1,nonce=9))
        m.invoke(c['up'],dialog,(185,154));assert not m.state(15040) and not m.state(20)
        assert not m.r(0x131f4e8+0x1a0)
        # A one-item stack needs no prompt. Zero/overflow requests never reach packets.
        one=bytearray(snapshot(view,2));struct.pack_into('<I',one,292+8,1)
        m.receive(one);drop();assert m.state(20)==1 and m.r(choices+4)==1 and not m.state(15040)
        m.receive(snapshot(view,2));m.choose(*start,amount=99);drop()
        assert m.r(choices+4)==100 and not m.state(15040)
        # The native amount frame drags independently of the storefront.
        m.receive(snapshot(view,2));drop();a=(m.r(dialog+0x1c),m.r(dialog+0x20));parent=(m.r(frame+0x1c),m.r(frame+0x20))
        m.invoke(c['down'],dialog,(40,10));m.invoke(c['drag'],dialog,(60,25));m.invoke(c['up'],dialog,(40,10))
        assert (m.r(dialog+0x1c),m.r(dialog+0x20))==(a[0]+20,a[1]+15)
        assert (m.r(frame+0x1c),m.r(frame+0x20))==parent and not m.r(0x131f4e8+0x19c)
        key(27,dialog)
    # Seller slot count remains server-authoritative even with drag selection.
    one_slot=bytearray(snapshot(2,2));struct.pack_into('<H',one_slot,36,1)
    m.receive(one_slot);m.choose(437,185);m.drag_item(471,185,100,160)
    assert m.state(20)==1 and not m.state(15040)
    # A different native edit taking focus cannot replace the amount with its
    # unrelated global input buffer (chat, another window, etc.).
    m.receive(snapshot(4,2));m.drag_item(70,145,450,200);m.inputText('35')
    m.invoke(c['editdraw'],m.state(15036));foreign=m.alloc(512)
    m.w(0x131f4e8+0x1a0,foreign);m.inputText('99');m.amount_click(185,154)
    assert m.r(choices+4)==35 and m.r(0x131f4e8+0x1a0)==foreign
    m.w(0x131f4e8+0x1a0,0)
    # A sale in our own store does not invalidate a remote amount dialog.
    m.receive(snapshot(3,2));m.receive(snapshot(4,2,owner=2000002,shop=124))
    m.drag_item(70,145,450,200);m.inputText('35');epoch=m.state(64);dialog=m.state(15032);raised=len(m.raised)
    m.receive(snapshot(3,1,history=1))
    assert m.state(15040) and mode()==4 and m.state(64)==epoch and len(m.raised)==raised
    m.amount_click(185,154);assert m.r(choices+4)==35
    before=len(m.sent);m.click(460,435);assert m.state(14212) and len(m.sent)==before
    m.confirm_click(195,132)
    assert struct.unpack_from('<HHIIHH',m.sent[-1])==(0x801,16,2000002,124,35,2)
    assert mode()==3 and m.state(8),'confirmed remote purchase returns to own store'
    # Destroying the prompt clears its native focus and cannot close a store.
    m.receive(snapshot(4,2,owner=2000002,shop=124));m.drag_item(70,145,450,200);before=len(m.sent)
    m.invoke(c['destroy'],m.state(15032),(0,))
    assert not m.state(15040) and not m.state(15032) and not m.state(15036)
    assert not m.r(0x131f4e8+0x1a0) and len(m.sent)==before

def test_native_enter(exe,assets,output):
    from PIL import ImageChops
    m=VendingMachine(exe,assets);s=m.c['state'];choices=s+13808
    def button(window,x,y,state):
        m.invoke(m.c['draw'],window);pix,w,h=m.pixels(window)
        actual=Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').crop((x,y,x+44,y+18)).convert('RGB')
        expected=Image.new('RGBA',(44,18),(244,248,252,255))
        expected.alpha_composite(Image.open(assets/'genericsui'/('ok_'+state+'.png')).convert('RGBA'))
        assert max(v[1] for v in ImageChops.difference(actual,expected.convert('RGB')).getextrema())<=1,state
    for view in [2,4]:
        packet=bytearray(snapshot(view,1));struct.pack_into('<I',packet,300,15)
        m.receive(packet);before=len(m.sent)
        m.drag_item(437 if view==2 else 70,185 if view==2 else 145,100 if view==2 else 450,160 if view==2 else 200)
        dialog=m.state(15032);editor=m.state(15036);clears=len(m.native_clears)
        # Invalid Enter leaves the exact input and focus available for correction.
        for invalid in ['16','0','','1.5']:
            m.inputText(invalid);m.enter()
            assert m.state(15040) and not m.state(20) and m.cstr(s+15060)=='Enter an amount from 1 to 15.'
            assert m.cstr(m.input+0x34)==invalid and m.r(0x131f4e8+0x1a0)==editor
            assert len(m.native_clears)==clears and len(m.sent)==before
        m.inputText('1');m.w(m.input+0x50,0);m.w(m.input+0x54,1)
        ptr=m.alloc(4);m.u.mem_write(ptr,b'15\0');m.invoke(0xA6EA10,m.input,(ptr,))
        # No draw/cache refresh between typing the last digit and native Enter.
        m.enter()
        assert m.state(20)==1 and m.r(choices+4)==15 and not m.state(15040)
        assert not m.r(0x131f4e8+0x1a0) and len(m.native_clears)==clears and len(m.sent)==before
        m.key_codes.add(13);m.invoke(m.c['cursor'],m.r(s),(-50,-50));m.key_codes.clear()
        assert m.r(choices+4)==15 and len(m.sent)==before and not m.state(14212)
        # A late native event for the hidden editor must neither add nor clear.
        m.inputText('unrelated');m.invoke(m.r(m.r(editor)+37*4),editor,(0,0,0,0,0,0))
        assert m.cstr(m.input+0x34)=='unrelated' and m.r(choices+4)==15
        m.receive(packet);m.drag_item(437 if view==2 else 70,185 if view==2 else 145,100 if view==2 else 450,160 if view==2 else 200)
        m.inputText('15');m.invoke(m.c['move'],dialog,(-1,-1));button(dialog,172,146,'out')
        m.preview(output/('enter-vend-15.png' if view==2 else 'enter-buy-15.png'))
        m.invoke(m.c['move'],dialog,(185,154));button(dialog,172,146,'over')
        m.invoke(m.c['down'],dialog,(185,154));button(dialog,172,146,'press')
        m.invoke(m.c['up'],dialog,(185,154));assert m.r(choices+4)==15 and len(m.sent)==before
    # Purchase confirmation uses the same exact OK artwork, including disabled.
    m.click(460,435);confirm=m.state(14220);assert m.state(14212)
    m.invoke(m.c['move'],confirm,(-1,-1));button(confirm,180,124,'out')
    m.preview(output/'confirm-generic-ok.png');assert any(t[0]=='Press OK to confirm.' for t in m.texts)
    m.invoke(m.c['move'],confirm,(195,132));button(confirm,180,124,'over')
    m.invoke(m.c['down'],confirm,(195,132));button(confirm,180,124,'press')
    # Server balance invalidation disables confirmation without issuing payment.
    m.w(s+76+28,0);button(confirm,180,124,'off')
    m.invoke(m.c['up'],confirm,(195,132));assert len(m.sent)==before and m.state(14212)
    m.w(s+76+28,2000000000);m.confirm_click(195,132)
    assert len(m.sent)==before+1 and struct.unpack_from('<HHIIHH',m.sent[-1])==(0x801,16,2000001,123,15,2)
    # Ordinary price/title edits keep their original native event behavior.
    m.receive(snapshot(2,1));m.choose(437,185);m.click(80,189);m.inputText('15')
    clears=len(m.native_clears);m.enter()
    assert len(m.native_clears)==clears+1 and m.cstr(m.input+0x34)==''

if __name__=='__main__':main()
