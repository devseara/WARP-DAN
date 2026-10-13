"""Execute QJS-emitted cursor routing code, without generating a client EXE."""
import argparse
from itertools import product
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS)


def verify(case):
    route=case['route'];callbacks=case['callbacks'];count=0
    for inventory_hand,cart_hand,storage_hand in product([False,True],repeat=3):
        for flags in [0x202,0x246,0xA97]:
            u=Uc(UC_ARCH_X86,UC_MODE_32)
            u.mem_map(0x400000,0x4000000);u.mem_map(0x60000000,0x10000)
            for blob in case['code']:u.mem_write(blob['address'],bytes.fromhex(blob['hex']))
            for name in ['inventory','cart','storage']:
                u.mem_write(route[name+'CellVir'],struct.pack('<I',callbacks.get(name,0)))
            # Preserve the thiscall mode pointer, registers and flags at dispatch.
            registers=[UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,
                       UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP]
            values=[0x1234,0x2345,0x60001000,0x4567,0x5678,0x6789,0x789A]
            for reg,value in zip(registers,values):u.reg_write(reg,value)
            u.reg_write(UC_X86_REG_ESP,0x60008000);u.reg_write(UC_X86_REG_EFLAGS,flags)
            trace=[]
            def reached(uc,address,size,data):
                if address not in [*callbacks.values(),0xA74410]:return
                assert [uc.reg_read(reg) for reg in registers]==values,(case['label'],'register clobber')
                assert uc.reg_read(UC_X86_REG_EFLAGS)==flags,(case['label'],'flags clobber')
                assert uc.reg_read(UC_X86_REG_ESP)==0x60008000,(case['label'],'stack imbalance')
                if address==callbacks.get('inventory'):
                    trace.append('inventory')
                    if inventory_hand:uc.emu_stop()
                    else:uc.reg_write(UC_X86_REG_EIP,route['cartDispatchVir'])
                elif address==callbacks.get('cart'):
                    trace.append('cart')
                    if cart_hand:uc.emu_stop()
                    else:uc.reg_write(UC_X86_REG_EIP,route['storageDispatchVir'])
                elif address==callbacks.get('storage'):
                    trace.append('storage')
                    if storage_hand:uc.emu_stop()
                    else:uc.reg_write(UC_X86_REG_EIP,0xA74410)
                else:trace.append('native/Battle Pass');uc.emu_stop()
            u.hook_add(UC_HOOK_CODE,reached);u.emu_start(route['routerVir'],0,count=100)
            expected=[]
            if 'inventory' in callbacks:expected.append('inventory')
            if not ('inventory' in callbacks and inventory_hand):
                if 'cart' in callbacks:expected.append('cart')
                if not ('cart' in callbacks and cart_hand):
                    if 'storage' in callbacks:expected.append('storage')
                    if not ('storage' in callbacks and storage_hand):expected.append('native/Battle Pass')
            assert trace==expected,(case['label'],trace,expected);count+=1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('cases',type=Path)
    args=parser.parse_args();cases=json.loads(args.cases.read_text())
    count=sum(verify(case) for case in cases)
    print(f'PASS {count} x86 dispatcher scenarios across {len(cases)} patch/lifecycle states; '
          'registers, flags, stack and native/Battle Pass fallback preserved')


if __name__=='__main__':main()
