"""Execute current QJS-emitted x86; native engine boundaries are explicit doubles.

Run vip_menu_emit.cjs first. These checks do not establish Windows/live acceptance.
"""
import argparse, itertools, json, struct
from pathlib import Path
from types import SimpleNamespace
import pefile
from bestiary_test_vm import VM

def verify(directory, assets_report=None):
    state=json.loads((directory/'state.json').read_text(encoding='utf-8'))
    raw=(directory/'bytes.bin').read_bytes();length=state['originalLength']
    pe=pefile.PE(data=raw[:length],fast_load=True)
    base=pe.OPTIONAL_HEADER.ImageBase;extra=state['extraBase']-base
    mapped=bytearray(pe.get_memory_mapped_image());mapped.extend(bytes(extra+len(raw)-length-len(mapped)))
    mapped[extra:]=raw[length:]
    image=SimpleNamespace(OPTIONAL_HEADER=pe.OPTIONAL_HEADER,get_memory_mapped_image=lambda:bytes(mapped))
    menu=state['menu'];button=menu['vip'];routes=state['routes'];dummy=state['dummy']['vir']
    v=VM(image,{'state':{'vir':dummy},'vtable':{'vir':button['buttonVtableVir']},'timeGetTimeIat':dummy+240})
    v.stub(menu['themeLoadBridgeVir'],0)
    v.stub(0xDBBC4F,0,lambda c,a:v.alloc(0x120));v.stub(0x8172B0,0,lambda c,a:c)
    parents=[];loaded=[];sent=[];is_open=[False];available=[True]
    def load(c,a):
        name=v.cstring(a[0]).decode('latin1');loaded.append(name)
        if a[1]==0:
            size=(32,34) if '_old_' in name else (45,41)
            v.write32(c+0xBC,a[0]);v.write32(c+0xD0,len(name))
            v.write32(c+0xB4,size[0]);v.write32(c+0xB8,size[1])
    def size(c,a):
        v.write32(c+0x14,a[0]);v.write32(c+0x18,a[1]);surface=v.alloc(32)
        v.write32(surface+4,a[0]);v.write32(surface+8,a[1]);v.write32(c+0x24,surface)
    def add(c,a):parents.append((c,a[0]));v.write32(a[0]+0x10,c)
    def position(c,a):v.write32(c+0x1C,a[0]);v.write32(c+0x20,a[1])
    def close(c,a):
        was=is_open[0];is_open[0]=False;return int(was)
    def send(c,a):
        assert c==dummy and a[0]==24;sent.append(bytes(v.u.mem_read(a[1],a[0])))
    v.stub(0x82DAC0,12,load);v.stub(0xA1CB70,8,size);v.stub(0xA1B780,4,add)
    v.stub(v.read32(button['buttonVtableVir']+0xD4),4,lambda c,a:v.write32(c+0x28,a[0]))
    v.stub(v.read32(button['buttonVtableVir']+0x10),8,position)
    v.stub(state['close'],0,close)
    v.stub(state['refs']['packetCtorA'],0,lambda c,a:dummy if available[0] else 0)
    v.stub(state['refs']['packetSend'],8,send)
    parent=v.alloc(0x200);v.write32(parent+0x28,1);v.u.mem_write(0x160227C,b'\1')
    callback=v.read32(button['requestCellVir']);v.write32(button['requestCellVir'],0)
    v.run(button['ensureVir'],ecx=parent);assert not parents
    v.write32(button['requestCellVir'],callback)
    earlier=[routes[x] for x in ('Auto Hunt','Item Collection','AutoSupport','Bestiary')]
    count=0
    for theme in (1,0,1):
        v.write32(menu['themeStateVir'],theme);v.run(button['ensureVir'],ecx=parent)
        child=v.read32(button['buttonStateVir']);assert v.read32(child+0x2C)==0x3FE
        assert (v.read32(child+0x14),v.read32(child+0x18))==((45,41) if theme else (32,34))
        n=len(loaded);v.run(button['ensureVir'],ecx=parent);assert len(loaded)==n
        for bits in itertools.product((0,1),repeat=4):
            for route,bit in zip(earlier,bits):v.write32(route['visibleVir'],bit)
            for native in (0,4,5,25):
                v.write32(menu['visibleMaskVir'],(1<<native)-1);v.write32(menu['gridStrideYVir'],61)
                v.run(button['syncVir'],ecx=parent);row,col=divmod(native+sum(bits),5)
                expected=(13+68*col,12+61*row) if theme else (9+42*col,23+43*row)
                assert (v.read32(child+0x1C),v.read32(child+0x20))==expected
                assert v.read32(child+0x28)==1;count+=1
        for address,old in ((button['visibleVir'],1),(button['requestCellVir'],callback),(parent+0x28,1)):
            v.write32(address,0);v.run(button['syncVir'],ecx=parent);assert not v.read32(child+0x28);v.write32(address,old)
        v.u.mem_write(0x160227C,b'\0');v.run(button['syncVir'],ecx=parent);assert not v.read32(child+0x28);v.u.mem_write(0x160227C,b'\1')
    assert len(parents)==1 and len(set(loaded))==6
    expected={f'bt_vip_{theme}{state}.bmp' for theme in ('','old_') for state in ('normal','mouseon','pressed')}
    assert {name.rsplit('\\',1)[-1] for name in loaded}==expected
    for name in loaded:
        assert '\\uirenewal\\menuicon\\' in name, 'VIP runtime uses a different menu asset folder'
    if assets_report:
        installed=json.loads(assets_report.read_text(encoding='utf-8'))
        texture_root=Path(installed['textureRoot'])
        source=Path(__file__).resolve().parents[1]/'Assets/VipUI/menuicon'
        for name in set(loaded):
            deployed=texture_root/Path(name.replace('\\','/'))
            assert deployed.is_file(), f'Emitted texture path not installed: {name}'
            assert deployed.read_bytes()==(source/deployed.name).read_bytes()
    # All 25 native nodes, five optional buttons and MENU occupy seven rows.
    head=v.alloc(32);nodes=[v.alloc(32) for _ in state['commandGrid']]
    v.write32(head,nodes[0]);v.u.mem_write(head+13,b'\1')
    for i,(node,(command,index)) in enumerate(zip(nodes,state['commandGrid'])):
        v.write32(node,head);v.write32(node+4,nodes[i-1] if i else head)
        v.write32(node+8,nodes[i+1] if i+1<len(nodes) else head)
        v.write32(node+16,command);v.write32(node+20,child)
    v.write32(parent+state['treeOffsets'][0],head)
    for route in routes.values():v.write32(route['visibleVir'],1)
    v.run(menu['measureRowsVir'],ecx=parent)
    assert v.read32(menu['rowCountVir'])==7 and v.read32(menu['panelHeightVir'])==444
    v.write32(button['visibleVir'],0);v.run(menu['measureRowsVir'],ecx=parent);assert v.read32(menu['rowCountVir'])==6
    v.write32(button['visibleVir'],1)
    # Exact dedicated wire request, close without reopening, allocation failure,
    # missing producer, recreation, and callback stack/register preservation.
    def click():v.run(button['buttonMouseUpVir'],[0,0],ecx=child)
    click();assert sent==[struct.pack('<HHIHHIII',0xBFA,24,0x55504956,4,13,0,0,0)]
    is_open[0]=True;click();assert not is_open[0] and len(sent)==1
    click();assert len(sent)==2
    available[0]=False;click();assert len(sent)==2
    v.write32(button['requestCellVir'],0);click();assert len(sent)==2
    v.write32(button['requestCellVir'],callback)
    v.stub(0x81A5A0,4);v.run(button['buttonDestructorVir'],[0],ecx=child)
    assert not v.read32(button['buttonStateVir'])
    second=v.alloc(0x200);v.run(button['ensureVir'],ecx=second);assert len(parents)==2 and parents[-1][0]==second
    result={'passed':True,'placements':count,'native_engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: 192 placements after Bestiary, both themes/six image states, seven-row maximum, producer/visibility/parent gates, exact VIP open packet, close/reopen and native child recreation; ABI preserved')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--assets-report',type=Path)
    args=parser.parse_args();verify(args.directory,args.assets_report)
