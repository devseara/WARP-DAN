"""Execute the emitted Bestiary menu child; native engine boundaries are mocked."""
from pathlib import Path
import argparse, itertools, json, struct
import pefile
from PIL import Image
from bestiary_test_vm import VM
from verify_bestiary_journal import JournalVM

ROOT=Path(__file__).resolve().parents[1]

def verify(directory):
    state=json.loads((directory/'baseline-state.json').read_text(encoding='utf-8'))
    m=state['bestiaryNative']
    menu=next(e['value'] for e in reversed(state['events']) if e['topic']=='ROGlobalZeroMenu.QjsOnly')
    button=menu['bestiary']
    pe=pefile.PE(str(directory/'baseline.exe'),fast_load=True)
    v=VM(pe,m)
    v.stub(menu['themeLoadBridgeVir'],0)
    v.stub(0xDBBC4F,0,lambda ecx,args:v.alloc(0x120))
    v.stub(0x8172B0,0,lambda ecx,args:ecx)
    parents=[];loaded=[]
    def load_image(ecx,args):
        name=v.cstring(args[0]).decode('latin-1')
        loaded.append(name)
        if args[1]==0:
            v.write32(ecx+0xBC,args[0]);v.write32(ecx+0xD0,len(name))
            size=(32,34) if '_old_' in name else (45,41)
            v.write32(ecx+0xB4,size[0]);v.write32(ecx+0xB8,size[1])
    def size_image(ecx,args):
        v.write32(ecx+0x14,args[0]);v.write32(ecx+0x18,args[1])
        surface=v.alloc(32);v.write32(surface+4,args[0]);v.write32(surface+8,args[1]);v.write32(ecx+0x24,surface)
    def add_child(ecx,args):
        parents.append((ecx,args[0]));v.write32(args[0]+0x10,ecx)
    v.stub(0x82DAC0,12,load_image);v.stub(0xA1CB70,8,size_image);v.stub(0xA1B780,4,add_child)
    v.stub(v.read32(button['buttonVtableVir']+0xD4),4,lambda ecx,a:v.write32(ecx+0x28,a[0]))
    def position(ecx,a):v.write32(ecx+0x1C,a[0]);v.write32(ecx+0x20,a[1])
    v.stub(v.read32(button['buttonVtableVir']+0x10),8,position)
    parent=v.alloc(0x200);v.write32(parent+0x28,1)
    v.u.mem_write(0x160227C,b'\1')
    checks=[]
    # Optional producer never creates an inert menu child.
    callback=v.read32(button['requestCellVir']);v.write32(button['requestCellVir'],0)
    v.run(button['ensureVir'],ecx=parent);assert not parents
    v.write32(button['requestCellVir'],callback)
    routes=[state[x] for x in ('hunt','item','support')]
    for theme in (1,0,1):
        v.write32(menu['themeStateVir'],theme)
        v.run(button['ensureVir'],ecx=parent)
        child=v.read32(button['buttonStateVir']);assert v.read32(child+0x2C)==0x3FB
        assert (v.read32(child+0x14),v.read32(child+0x18))==((45,41) if theme else (32,34))
        calls=len(loaded);v.run(button['ensureVir'],ecx=parent);assert len(loaded)==calls
        for bits in itertools.product((0,1),repeat=3):
            for bridge,bit in zip(routes,bits):v.write32(bridge['visibleVir'],bit)
            for native_count in (0,4,5,25):
                v.write32(menu['visibleMaskVir'],(1<<native_count)-1)
                v.write32(menu['gridStrideYVir'],61)
                v.write32(button['visibleVir'],1)
                v.run(button['syncVir'],ecx=parent)
                row,col=divmod(native_count+sum(bits),5)
                expected=(13+68*col,12+61*row) if theme else (9+42*col,23+43*row)
                assert (v.read32(child+0x1C),v.read32(child+0x20))==expected
                assert v.read32(child+0x28)==1
        for address,old in ((button['visibleVir'],1),(button['requestCellVir'],callback),(parent+0x28,1)):
            v.write32(address,0);v.run(button['syncVir'],ecx=parent);assert v.read32(child+0x28)==0;v.write32(address,old)
        v.u.mem_write(0x160227C,b'\0');v.run(button['syncVir'],ecx=parent);assert v.read32(child+0x28)==0;v.u.mem_write(0x160227C,b'\1')
    assert len(parents)==1
    checks.append('New/Classic/New image refresh, 96 compact-grid placements, parent/expanded/visibility/producer gates, no duplicate child')
    # Destructor clears both cached owners; recreating under another parent is valid.
    v.stub(0x81A5A0,4)
    v.run(button['buttonDestructorVir'],[0],ecx=child)
    assert v.read32(button['buttonStateVir'])==0
    second=v.alloc(0x200);v.run(button['ensureVir'],ecx=second)
    assert len(parents)==2 and parents[-1][0]==second
    checks.append('Native child destructor clears the cached owner; menu recreation attaches to the new parent')
    # Execute the unmodified journal toggle through the actual menu mouse-up.
    v=JournalVM(pe,m)
    v.run(button['buttonMouseUpVir'],[0,0]);assert v.u.mem_read(v.window+0x28,1)==b'\0'
    v.run(button['buttonMouseUpVir'],[0,0]);assert v.u.mem_read(v.window+0x28,1)==b'\1' and len(v.sent)==1
    checks.append('Actual menu mouse-up closes/reopens the Bestiary journal and sends one catalog request; stack/registers preserved')
    paths=set(loaded);assert len(paths)==6
    for path in paths:
        source=ROOT/'Images/BestiaryUI/menuicon'/Path(path.replace('\\','/')).name
        deployed=directory/'data/texture'/path.replace('\\','/')
        assert source.read_bytes()==deployed.read_bytes()
        raw=source.read_bytes();assert struct.unpack_from('<HI',raw,28)==(24,0)
        with Image.open(source) as im:assert im.size==((32,34) if '_old_' in path else (45,41))
    checks.append('All six emitted native texture paths resolve to byte-identical deployed 24-bit BI_RGB button states')
    result={'passed':True,'checks':checks,'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'bestiary-menu-verification.json').write_text(json.dumps(result,indent=2))
    return result

def verify_visibility(directory):
    expected = {'baseline':1,'hide-bestiary':0,'show-bestiary':1,
                'overlap-show-bestiary':1,'overlap-hide-bestiary':0,
                'remove-show-bestiary':0,'remove-hide-bestiary':1,
                'overlap-reapply-bestiary':1,'hide-before-menu':0,'show-disabled':0}
    baseline=json.loads((directory/'baseline-state.json').read_text(encoding='utf-8'))['bestiaryNative']
    rows=[]
    for case,visible in expected.items():
        state=json.loads((directory/(case+'-state.json')).read_text(encoding='utf-8'))
        menu=next(e['value'] for e in reversed(state['events']) if e['topic']=='ROGlobalZeroMenu.QjsOnly')
        button=menu['bestiary'];m=state.get('bestiaryNative') or baseline
        pe=pefile.PE(str(directory/(case+'.exe')),fast_load=True)
        v=VM(pe,m);v.stub(menu['themeLoadBridgeVir'],0)
        parent=v.alloc(0x200);child=v.alloc(0x120)
        v.write32(parent+0x28,1);v.write32(child,button['buttonVtableVir'])
        v.write32(button['buttonStateVir'],child)
        v.u.mem_write(0x160227C,b'\1')
        v.write32(menu['gridStrideYVir'],61)
        v.stub(v.read32(button['buttonVtableVir']+0xD4),4,lambda ecx,a:v.write32(ecx+0x28,a[0]))
        def position(ecx,a):v.write32(ecx+0x1C,a[0]);v.write32(ecx+0x20,a[1])
        v.stub(v.read32(button['buttonVtableVir']+0x10),8,position)
        for theme in (1,0,1):
            v.write32(menu['themeStateVir'],theme)
            # The visibility/request words are exactly those exported by WARP.
            v.run(button['syncVir'],ecx=parent)
            assert v.read32(child+0x28)==visible,(case,theme,visible)
            rows.append({'case':case,'theme':'renewal' if theme else 'classic','visible':bool(visible)})
    result={'passed':True,'checks':rows,'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'bestiary-theme-visibility.json').write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);ap.add_argument('--visibility',action='store_true')
    args=ap.parse_args();print(json.dumps(verify(args.directory),indent=2))
    if args.visibility:print(json.dumps(verify_visibility(args.directory),indent=2))
