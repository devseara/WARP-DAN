"""Check the native header underlay boundary and the grade-tinted card header."""
from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from verify_item_description_native import VM,WIN,ITEM,PIXELS
from verify_item_description_comparison import DualVM,COMP,COMP_PIXELS
ROOT=Path(__file__).resolve().parents[1]

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    hook=m['headerHook'];site=hook['address'];resume=hook['resume'];code=pe.get_data(site-0x400000,7)
    assert code[0]==0xe9 and code[5:]==b'\x90\x90' and site+5+struct.unpack_from('<i',code,1)[0]==hook['bridge']['vir']
    baseline=json.loads((ROOT/'tools/fixtures/item_description/baseline.json').read_text())
    title=bytes.fromhex(baseline['title_bytes'])
    assert pe.get_data(baseline['title_address']-0x400000,len(title))==title,'native title producer/draw path changed'
    def fresh():
        v=VM(pe,m);v.open();assert v.receive(v.response())==1;return v
    def pixel(v,x,y,pixels=PIXELS,w=None):return v.read32(pixels+(y*(w or v.read32(WIN+0x14))+x)*4)&0xffffff
    v=fresh();registers=[UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP]
    captured={};passes=[]
    def observe(u,pc,size,_):
        if pc==site:captured['regs']=[u.reg_read(r) for r in registers]
        if pc==resume:
            assert [u.reg_read(r) for r in registers]==captured['regs'],'underlay clobbered native draw registers/stack'
            flags=u.reg_read(UC_X86_REG_EFLAGS)
            assert flags&1==0 and bool(flags&0x40)==(v.read32(WIN+0x1d4)==0),'displaced CMP semantics changed'
            passes.append(True)
    v.u.hook_add(UC_HOOK_CODE,observe)
    v.run('Draw');v.write32(WIN+0x1d4,8);v.run('Draw');assert len(passes)==2
    assert pixel(v,0,0)==0xff00ff and pixel(v,200,2) not in (0xffffff,0xff00ff),'tinted header with keyed corners'
    assert pixel(v,40,60)==0xffffff,'white backing under the native 75x100 art'
    assert all(((pixel(v,150,20)>>s)&255)>=0xe0 for s in (0,8,16)),'frosted bar under the native title'
    assert any(x==113 and y==98 and text=='Unbound' for x,y,text,*_ in v.draws) and any(text=='Weapon' for _,_,text,*_ in v.draws)
    assert pixel(v,100,104)==0xffffff and pixel(v,101,101)!=0xffffff,'open lock for an unbound item'
    bound=fresh();data=bound.response();data[64:96]=b'Character bound\0'.ljust(32,b'\0')
    bound.s('pending',1);assert bound.receive(data)==1;bound.run('Draw')
    assert pixel(bound,101,101)==0xffffff and any(text=='Character bound' for _,_,text,*_ in bound.draws),'closed lock for a bound item'
    # Unowned windows, forced-stock and stale item identities retain stock
    # backing. Nothing is painted using another window's title/color.
    other=0x50103000;v.u.mem_write(other,bytes(0x300));v.write32(other+0x1f8,12)
    before=bytes(v.u.mem_read(PIXELS,v.surface_size));v.run('Header',[other],ecx=0);assert bytes(v.u.mem_read(PIXELS,v.surface_size))==before
    for mode in ['loading','forced','stale']:
        t=VM(pe,m);t.open()
        if mode!='loading':assert t.receive(t.response())==1
        if mode=='forced':t.s('force',1)
        if mode=='stale':t.write32(WIN+0xb8+0x60,9)
        before=bytes(t.u.mem_read(PIXELS,t.surface_size));t.run('Header',[WIN],ecx=0)
        changed=bytes(t.u.mem_read(PIXELS,t.surface_size))!=before
        assert changed==(mode=='loading'),mode
    t=fresh();t.write32(t.renderer+0x28,320);t.write32(t.renderer+0x2c,300);t.s('origin',1);t.run('Message',[0,24,ITEM,0,0,0]);t.s('origin',0);t.receive(t.response());t.run('Draw')
    assert t.read32(WIN+0x14)==288 and bytes(t.u.mem_read(PIXELS+t.surface_size,64))==b'\xcd'*64
    d=DualVM(pe,m);right,left=d.open_pair();d.receive(right);d.receive(left);d.run('Draw',ecx=COMP)
    w=d.read32(COMP+0x14);assert pixel(d,200,2,COMP_PIXELS,w) not in (0xffffff,0xff00ff)
    assert d.read32(COMP+0x1f8)==0xea and any(text=='Equipped' for _,_,text,*_ in d.draws)
    report={'passed':True,'checks':['actual pre-title detour preserves registers/stack and replays the displaced CMP',
        'native title instructions match the accepted baseline byte-for-byte','grade-tinted header, white art backing, frosted title bar, open/closed binding lock',
        'the opening skeleton paints the header; forced-stock, unrelated and stale views keep stock backing','comparison underlay resolves its exact owner; small-window writes stay bounded'],
        'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'header-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
