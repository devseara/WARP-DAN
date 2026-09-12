"""Regression tests for V8 physical Escape, server reload and numeric formatting."""
from pathlib import Path
import argparse,json,struct
import pefile
from PIL import Image
from verify_bestiary_journal import JournalVM
from verify_bestiary_cache import reply


def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary']
    assert m['layoutVersion']>=8
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True)
    checks=[]
    def fresh():
        v=JournalVM(pe,m)
        v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]))
        v.write32(v.window,m['vtable']['vir']);v.state32(0,v.window)
        v.u.mem_write(v.window+0x28,b'\1')
        return v
    v=fresh();out=m['numberBuffer']['vir']
    for value,expected in [('0','0'),('999','999'),('1000','1,000'),('3567200','3,567,200'),
        ('71372500','71,372,500'),('1000000000000000','1,000,000,000,000,000'),
        ('18446744073709551615','18,446,744,073,709,551,615'),
        ('-9223372036854775808','-9,223,372,036,854,775,808'),('1234.5%','1,234.5%'),('N/A','N/A'),('','')]:
        v.u.mem_write(out,b'?'*64)
        v.run('numberText',[v.string(value),out])
        assert v.cstring(out).decode()==expected,(value,v.cstring(out))
        assert v.u.mem_read(out+63,1)==b'?'
    checks.append('Comma formatting preserves zero, negative, decimal percent and full 64-bit values without buffer overrun')

    manager=0x131f4e8
    def key_fixture():
        v=fresh();head=v.alloc(16);node=v.alloc(16)
        v.write32(manager+0x17c,head);v.write32(head,node);v.write32(node,head);v.write32(node+8,v.window)
        v.write32(manager+0x1b4,0)
        # Execute the patched native entry, including AutoHook. Unhandled keys
        # replay the real six-byte prologue then this minimal stock epilogue.
        v.u.mem_write(m['escapeHook']['resume'],b'\x5d\xc2\x08\x00')
        return v,node
    v,node=key_fixture();v.state32(208,1)
    v.run(m['escapeHook']['site'],[27,1],ecx=manager)
    assert v.state32(208)==0 and v.u.mem_read(v.window+0x28,1)==b'\1'
    v.state32(124,1);v.run(m['escapeHook']['site'],[27,1],ecx=manager)
    assert v.state32(124)==0 and v.u.mem_read(v.window+0x28,1)==b'\1'
    v.state32(116,0x60000a00);v.focus=0x60000a00;v.capture=v.window
    v.run(m['escapeHook']['site'],[27,1],ecx=manager)
    assert v.u.mem_read(v.window+0x28,1)==b'\0' and v.focus==0 and v.capture==0
    for condition in ['other_key','key_up','hidden','modal','foreign_front','missing','bad_vtable']:
        v,node=key_fixture();key=27;pressed=1
        if condition=='other_key':key=65
        if condition=='key_up':pressed=0
        if condition=='hidden':v.u.mem_write(v.window+0x28,b'\0')
        if condition=='modal':v.write32(manager+0x1b4,1)
        if condition=='foreign_front':
            other=v.alloc(128);v.u.mem_write(other+0x28,b'\1');v.write32(node+8,other)
        if condition=='missing':v.state32(0,0)
        if condition=='bad_vtable':v.write32(v.window,0)
        previous=bytes(v.u.mem_read(v.window+0x28,1))
        assert v.run(m['escapeHook']['site'],[key,pressed],ecx=manager)==key,condition
        assert v.u.mem_read(v.window+0x28,1)==previous,condition
    checks.append('Real ProcessPushButton entry closes owned topmost frame/popups; key-up, hidden, modal and foreign windows retain stock routing')

    def notice(revision):return struct.pack('<HHIHHII',0xbef,20,0x49555342,3,7,revision,0)
    v=fresh();before=bytes(v.u.mem_read(m['payload']['vir'],5120))
    assert struct.unpack_from('<H',v.sent[-1],106)[0]==1
    v.run('sender',[3,1,1004,0]);old=v.sent[-1]
    v.receive(notice(4));assert len(v.sent)==2 and v.state32(240)==1
    v.receive(reply(old,revision=3));assert bytes(v.u.mem_read(m['payload']['vir'],5120))==before
    v.run('requestTick');assert len(v.sent)==3 and v.state32(16)==1
    current=v.sent[-1];v.run('requestTick');assert len(v.sent)==3
    v.receive(reply(current,revision=4));assert v.state32(20)==4 and v.state32(236)==0 and v.state32(240)==0
    v.receive(notice(4));v.run('requestTick');assert len(v.sent)==3
    v.run('sender',[1,0,1002,0]);assert len(v.sent)==3,'Reopen invalidated valid server revision'
    v.u.mem_write(v.window+0x28,b'\0');v.receive(notice(5));v.run('requestTick');assert len(v.sent)==3
    v.u.mem_write(v.window+0x28,b'\1');v.run('requestTick');assert len(v.sent)==4
    checks.append('@reloadmobdb notice retires stale replies, preserves display, triggers one visible fetch and defers hidden-window fetches; reopen uses cache')

    maps=list((directory/'data/texture/bestiary/journal').glob('map_*.bmp'))
    assert maps
    for path in maps:
        with Image.open(path) as im:
            assert im.size==(94,43)
            assert not any(r>=248 and g<4 and b>=248 for r,g,b in im.convert('RGB').getdata()),path.name
    checks.append(f'All {len(maps)} minimaps contain no RGB565 magenta transparency-key pixels')
    report={'passed':True,'checks':checks,'live_accepted':False,'native_boundaries_mocked':True}
    (directory/'live-fixes-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path)
    print(json.dumps(verify(ap.parse_args().directory),indent=2))
