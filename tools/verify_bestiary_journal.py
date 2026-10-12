"""Execute BSUI's emitted x86 with native engine boundaries mocked.

This verifies native ABI, transport isolation, malformed input, pagination,
resource lookup and rendering bounds. It is not live visual acceptance.
"""
from pathlib import Path
from bestiary_paths import bestiary_texture_root
import argparse,json,struct
import pefile
from unicorn.x86_const import UC_X86_REG_ESP
from bestiary_test_vm import VM,verify_dispatch


def packet(request=1, version=2):
    size=5120 if version>=3 else 3392
    data=bytearray(size)
    def w16(off,v):struct.pack_into('<H',data,off,v)
    def w32(off,v):struct.pack_into('<I',data,off,v)
    def text(off,value):data[off:off+len(value)]=value.encode()
    w16(0,0xbef);w16(2,size);w32(4,0x49555342);w16(8,version);w16(10,2);w32(12,request);w32(16,3)
    w16(26,2);w16(28,6);w32(32,9);w32(36,1002);w16(42,2);w16(44,4);w16(48,2);w16(50,2);w32(52,1)
    for i,(id,name) in enumerate([(1002,'Poring'),(1004,'Hornet'),(1005,'Familiar'),(1007,'Fabre'),(1008,'Pupa'),(1009,'Condor')]):
        off=64+i*128;w32(off,id);w32(off+4,id);w16(off+8,1);w16(off+10,1);text(off+20,name);text(off+84,'Lv. 1');text(off+104,'Water 1')
    d=832
    w32(d,1002);w32(d+4,1002);w32(d+8,50);struct.pack_into('<QQ',data,d+16,50,25)
    for off,value in [(64,'Poring'),(128,'No. 1002 / Lv. 1'),(176,'50'),(200,'50'),(224,'25'),(248,'Water 1'),(272,'Plant'),(296,'Medium'),(320,'Passive / Looter'),(384,'7 - 10'),(408,'0'),(432,'5'),(456,'Server rates; personal and party modifiers excluded.')]:text(d+off,value)
    for i,(id,name,rate) in enumerate([(909,'Jellopy','100.00%'),(713,'Empty Bottle','100.00%'),(1201,'Knife','25.00%'),(4001,'Poring Card','0.25%')]):
        off=1344+i*128;w32(off,id);text(off+16,name);text(off+80,rate);text(off+104,'Server drop rate')
    for i,name in enumerate(['prt_fild08','prt_fild05']):
        off=1856+i*128;w32(off,100+i);w32(off+4,20);text(off+8,name);text(off+32,name);text(off+96,'Spawns: 20')
    for i in range(40):
        struct.pack_into('<q',data,2112+i*8,i+1)
        text(2432+i*24,str(i+1))
    if version>=3:
        w16(3402,65535)
        for off in [3406,3412,3418]:w16(off,1)
        w16(3408,1);w32(3424,1);w32(3428,3)
        w32(3456,28);w16(3460,1);text(3464,'Heal Lv.1');text(3512,'Attacking: Own HP <= 50%');text(3576,'Cast 0ms / Delay 5000ms')
        for i in range(2):text(4112+i*96,'Respawn: 1.000s')
    return bytes(data)


class JournalVM(VM):
    def __init__(self,pe,m):
        super().__init__(pe,m)
        self.sent=[];self.personal_sent=[]
        self.stub(0xA21C90,24,lambda ecx,a:len(self.cstring(a[0]))*5)
        self.stub(0xA25A70,36)
        self.stub(0xA1CB30,4)
        self.stub(0xA1D260,16)
        self.stub(m['fill']['vir'],24)
        self.stub(m['colorKeyBlit']['vir'],16)
        self.stub(m["preview"]["vir"],32)
        self.stub(m['packetRefs']['packetCtorA'],0,lambda ecx,a:0x60000140)
        self.stub(m['packetRefs']['packetSend'],8,self.send)
        self.stub(0x59CDF0,0,self.format)
        self.stub(0xD5BB40,8,lambda ecx,a:self.string('poring'))
        self.stub(0xA8E500,4,lambda ecx,a:1)
        self.stub(0xA9F030,0,lambda ecx,a:self.read32(self.u.reg_read(UC_X86_REG_ESP)+4))
        self.stub(0xC9E1DD,0)
        if m['fallback'] != 0xC9E1DD:self.stub(m['fallback'],0)
        self.stub(m['itemResolver']['vir'],4,lambda ecx,a:self.string('jellopy'))

    def send(self,ecx,a):
        packet=bytes(self.u.mem_read(a[1],a[0]))
        target=self.personal_sent if len(packet)==128 and struct.unpack_from('<H',packet,10)[0]==8 else self.sent
        target.append(packet)
    def format(self,ecx,a):
        esp=self.u.reg_read(UC_X86_REG_ESP)
        args=[self.read32(esp+4+i*4) for i in range(5)]
        dest,capacity,_truncate,fmt,value=args
        pattern=self.cstring(fmt)
        result=pattern.replace(b'%s',self.cstring(value)) if b'%s' in pattern else pattern.replace(b'%u',str(value).encode())
        assert len(result)<capacity
        self.u.mem_write(dest,result+b'\0');return len(result)
    def state32(self,off,value=None):
        if value is not None:self.write32(self.state+off,value)
        return self.read32(self.state+off)
    def receive(self,data):
        self.u.mem_write(0x15e8198,data)
        self.run('receiver')
    def ready(self):
        self.state32(24,1);self.state32(152,1);self.receive(packet(version=self.m.get("protocolVersion",2)))


def verify(directory):
    full=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True)
    verify_dispatch(pe,full)
    m=full['bestiary'];checks=['Exact /bestiary dispatch, fallback, stack and register ownership']
    if not m:
        route=full.get('sharedRoute')
        if route:
            target=struct.unpack('<I',pe.get_data(route['fallbackCellVir']-pe.OPTIONAL_HEADER.ImageBase,4))[0]
            extensions=full.get('extensions') or {}
            expected=extensions.get('router',{}).get('vir') if extensions.get('selected') else route['fallbackVir']
            assert target==expected and target!=full['previousReceiver']
            assert 'BestiaryUI' not in extensions.get('entries',{})
            checks.append('Removal restores the shared packet fallback before freeing the BSUI receiver')
        return {'passed':True,'checks':checks+['Removal: slash no longer reaches freed code'],'live_accepted':False}
    version=m.get("protocolVersion",2);size=m["payload"]["size"];request_size=m["pendingRequest"]["size"]
    make=lambda request=1:packet(request,version)
    import hashlib
    source=Path(__file__).resolve().parent/'native/bestiary_preview.cpp'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==m['preview']['sourceSha256']
    for emitted in m['emissions']:
        expect=bytes.fromhex(emitted['hex'])
        assert pe.get_data(emitted['vir']-pe.OPTIONAL_HEADER.ImageBase,len(expect))==expect
    checks.append('All emitted code and initial data match the actual patched PE')
    for name in m['assets']:
        path=directory/bestiary_texture_root(m)/'journal'/name
        assert path.is_file() and path.read_bytes()[:2]==b'BM',name
    checks.append(f'All {len(m["assets"])} resource files are deployed at the emitted native paths')
    v=JournalVM(pe,m);v.u.mem_write(m['query']['vir'],b'Poring\0');v.state32(120,2);v.state32(132,1);v.state32(136,3)
    v.run('sender',[3,1,1002,0]);raw=v.sent[-1]
    assert len(raw)==request_size and struct.unpack_from('<HHIHH',raw)==(0xbf8,request_size,0x49555342,version,3)
    assert struct.unpack_from('<I',raw,12)[0]==1 and struct.unpack_from('<HH',raw,32)==(1,3)
    assert raw[36:43]==b'Poring\0' and raw[-1]==0 and v.state32(152)==1
    checks.append(f'{request_size}-byte requests: opcode, BSUI magic, sequence, query, filters, selection and subpages')
    v=JournalVM(pe,m);v.ready();assert v.state32(16)==1 and v.state32(52)==6 and v.state32(28)==1002
    assert bytes(v.u.mem_read(m['payload']['vir'],size))==make()
    # Each rejection starts with an outstanding request and a guarded payload.
    vectors=[(2,'H',size-1),(2,'H',65535),(8,'H',1),(10,'H',4),(12,'I',0),(12,'I',2),(28,'H',7),(30,'H',11),(44,'H',5),(50,'H',3),(24,'H',2),(40,'H',2),(46,'H',2),(36,'I',1234),(832,'I',1234),(20,'I',4)]
    if version>=3:vectors += [(3392,"H",13),(3394,"H",4),(3396,"H",4),(3398,"H",3),(3408,"H",5),(3414,"H",5),(3420,"H",5),(3404,"H",1),(3410,"H",1),(3416,"H",1)]
    for off,fmt,value in vectors:
        v=JournalVM(pe,m);v.state32(24,1);v.state32(152,1)
        before=b'G'*size;v.u.mem_write(m['payload']['vir'],before)
        bad=bytearray(make());struct.pack_into('<'+fmt,bad,off,value);v.receive(bytes(bad))
        assert bytes(v.u.mem_read(m['payload']['vir'],size))==before,(off,value)
        assert v.state32(16)==0,(off,value)
    v=JournalVM(pe,m);v.ready();v.receive(make());assert v.state32(152)==0
    checks.append('Snapshot rejection: exact lengths, version/type, stale/future requests, counts, pages and detail identity')
    v=JournalVM(pe,m);v.ready();v.state32(12,7);v.state32(132,2);v.state32(136,3);v.state32(152,1);v.state32(148,10000)
    raw=bytearray(size);struct.pack_into('<HHIHHIII',raw,0,0xbef,size,0x49555342,version,2,1,3,2)
    v.receive(bytes(raw));assert [v.state32(off) for off in [12,132,136,28]]==[7,2,3,1002]
    assert v.state32(156)==2 and v.state32(148)==10000
    v.run('sender',[6,0,1002,0]);assert v.state32(16)==1, 'Retry must retain the last valid displayed snapshot'
    checks.append('Busy snapshots preserve the displayed monster/subpages and use bounded request retries')

    v=JournalVM(pe,m);v.state32(24,1);v.state32(152,1)
    raw=bytearray(make());raw[84:148]=b'A'*64;v.receive(bytes(raw));assert v.u.mem_read(m['payload']['vir']+147,1)==b'\0'
    raw=bytearray(make());raw[2432:2456]=b'Z'*24;v.state32(152,1);v.receive(bytes(raw))
    assert v.u.mem_read(m['payload']['vir']+2455,1)==b'\0'
    checks.append('All fixed strings, including 40 v2 statistic values, are terminated before drawing')
    v=JournalVM(pe,m);v.ready()
    def click(x,y):v.run('down',[x,y]);v.run('up',[x,y])
    click(40,174);assert struct.unpack_from('<I',v.sent[-1],28)[0]==1004
    v.ready();click(155,451);assert struct.unpack_from('<H',v.sent[-1],24)[0]==1
    v.ready();click(731,333);assert struct.unpack_from('<H',v.sent[-1],32)[0]==1
    v.ready();click(733,86);assert struct.unpack_from('<H',v.sent[-1],34)[0]==1
    v.ready();click(708,119);assert struct.unpack_from('<H',v.sent[-1],26)[0]==2
    v.ready();click(708,176);assert struct.unpack_from('<H',v.sent[-1],26)[0]==3
    v.ready();click(166,92);v.run('down',[24,149]);assert v.state32(120)==2
    v.focus=v.state32(116);v.capture=v.window;click(747,11);assert v.u.mem_read(v.window+0x28,1)==b'\0' and v.capture==0
    checks.append('Native clicks: selection, catalog/drop/habitat paging, both navigation buttons, filter and close')
    v=JournalVM(pe,m);v.ready()
    def click(x,y):v.run('down',[x,y]);v.run('up',[x,y])
    click(309,336);assert v.state32(140)==1
    for expect in [1,2,3,3]:click(731,333);assert v.state32(160)==expect
    assert not v.sent and v.state32(132)==0
    for expect in [2,1,0,0]:click(711,333);assert v.state32(160)==expect
    click(397,336);assert v.state32(140)==2
    click(731,333);assert not v.sent and v.state32(132)==0
    for x,expected in [(625,1),(703,2)]:
        click(x,39);assert v.state32(4)==expected
        click(63,486);assert v.state32(4)==0 and v.state32(28)==1002
    checks.append('Info paging is local and bounded; Lore cannot page drops; Research/Rewards return to the selected monster')

    v=JournalVM(pe,m)
    for value,good in [('prt_fild08',True),('1@tower',True),('../secret',False),('C:\\file',False),('x'*24,False),('',False)]:
        v.calls=[];v.run('map',[v.string(value),503,110]);loads=[call for call in v.calls if call[0]==0xA8D4A0]
        assert bool(loads)==good,value
    checks.append('Map path allowlist rejects traversal, absolute paths, empty and overlong names')
    v=JournalVM(pe,m);v.run('sprite',[1002,20,20,32,32,0])
    resolver=[call for call in v.calls if call[0]==0xD5BB40][-1];assert resolver[1:]==(0x15fa3c0,[1002,0xffffffff])
    v.calls=[];v.stub(0xA8E500,4,lambda ecx,a:0);v.run('sprite',[1002,20,20,32,32,0]);assert not any(call[0]==0xA8D4A0 for call in v.calls)
    v.calls=[];v.run('image',[v.string('bestiary\\missing.bmp'),2,2]);assert not any(call[0]==0xA8D4A0 for call in v.calls)
    checks.append('Numeric native sprite resolver and missing-resource guards preserve ABI without loader spam')
    v=JournalVM(pe,m);v.ready();v.run('draw')
    portraits=[args for addr,ecx,args in v.calls if addr==m['preview']['vir']]
    assert any(args[3:7]==[215,103,240,156] for args in portraits)
    expected={m['payload']['vir']+2432+i*24 for i in range(40)}
    seen=set()
    if m.get('layoutVersion',0)>=8:
        from unicorn import UC_HOOK_CODE
        def numeric_source(uc,address,size,data):
            seen.add(v.read32(uc.reg_read(UC_X86_REG_ESP)+4))
        v.u.hook_add(UC_HOOK_CODE,numeric_source,begin=m['numberText']['vir'],end=m['numberText']['vir'])
    for page in range(4):
        v.calls=[];v.state32(140,1);v.state32(160,page);v.run('draw')
        seen.update(args[2] for addr,ecx,args in v.calls if addr==0xA25A70)
    assert expected<=seen,expected-seen
    v.calls=[];v.state32(4,1)
    if m.get('layoutVersion',0)>=9:
        v.write32(m['personalState']['vir']+16,1);v.write32(m['personalPayload']['vir']+44,1002)
    v.run('draw')
    research_rect=[31,181,210,168] if m.get('layoutVersion',0)>=9 else [32,167,210,156]
    assert any(args[3:7]==research_rect for addr,ecx,args in v.calls if addr==m['preview']['vir'])
    checks.append('Emitted draw uses enlarged portrait rectangles and renders every one of the 40 statistic fields')

    v=JournalVM(pe,m);v.ready();v.calls=[]
    raw=bytearray(make());struct.pack_into('<I',raw,4,0x49554F43);v.receive(bytes(raw))
    assert any(call[0]==m['fallback'] for call in v.calls)
    extensions = full.get('extensions')
    extension_router = extensions.get('router', {}).get('vir') if extensions else m.get('extension', {}).get('routerVir')
    if extension_router:
        assert pe.get_data(m['route']['fallbackCellVir']-pe.OPTIONAL_HEADER.ImageBase,4)==struct.pack('<I',extension_router)
        if extensions:
            assert extensions['entries']['BestiaryUI']=={'magic':0x49555342,'handlerVir':m['receiver']['vir']}
        routed=JournalVM(pe,m);routed.stub(m['receiver']['vir'],0)
        routed.u.mem_write(0x15e8198,bytes(make()));routed.run(m['route']['routerVir'])
        assert any(call[0]==m['receiver']['vir'] for call in routed.calls)
    else:
        assert pe.get_data(m['route']['fallbackCellVir']-pe.OPTIONAL_HEADER.ImageBase,4)==struct.pack('<I',m['receiver']['vir'])
    checks.append('BSUI fallback wrapper preserves the shared 0x0BEF router and unrelated packet path')
    # Exercise the actual shared router entry, not only BSUI's wrapper.
    for magic,cell in [(0x49554841,'ahui'),(0x49555341,'asui'),(0x49554f43,'coui'),(0x434e4950,'pincode')]:
        v=JournalVM(pe,m)
        target=v.read32(m['route'][cell+'HandlerCellVir'])
        if target:
            v.stub(target,0);raw=bytearray(make());struct.pack_into('<I',raw,4,magic)
            v.u.mem_write(0x15e8198,bytes(raw));v.run(m['route']['routerVir'])
            assert any(call[0]==target for call in v.calls),(cell,hex(target))
    checks.append('Installed shared router dispatches every present AHUI/ASUI/COUI/PINC peer correctly')
    # Native child ownership and positioning in the smallest supported viewport.
    v=JournalVM(pe,m);v.state32(0,0);edit_vtable=v.alloc(64);v.write32(edit_vtable+16,0x60000020)
    v.stub(0xDBBC4F,0,lambda ecx,a:v.alloc(v.read32(v.u.reg_read(UC_X86_REG_ESP)+4)))
    def frame_ctor(ecx,a):v.u.mem_write(ecx+0x28,b'\1');return ecx
    def edit_ctor(ecx,a):v.write32(ecx,edit_vtable);return ecx
    v.stub(0x86B950,4,frame_ctor);v.stub(0x817DA0,0,edit_ctor)
    for addr,pop in [(0xA245C0,8),(0xA1CB70,8),(0x60000020,8),(0xA1B780,4),(0xA2D240,4)]:v.stub(addr,pop)
    renderer=v.alloc(64);v.write32(0x12515f8,renderer);v.write32(renderer+0x28,800);v.write32(renderer+0x2c,600)
    v.run('toggle');created,edit=v.state32(0),v.state32(116)
    assert created and edit and v.read32(created)==m['vtable']['vir']
    assert (v.read32(created+0x1c),v.read32(created+0x20))==(20,50)
    assert (0xA245C0,created,[760,500]) in v.calls and (0xA1B780,created,[edit]) in v.calls
    assert v.read32(edit+0x88)==27 and len(v.sent)==1
    v.focus=edit;v.capture=created;v.run('toggle');assert v.focus==0 and v.capture==0 and v.u.mem_read(created+0x28,1)==b'\0'
    v.run('toggle');assert v.u.mem_read(created+0x28,1)==b'\1' and len(v.sent)==2
    v.state32(160,3);v.run('destructor',[1],ecx=created);assert v.state32(0)==0 and v.state32(116)==0
    v.run('toggle');assert v.state32(0)!=created and v.state32(116)!=edit and v.state32(160)==0
    checks.append('800x600 viewport: 760x500 construction centered at 20,50; child edit, close/reopen and destruction')
    for foreign in [False,True]:
        v=JournalVM(pe,m);v.state32(116,0x60000a00)
        v.focus=0x60000b00 if foreign else 0x60000a00;v.capture=0x60000c00 if foreign else v.window
        v.run('destructor',[1]);assert v.state32(0)==v.state32(116)==v.state32(96)==0
        assert v.focus==(0x60000b00 if foreign else 0) and v.capture==(0x60000c00 if foreign else 0)
    checks.append('Destructor releases only Bestiary-owned focus and capture')
    v=JournalVM(pe,m);v.state32(116,0x60000a00);v.focus=0x60000a00
    v.u.mem_write(v.native_text,b'Poring\0');v.run('search');assert not v.sent and v.state32(96)==1
    v.now+=249;v.run('search');assert not v.sent
    v.now+=1;v.run('search');assert v.sent[-1][36:43]==b'Poring\0'
    v.u.mem_write(v.native_text,b'a'*60+b'\0');v.run('search');v.now+=250;v.run('search')
    assert v.sent[-1][36:64]==b'a'*27+b'\0'
    checks.append('Native Item Collection edit debounce and maximum-length search serialize correctly')
    native=struct.unpack('<53I',pe.get_data(0x102fe08-pe.OPTIONAL_HEADER.ImageBase,212))
    private=struct.unpack('<53I',pe.get_data(m['vtable']['vir']-pe.OPTIONAL_HEADER.ImageBase,212))
    assert all(private[i]==native[i] for i in range(53) if i not in ([0,20,25,28,31,32,33,35,37] if m.get("layoutVersion",0)>=12 else [0,20,25,28,30,31,32,35,37] if m.get("layoutVersion",0)>=11 else [0,20,25,28,31,35,37] if version>=3 else [0,20,25,28,31]))
    checks.append('Private vtable changes only the documented Bestiary destructor/draw/mouse slots')
    report={'passed':True,'checks':checks,'live_accepted':False}
    (directory/'journal-verification.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('build_directory',type=Path);args=ap.parse_args()
    print(json.dumps(verify(args.build_directory),indent=2))
