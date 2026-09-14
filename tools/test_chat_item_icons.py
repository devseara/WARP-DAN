"""Execute emitted chat-icon x86 and native base62 decoding in Unicorn.

The test doubles are explicit CRT, resource and item-name/UI boundaries.
This is an offline acceptance gate, not an in-game visual acceptance claim.
"""
import argparse
import struct

from unicorn.x86_const import *
from unicorn import UC_HOOK_CODE
from test_modern_chat_ui import Machine, ASSETS, pack

PREFIX = '<ITEML>' + '0' * 13
TAIL = "'00)00)00)00)00</ITEML>"
ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def b62(value):
    result = ''
    while value:
        value, digit = divmod(value, 62)
        result = ALPHABET[digit] + result
    return result or '0'


class IconMachine(Machine):
    def stub(self, address, fn):
        if not hasattr(self, '_stub_handles'): self._stub_handles = {}
        if address in self._stub_handles: self.u.hook_del(self._stub_handles[address])
        self._stub_handles[address] = self.u.hook_add(UC_HOOK_CODE,
            lambda u,a,s,d: fn(), begin=address, end=address)

    def __init__(self, exe):
        super().__init__(exe, ASSETS)
        self.contract = {}
        tag = self.pe.__data__.find(b'ChatItemIcons.v2\0')
        assert tag >= 0, 'ChatItemIcons was not applied'
        tag_va = self.base + self.pe.get_rva_from_offset(tag)
        needle = pack(tag_va)
        locations = []
        for section in self.pe.sections:
            d = section.get_data()
            pos = 0
            while (pos := d.find(needle, pos)) >= 0:
                locations.append(self.base + section.VirtualAddress + pos)
                pos += 1
        assert len(locations) == 1, locations
        names = 'convert stock add marker decorateFirst decorateChild blit resolver draw vtable size pickup rawStock rawAdd linkDraw linkVtable'.split()
        self.contract = dict(zip(names, [self.r(locations[0]+4+i*4) for i in range(len(names))]))
        self.imports = {}
        for module in self.pe.DIRECTORY_ENTRY_IMPORT:
            for entry in module.imports:
                if entry.name:
                    self.imports[entry.name.decode()] = entry.address
        self.iat(0xFC1830, lambda: self.ret(0, int(self.cstr(self.args(1)[0]) or '0')))
        self.iat(0xFC1B5C, self.strcpy_s)
        self.stub(0xDBC895, lambda: self.ret(0, self.alloc(self.args(1)[0])))
        self.stub(0xDBC89E, lambda: self.ret(0))
        self.stub(0x4F08F0, lambda: self.ret(0))
        self.stub(0xDBBBD4, lambda: self.ret(0, self.u.reg_read(UC_X86_REG_EAX)))

    def cstr(self, address):
        result = bytearray()
        for offset in range(4096):
            value = self.u.mem_read(address+offset, 1)[0]
            if value == 0: return result.decode('latin1')
            result.append(value)
        raise AssertionError('unterminated test string')

    def string(self, value, where=None):
        value = value.encode('latin1') if isinstance(value, str) else value
        obj = where if where is not None else self.alloc(24)
        self.u.mem_write(obj, bytes(24))
        if len(value) < 16:
            data, capacity = obj, 15
        else:
            data, capacity = self.alloc(len(value)+1), len(value)
            self.w(obj, data)
        self.u.mem_write(data, value+b'\0')
        self.w(obj+16, len(value)); self.w(obj+20, capacity)
        return obj

    def str_value(self, obj):
        data = obj if self.r(obj+20) < 16 else self.r(obj)
        return bytes(self.u.mem_read(data, self.r(obj+16))).decode('latin1')

    def text_buffer(self, value):
        address = self.alloc(len(value)+1)
        self.u.mem_write(address, value.encode('latin1')+b'\0')
        return address

    def iat(self, address, fn):
        stub = self.alloc(16)
        self.stub(stub, fn)
        self.w(address, stub)

    def strcpy_s(self):
        dest, cap, src = self.args(3)
        data = self.cstr(src).encode('latin1')+b'\0'
        assert len(data) <= cap
        self.u.mem_write(dest, data)
        self.ret(0)

    def assign(self):
        text, count = self.args(2)
        obj = self.u.reg_read(UC_X86_REG_ECX)
        self.string(bytes(self.u.mem_read(text, count)), obj)
        self.ret(8, obj)

    def framed(self, target, frame, obj, args):
        # Preserve the ABI while presenting the hook with its profiled caller EBP.
        thunk = self.alloc(128)
        code = b'\x55\xBD'+pack(frame)
        for arg in reversed(args): code += b'\x68'+pack(arg)
        call_site = thunk+len(code)
        code += b'\xE8'+pack(target-call_site-5)+b'\x5D\xC3'
        self.u.mem_write(thunk, code)
        self.invoke(thunk, obj)


def test_converter(m):
    dest = m.alloc(1536+32)
    for raw, expected in [
        ('hello', 'hello'), ('You got ^i[501]Red Potion (10).', 'You got '+PREFIX+b62(501)+TAIL+'Red Potion (10).'),
        ('^i[1] ^i[9999999]', PREFIX+'1'+TAIL+' '+PREFIX+b62(9999999)+TAIL),
        ('^i[0000501]', PREFIX+b62(501)+TAIL),
        ('^i[0] ^i[-1] ^i[] ^i[12345678] ^i[12x] ^i[501', '^i[0] ^i[-1] ^i[] ^i[12345678] ^i[12x] ^i[501'),
        ("<ITEML>000041jn%0a&01'04)12)34)56)78+01,02-03</ITEML>",
         "<ITEML>000041jn%0a&01'04)12)34)56)78+01,02-03</ITEML>"),
        ('x'*1023, 'x'*1023),
    ]:
        source = m.text_buffer(raw)
        m.u.mem_write(dest+1536, b'Z'*32)
        m.invoke(m.contract['convert'], 0, [source,dest])
        assert m.cstr(m.u.reg_read(UC_X86_REG_EAX)) == expected, raw
        assert bytes(m.u.mem_read(dest+1536,32)) == b'Z'*32
    for raw in ['x'*1024, '^i[501]'*150]:
        source = m.text_buffer(raw)
        m.invoke(m.contract['convert'], 0, [source,dest])
        assert m.u.reg_read(UC_X86_REG_EAX) == source
    m.invoke(m.contract['convert'], 0, [0,dest])
    assert m.u.reg_read(UC_X86_REG_EAX) == 0


def test_native_decode(m):
    # Execute the actual 2025 decoder (not a Python implementation) including
    # seven leading zeros: item identity must survive conversion exactly.
    for value in [1, 501, 502, 1201, 1202, 32767, 65536, 1000000, 9999999]:
        obj = m.string('0'*7+b62(value))
        args = [m.r(obj+i*4) for i in range(6)]
        m.invoke(0x842A20, 0, args)
        assert m.u.reg_read(UC_X86_REG_EAX) == value, value


def native_crt(m):
    m.stub(0xDBBC4F, lambda: m.ret(0,m.alloc(m.args(1)[0])))
    m.stub(0xDBBEAE, lambda: m.ret(0,m.alloc(m.args(1)[0])))
    m.stub(0xDBBC7F, lambda: m.ret(0))
    def copy():
        dest,src,count=m.args(3)
        m.u.mem_write(dest,bytes(m.u.mem_read(src,count)));m.ret(0,dest)
    def clear():
        dest,value,count=m.args(3)
        m.u.mem_write(dest,bytes([value&255])*count);m.ret(0,dest)
    def find():
        hay,needle=m.args(2)
        where=m.cstr(hay).find(m.cstr(needle));m.ret(0,hay+where if where>=0 else 0)
    m.iat(0xFC1740,copy);m.iat(0xFC1760,copy);m.iat(0xFC1744,clear)
    m.iat(0xFC1964,find);m.iat(0xFC1764,find)
    m.iat(0xFC1B30,lambda: m.ret(0,min(len(m.cstr(m.args(2)[0])),m.args(2)[1])))
    # Pure byte-search intrinsic used by MSVC std::string::find.
    def memchr():
        source,byte,count=m.args(3)
        at=bytes(m.u.mem_read(source,count)).find(bytes([byte&255]))
        m.ret(0,source+at if at>=0 else 0)
    if 'memchr' in m.imports:m.iat(m.imports['memchr'],memchr)
    if 'memcmp' in m.imports:
        def compare():
            left,right,count=m.args(3)
            l=bytes(m.u.mem_read(left,count));r=bytes(m.u.mem_read(right,count))
            m.ret(0,(l>r)-(l<r))
        m.iat(m.imports['memcmp'],compare)


def native_font_boundaries(m):
    # GDI-dependent truncation only. Native string construction/appending and
    # the two actual parser passes execute; spaces use the normal 3px advance.
    def width(text): return sum(3 if ch == ' ' else 6 for ch in text)
    def truncate():
        out,source,limit=m.args(3)
        assert limit == max(12,m.r(m.u.reg_read(UC_X86_REG_ECX)+0x14)//2-24)
        text=m.str_value(source)
        while width(text)>limit:text=text[:-1]
        m.string(text,out);m.ret(12,out)
    m.stub(0xA24EE0,truncate)
    m.stub(0xA21C90,lambda:m.ret(24,width(m.cstr(m.args(6)[0]))))
    m.stub(0xA240E0,lambda:m.ret(20,m.args(5)[0]))


def test_native_tokenizer(m):
    native_crt(m)
    for value in [1,501,1201,1202,65536,9999999]:
        source=m.string('0'*13+b62(value)+TAIL[:-8]); vector=m.alloc(12)
        m.invoke(0x847AF0,0,[source,vector])
        start,end=m.r(vector),m.r(vector+4)
        assert end-start>=12
        assert m.r(start)==0 and m.r(start+4)==0 and m.r(start+8)==value


def test_native_first_pass(m):
    native_crt(m)
    native_font_boundaries(m)
    m.string('<ITEML>',0x1204068);m.string('</ITEML>',0x1204080)
    # The item database/name boundary is mocked, but the actual chat message
    # parser, native std::string operations and emitted decoration hook run.
    def item_name():
        raw,out=m.args(2)
        m.string('Red Potion',out);m.ret(8,1)
    m.stub(0x849A00,item_name)
    pane=m.window(parent=m.window())
    for raw,expected in [
        ('You got '+PREFIX+b62(501)+TAIL+'Red Potion (10).','You got '+' '*8+'Red Potion (10).'),
        (PREFIX+'1'+TAIL+' / '+PREFIX+b62(9999999)+TAIL,' '*8+' / '+' '*8),
        ('Seara : <ITEML>000000'+b62(501)+TAIL,'Seara : '+' '*8+'Red Potion'),
        ('<ITEML>000000'+b62(501)+TAIL+' / <ITEML>000000'+b62(501)+TAIL,
         ' '*8+'Red Potion / '+' '*8+'Red Potion'),
    ]:
        source=m.string(raw);out=m.alloc(24)
        try:m.invoke(0x8416B0,pane,[out,source])
        except Exception:
            print('Native first-pass stopped at',hex(m.u.reg_read(UC_X86_REG_EIP)))
            raise
        assert m.str_value(out)==expected,(m.str_value(out),expected)


def test_native_child_pass(m):
    native_crt(m)
    native_font_boundaries(m)
    m.string('<ITEML>',0x1204068);m.string('</ITEML>',0x1204080)
    children=[]
    def item_ctor():
        obj=m.u.reg_read(UC_X86_REG_ECX)
        m.u.mem_write(obj,bytes(0xF8));m.string('',obj+0x2C);m.ret(0,obj)
    def item_from_token():
        vector,item=m.args(2)
        value=m.r(m.r(vector)+8)
        m.string(str(value),item+0x2C);m.ret(8,1)
    def item_copy():
        dest=m.u.reg_read(UC_X86_REG_ECX);source=m.args(1)[0]
        m.string(m.str_value(source+0x2C),dest+0x2C);m.ret(4,dest)
    def widget_ctor():
        obj=m.u.reg_read(UC_X86_REG_ECX)
        m.u.mem_write(obj,bytes(0x200));m.w(obj,0x102E648)
        m.string('',obj+0x7C);m.string('',obj+0xD4);m.string('',obj+0xF8+0x2C)
        m.ret(0,obj)
    def widget_text():
        obj=m.u.reg_read(UC_X86_REG_ECX);args=m.args(6)
        m.string(m.cstr(args[0]),obj+0x7C);m.w(obj+0xC8,12)
        m.setsize(obj,25,14);m.ret(24)
    def attach():
        obj=m.args(1)[0];m.w(obj+0x10,m.u.reg_read(UC_X86_REG_ECX))
        children.append(obj);m.ret(4)
    m.stub(0x6A1B20,item_ctor);m.stub(0x85B630,item_from_token)
    m.stub(0x6A25F0,item_copy)
    m.stub(0x6A2CE0,lambda: (m.string('Red Potion',m.args(2)[0]),m.ret(8,m.args(2)[0])))
    m.stub(0x835910,widget_ctor);m.stub(0x8448B0,widget_text)
    m.stub(0x831A50,lambda:m.ret(4));m.stub(0xA1B780,attach)
    m.stub(0xD99070,lambda:m.ret(0))
    m.stub(0x5AA6B0,lambda:m.ret(4))
    for parent_vt in [0x1037F80,0x1037EA8]:
        for raw,visible,child_text,vt in [
            ('You got '+PREFIX+b62(501)+TAIL+'Red Potion (10).',
             'You got '+' '*8+'Red Potion (10).',' '*8,'vtable'),
            ('Seara : <ITEML>000000'+b62(501)+TAIL,
             'Seara : '+' '*8+'Red Potion',' '*8+'Red Potion','linkVtable'),
        ]:
            children.clear()
            pane=m.window(parent=m.window(vt=parent_vt))
            head=m.alloc(20);m.w(head,head);m.w(head+4,head);m.w(pane+0xD4,head)
            out=m.alloc(24);source=m.string(raw)
            try:m.invoke(0x84A780,pane,[out,m.text_buffer(visible),source])
            except Exception:
                print('Native child-pass stopped at',hex(m.u.reg_read(UC_X86_REG_EIP)))
                raise
            assert m.str_value(out)==visible,(m.str_value(out),visible)
            # This native parser consumes its mutable raw-line working copy.
            # Converter preservation and CItem preservation are tested separately.
            assert len(children)==1
            child=children[0]
            assert m.r(child)==m.contract[vt]+4
            assert m.r(child+0x10)==pane and m.r(child+0x18)==18
            assert m.str_value(child+0xF8+0x2C)=='501'
            assert m.str_value(child+0x7C)==child_text
            if vt=='linkVtable': assert m.str_value(child+0xD4)==child_text


def test_native_wrap_gate(m):
    native_crt(m)
    for location,text in [(0x1202C28,'<ITEM>'),(0x1202C40,'</ITEM>'),
                          (0x1202B50,'<ITEML>'),(0x1202B68,'</ITEML>')]:
        m.string(text,location)
    seen=[];wrapped=[]
    dispatch=m.alloc(16)
    m.stub(dispatch,lambda:(seen.append(m.cstr(m.args(3)[0])),m.ret(12)))
    table=m.alloc(256);m.u.mem_write(table,bytes(m.u.mem_read(0x102D280,256)))
    m.w(table+0xE4,dispatch)
    def plain_wrap():
        wrapped.append(m.cstr(m.args(3)[0]));m.ret(12)
    m.stub(0xA23A20,plain_wrap)
    pane=m.window(w=120,parent=m.window());m.w(pane,table)
    for text in ['You got ^i[501]Red Potion (10).','^i[1]abc ^i[9999999]xyz']:
        source=m.text_buffer(text)
        m.invoke(0x83D3F0,pane,[source,0xFFFF00,source])
        assert '<ITEML>' in seen[-1] and '^i[' not in seen[-1]
        assert not wrapped, 'icon syntax reached plain-text wrapping before conversion'
    source=m.text_buffer('ordinary chat')
    m.invoke(0x83D3F0,pane,[source,0xFFFF00,source])
    assert wrapped==['ordinary chat']


def test_scopes_and_spacing(m):
    native_crt(m)
    native_font_boundaries(m)
    m.stub(0x84C6B0, lambda: m.ret(8, 0x12345678))
    m.stub(0x85F480, lambda: m.ret(8, 0x12345678))
    frame = m.alloc(2048)+1024
    raw = '0'*13+b62(501)+TAIL[:-8]
    for parent_vt in [0x1037F80, 0x1037EA8, 0x1020000]:
        parent = m.window(vt=parent_vt)
        pane = m.window(parent=parent)
        for body,expected in [(raw,' '*8),('000000'+b62(501)+TAIL[:-8],' '*8+'Red Potion')]:
            for marker_offset, key in [(-0x40,'decorateFirst'),(-0x28,'decorateChild')]:
                m.string(body, frame+marker_offset)
                result = m.alloc(24)
                m.framed(m.contract[key], frame, pane, [result, m.string('Red Potion')])
                if parent_vt == 0x1020000:
                    assert m.u.reg_read(UC_X86_REG_EAX)==0x12345678
                else:
                    assert m.str_value(result)==expected
        child = m.window(w=24,h=14,vt=0x102E648)
        m.w(frame-0x238,pane); m.string(raw, frame-0x28)
        m.framed(m.contract['size'], frame, child, [25,14])
        if parent_vt != 0x1020000:
            assert m.r(child)==m.contract['vtable']+4
            assert (m.r(child+0x14),m.r(child+0x18))==(25,18)
        else: assert m.r(child)==0x102E648
    for raw in ['00000085'+"'00)00)00)00)00", '00000T1234', 'plain text']:
        obj=m.string(raw); m.invoke(m.contract['marker'],obj)
        assert m.u.reg_read(UC_X86_REG_EAX)==0
    for offset in range(0,0xD8,4):
        if offset != 0x50:
            assert m.r(m.contract['vtable']+4+offset)==m.r(0x102E648+offset), hex(offset)
            assert m.r(m.contract['linkVtable']+4+offset)==m.r(0x102E648+offset), hex(offset)
    # A full item instance must not be reconstructed as a base-ID-only icon.
    pane=m.window(parent=m.window());m.w(frame-0x238,pane)
    m.string("000041"+b62(1201)+"%0a&01'04)12)34)56)78+01,02-03",frame-0x28)
    child=m.window(w=110,h=14,vt=0x102E648)
    payload=bytes((i*37+11)%256 for i in range(0xF8))
    m.u.mem_write(child+0xF8,payload)
    m.framed(m.contract['size'],frame,child,[110,14])
    assert m.r(child)==m.contract['linkVtable']+4 and m.r(child+0x18)==18
    assert bytes(m.u.mem_read(child+0xF8,0xF8))==payload


def test_link_long_names(m):
    native_crt(m);native_font_boundaries(m)
    frame=m.alloc(2048)+1024
    m.string('000000'+b62(501)+TAIL[:-8],frame-0x40)
    m.string('000000'+b62(501)+TAIL[:-8],frame-0x28)
    for width in [40,80,120,594]:
        pane=m.window(w=width,parent=m.window())
        results=[]
        for hook in ['decorateFirst','decorateChild']:
            out=m.alloc(24)
            m.framed(m.contract[hook],frame,pane,[out,m.string('Refined Long Item Name [3]'*10)])
            results.append(m.str_value(out))
        assert results[0]==results[1] and results[0].startswith(' '*8)
        assert '<' not in results[0] and '>' not in results[0]
        expected='Refined Long Item Name [3]'*10
        while sum(3 if ch==' ' else 6 for ch in expected)>max(12,width//2-24):
            expected=expected[:-1]
        assert results[0]==' '*8+expected


def test_drop_producer(m):
    native_crt(m)
    # Both old dispatch and new packet-handler paths call the same ID-aware
    # wrapper immediately before MSI_DROP_ITEM; no shared formatter mutation.
    for site in [0xCA05EA,0xCC5F46]:
        assert m.u.mem_read(site,1)==b'\xe8'
        assert (site+5+m.r(site+1))&0xffffffff==m.contract['pickup']
    for site in [0xCA0602,0xCC5F59]:
        assert bytes(m.u.mem_read(site,5))==b'\x68'+pack(1609)
    captured=[];deleted=[]
    def inventory_item():
        out,index=m.args(2);assert index==7
        m.u.mem_write(out,bytes(0xF8));m.w(out+4,10);m.string('501',out+0x2C)
        m.ret(8,out)
    m.stub(0xD5AA40,inventory_item)
    m.stub(0xD57A30,lambda:(deleted.append(m.args(2)),m.ret(8)))
    m.stub(0x6A2CE0,lambda:(m.string('Red Potion',m.args(2)[0]),m.ret(8,m.args(2)[0])))
    fmt=m.text_buffer('You dropped %s (%d).')
    def message():
        assert m.args(1)[0]==1609;m.ret(0,fmt)
    def prefix():
        out,format_ptr,item_id,name=m.args(4)
        m.u.mem_write(out,(f'^i[{item_id}]'+m.cstr(name)).encode()+b'\0');m.ret(0)
    def format_drop():
        out,format_ptr,name,count=m.args(4);assert format_ptr==fmt
        m.string(f'You dropped {m.cstr(name)} ({count}).',out);m.ret(0,out)
    m.stub(0xA9ED30,message);m.stub(0xA94930,format_drop)
    calls=m.targets(m.contract['pickup'],180);m.stub(calls[2],prefix)
    m.stub(0xA4AD20,lambda:(captured.append((m.args(5),m.cstr(m.args(5)[1]))),m.ret(20)))
    owner=m.alloc(0x400);packet=m.alloc(8)
    m.u.mem_write(packet,struct.pack('<HHHH',0xAF,7,2,0))
    m.invoke(0xCC5EB0,owner,[packet])
    assert captured[0][1]=='You dropped ^i[501]Red Potion (2).'
    assert captured[0][0][2:]==[0xFFFF00,6,0]
    assert deleted==[[7,2]]


def test_add_and_pickup(m):
    received=[]
    m.stub(m.contract['stock'], lambda: (received.append(tuple(m.cstr(a) if a else None for a in [m.args(3)[0],m.args(3)[2]])),m.ret(12)))
    for vt in [0x1037F80,0x1037EA8,0x1020000]:
        pane=m.window(parent=m.window(vt=vt)); m.w(pane+0xB8,14)
        text=m.text_buffer('You got ^i[501]Red Potion (10).')
        m.invoke(m.contract['add'],pane,[text,0xFFFF00,text])
        wanted='You got '+PREFIX+b62(501)+TAIL+'Red Potion (10).' if vt!=0x1020000 else m.cstr(text)
        assert received[-1]==(wanted,wanted)
        assert m.r(pane+0xB8)==(20 if vt!=0x1020000 else 14)
    m.stub(0x6A2CE0, lambda: (m.string('Knife [3]',m.args(2)[0]),m.ret(8,m.args(2)[0])))
    m.stub(0x4F1940,m.assign)
    # Native CItem::ItemIdGetter uses +2C, not display-name matching.
    fmt = m.alloc(16)
    def snprintf():
        dest, format_ptr, item_id, name = m.args(4)
        assert m.cstr(format_ptr)=='^i[%u]%s'
        value=f'^i[{item_id}]'+m.cstr(name)
        m.u.mem_write(dest,value.encode()+b'\0');m.ret(0,len(value))
    # Resolve the native StringFormat CALL from the pickup wrapper.
    ins=list(m.cs.disasm(bytes(m.u.mem_read(m.contract['pickup'],256)),m.contract['pickup']))
    calls=[int(i.op_str,16) for i in ins if i.mnemonic=='call']
    format_call=calls[2]; m.stub(format_call,snprintf)
    for value in [1201,1202,0,9999999,10000000]:
        item=m.alloc(0x100);m.string(str(value),item+0x2C);out=m.alloc(24)
        m.invoke(m.contract['pickup'],item,[out,0])
        expected=f'^i[{value}]Knife [3]' if 1<=value<=9999999 else 'Knife [3]'
        assert m.str_value(out)==expected,(value,m.str_value(out))


def test_blit(m):
    tex=m.alloc(0x130); src=m.alloc(24*24*4)
    m.w(tex+0x114,24);m.w(tex+0x118,24);m.w(tex+0x11C,src)
    colors=[0xFF00FF if (x+y)%5==0 else (0 if x==1 else x+y*256) for y in range(24) for x in range(24)]
    m.u.mem_write(src,b''.join(pack(v) for v in colors))
    for width,height in [(25,18),(9,7),(18,22)]:
        obj=m.window(w=width,h=height);pixels,_,_=m.pixels(obj)
        m.u.mem_write(pixels,pack(0x80111114)*(width*height))
        m.invoke(m.contract['blit'],0,[obj,tex])
        for y in range(height):
            for x in range(width):
                expected=0x80111114
                if x<18 and y<18:
                    color=colors[(y*24//18)*24+x*24//18]
                    if color!=0xFF00FF:expected=color|0xFF000000
                assert m.r(pixels+(y*width+x)*4)==expected,(x,y,width,height)
    obj=m.window(w=18,h=18);pixels,_,_=m.pixels(obj)
    m.w(tex+0x114,65);m.invoke(m.contract['blit'],0,[obj,tex])
    assert bytes(m.u.mem_read(pixels,18*18*4))==bytes(18*18*4)


def test_draw(m):
    node=m.alloc(0x90);m.string('test_red_potion',node+0x58)
    manager=m.alloc(32);m.w(0x159C088,manager)
    looked_up=[]
    def lookup():
        value=m.r(m.args(1)[0]);looked_up.append(value)
        assert m.u.reg_read(UC_X86_REG_ECX)==manager+8
        m.ret(4,node if value==501 else 0)
    m.stub(0xA7E780,lookup)
    # The image loader is a boundary; path formatting, the actual ItemId map
    # resolver, emitted draw and scale/clipping code all execute.
    draw_ins=list(m.cs.disasm(bytes(m.u.mem_read(m.contract['draw'],512)),m.contract['draw']))
    format_addr=[int(i.op_str,16) for i in draw_ins if i.mnemonic=='call'][3]
    def format_path():
        dest,fmt,key=m.args(3)
        value=m.cstr(fmt).replace('%s',m.cstr(key))
        assert value.endswith('\\item\\test_red_potion.bmp')
        m.u.mem_write(dest,value.encode('latin1')+b'\0');m.ret(0,len(value))
    m.stub(format_addr,format_path)
    tex=m.alloc(0x130);src=m.alloc(24*24*4)
    m.w(tex+0x114,24);m.w(tex+0x118,24);m.w(tex+0x11C,src)
    m.u.mem_write(src,pack(0x00112233)*(24*24))
    m.stub(0xA8D4A0,lambda:m.ret(4,tex))
    for item_id in [501,502]:
        obj=m.window(w=25,h=18);m.string(str(item_id),obj+0xF8+0x2C)
        m.invoke(m.contract['draw'],obj)
        assert looked_up[-1]==item_id
        pixels,_,_=m.pixels(obj)
        expected=0xFF112233 if item_id==501 else 0x80111114
        assert m.r(pixels)==expected
        assert m.r(pixels+24*4)==0x80111114
        assert m.u.mem_read(m.r(obj+0x24)+0x28,1)==b'\x01'

    # Execute the real native item-link draw beneath our private wrapper.
    # GDI text remains a boundary, but receives the exact padded native name,
    # original foreground color, font arguments and hover/underline state.
    drawn=[]
    def text():
        obj=m.u.reg_read(UC_X86_REG_ECX);args=m.args(9)
        assert m.cstr(args[2])==' '*8+'Red Potion'
        drawn.append(args)
        pix,w,h=m.pixels(obj)
        m.w(pix+(w+25)*4,args[6]);m.w(pix+(w+26)*4,0)
        m.ret(36)
    def outlined_text():
        args=m.args(10);assert m.cstr(args[2])==' '*8+'Red Potion'
        drawn.append(args)
        obj=m.u.reg_read(UC_X86_REG_ECX);pix,w,h=m.pixels(obj)
        m.w(pix+(w+25)*4,args[4]);m.w(pix+(w+26)*4,0);m.ret(40)
    underlines=[]
    m.stub(0xA25A70,text);m.stub(0xA26E30,outlined_text)
    m.stub(0xA1D460,lambda:(underlines.append(m.args(5)),m.ret(20)))
    for item_id,hover in [(501,False),(502,False),(501,True)]:
        obj=m.window(w=90,h=18,vt=m.contract['linkVtable']+4)
        m.string(str(item_id),obj+0xF8+0x2C);m.string(' '*8+'Red Potion',obj+0xD4)
        m.w(obj+0xB4,0xFFFF00);m.w(obj+0xC8,12);m.w(obj+0x1FC,1)
        m.u.mem_write(obj+0xC4,bytes([int(hover),int(hover)]))
        m.invoke(m.contract['linkDraw'],obj)
        pix,w,h=m.pixels(obj)
        assert m.r(pix)==(0xFF112233 if item_id==501 else 0x80111114)
        assert m.r(pix+30*4)==0x80111114
        assert m.r(pix+(w+25)*4)==0xFFFFFF00 and m.r(pix+(w+26)*4)==0xFF000000
        assert m.u.mem_read(m.r(obj+0x24)+0x28,1)==b'\x01'
    assert len(drawn)==3 and len(underlines)==1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe');args=parser.parse_args()
    for test in [test_converter,test_native_decode,test_native_tokenizer,test_native_first_pass,test_native_child_pass,test_native_wrap_gate,test_scopes_and_spacing,test_link_long_names,test_add_and_pickup,test_drop_producer,test_blit,test_draw]:
        test(IconMachine(args.exe));print('PASS',test.__name__)
    print('PASS: bounded syntax, actual native ItemId decoding, scoped native-link spacing,')
    print('      main/floating routing, pickup/drop identity, icon-plus-name links, native handlers and clipped pixels.')
    print('In-game screenshot acceptance is still required.')


if __name__=='__main__':main()
