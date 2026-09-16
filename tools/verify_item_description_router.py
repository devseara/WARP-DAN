"""Exercise final-PE 0x0BEF routing and static patch removal, not just source patterns."""
from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))
    pe=pefile.PE(str(directory/'item-description.exe'));base=pe.OPTIONAL_HEADER.ImageBase;route=m['sharedRoute']
    read=lambda a:struct.unpack('<I',pe.get_data(a-base,4))[0]
    receivers={0x49554841:read(route['ahuiHandlerCellVir']),0x49555341:read(route['asuiHandlerCellVir']),
        0x434e4950:read(route['pincodeHandlerCellVir']),0x49554f43:read(route['couiHandlerCellVir'])}
    registry=m.get('extensions')or{}
    for entry in registry.get('entries',{}).values():receivers[entry['magic']]=entry['handlerVir']
    receivers={k:v for k,v in receivers.items()if v};fallback=route['fallbackVir'];checks=[]
    cases=[(0xbef,8,magic,target)for magic,target in receivers.items()]+[(0xbef,8,0x12345678,fallback),(0xbef,4,0x49554449,fallback),(0xbdd,8,0x49554449,fallback)]
    for packet_id,length,magic,expected in cases:
        u=Uc(UC_ARCH_X86,UC_MODE_32);image=pe.get_memory_mapped_image();u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,image)
        u.mem_map(0x60000000,0x10000);sp=0x60008000;u.mem_write(sp,b'guard-stack-unchanged')
        u.mem_write(0x15e8198,struct.pack('<HHI',packet_id,length,magic))
        registers={UC_X86_REG_EAX:0x1234,UC_X86_REG_EBX:0x2345,UC_X86_REG_ECX:0x3456,UC_X86_REG_EDX:0x4567,UC_X86_REG_ESI:0x5678,UC_X86_REG_EDI:0x6789,UC_X86_REG_EBP:0x789a,UC_X86_REG_ESP:sp,UC_X86_REG_EFLAGS:0x246}
        for reg,value in registers.items():u.reg_write(reg,value)
        destinations=set(receivers.values())|{fallback};hit=[]
        def hook(uc,pc,size,_):
            if pc in destinations:hit.append(pc);uc.emu_stop()
        u.hook_add(UC_HOOK_CODE,hook);u.emu_start(read(route['entryVir']),0,count=2000)
        assert hit==[expected],(hex(magic),hit,hex(expected))
        # The canonical v4 route intentionally reloads EAX with a handler cell.
        for reg,value in registers.items():
            if reg!=UC_X86_REG_EAX:assert u.reg_read(reg)==value,(hex(magic),reg)
        assert bytes(u.mem_read(sp,21))==b'guard-stack-unchanged'
    checks.append('Final native dispatcher preserves all selected AHUI/ASUI/PINC/COUI/BSUI/IDUI routes and the native fallback')
    checks.append('Short/foreign packets preserve stack, flags and register ownership through routing')
    if not m.get('itemDescription'):
        assert 0x49554449 not in receivers
        for h in m['previousItemDescription']['hooks']:assert read(h['address'])==h['original']
        checks.append('Removing IDUI restores every targeted native vtable slot and removes its route')
    report={'passed':True,'checks':checks,'magics':[hex(x)for x in receivers],'live_accepted':False}
    (directory/'router-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
