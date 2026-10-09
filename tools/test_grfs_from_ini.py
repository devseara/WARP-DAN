"""Run emitted 2025-07-16 GRFsFromIni x86 with read-only Win32/GRF boundaries.

Reproduces the unterminated filename/underallocated Riftlock marker regression.
No game process, file, registry or archive is changed.
"""
import argparse, configparser, json, re, struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

def verify(exe, ini, broken=False):
    raw=Path(exe).read_bytes();pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase
    mapped=pe.get_memory_mapped_image()
    candidates=[]
    for m in re.finditer(b'GetPrivateProfileStringA\x00',mapped):
        start=mapped.rfind(b'\xc8\x84\x00\x00\x60',max(0,m.start()-96),m.start())
        if start>=0:candidates.append(start)
    assert len(candidates)==1,candidates
    entry=base+candidates[0]
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,mapped)
    u.mem_map(0x30000000,0x20000);stop=0x30010000;sp=0x3000fff0
    def rd(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def wr(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def string(a):return bytes(u.mem_read(a,512)).split(b'\0')[0].decode('latin1')
    def args(n):return [rd(u.reg_read(UC_X86_REG_ESP)+4+i*4) for i in range(n)]
    def ret(n,value):
        esp=u.reg_read(UC_X86_REG_ESP);target=rd(esp)
        u.reg_write(UC_X86_REG_EAX,value&0xffffffff)
        u.reg_write(UC_X86_REG_ECX,0xdead0001);u.reg_write(UC_X86_REG_EDX,0xdead0002)
        u.reg_write(UC_X86_REG_ESP,esp+n+4);u.reg_write(UC_X86_REG_EIP,target)
    addresses={name:0x30011000+i*16 for i,name in enumerate(['GetModuleHandleA','GetProcAddress','GetPrivateProfileStringA','WritePrivateProfileStringA','GetFileAttributesA'])}
    for dll in pe.DIRECTORY_ENTRY_IMPORT:
        for imp in dll.imports:
            if imp.name and imp.name.decode() in addresses:wr(imp.address,addresses[imp.name.decode()])
    config=configparser.ConfigParser();config.read(ini)
    names={str(i):config.get('Data',str(i),fallback=str(i)) for i in range(10)}
    existing={v for v in names.values() if (Path(ini).parent/v).is_file()}
    calls=[];filenames=[];writes=[]
    def hook(uc,addr,size,user):
        if addr==stop:u.emu_stop();return
        if addr==addresses['GetModuleHandleA']:ret(4,1)
        elif addr==addresses['GetProcAddress']:ret(8,addresses[string(args(2)[1])])
        elif addr==addresses['GetPrivateProfileStringA']:
            section,key,default,buffer,capacity,path=args(6)
            filename=string(path);filenames.append(filename)
            value=names.get(string(key),string(default)) if filename.lower()=='.\\'+Path(ini).name.lower() else string(default)
            data=value.encode('latin1')[:capacity-1];u.mem_write(buffer,data+b'\0');ret(24,len(data))
        elif addr==addresses['GetFileAttributesA']:ret(4,0x20 if string(args(1)[0]) in existing else 0xffffffff)
        elif addr==addresses['WritePrivateProfileStringA']:
            writes.append(string(args(4)[3]));ret(16,0) # read-only boundary, never create an INI
        elif addr==0xA88890:
            assert u.reg_read(UC_X86_REG_ECX)==0x159D410
            calls.append(string(args(1)[0]));ret(4,1)
    u.hook_add(UC_HOOK_CODE,hook)
    saved=[UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP]
    for i,r in enumerate(saved):u.reg_write(r,0x10000+i)
    wr(sp,stop);u.reg_write(UC_X86_REG_ESP,sp);u.emu_start(entry,stop,count=10000)
    assert u.reg_read(UC_X86_REG_EIP)==stop and u.reg_read(UC_X86_REG_ESP)==sp+4
    assert all(u.reg_read(r)==0x10000+i for i,r in enumerate(saved))
    expected=[names[str(i)] for i in range(9,-1,-1) if names[str(i)] in existing]
    if broken:
        assert not calls and filenames and all(p.lower()!='.\\'+Path(ini).name.lower() for p in filenames)
        print('REPRODUCED: emitted loader reads corrupted INI filename and opens zero GRFs:',repr(filenames[0]))
    else:
        assert calls==expected,(calls,expected,filenames)
        assert not writes and all(p.lower()=='.\\'+Path(ini).name.lower() for p in filenames)
        marker=b'RIFTLOCK_GRFS_V1|ini|'+Path(ini).name.encode()+b'\0'
        assert raw.count(marker)==1,'GRF marker is missing or overwritten by the following allocation'
        assert b'.\\'+Path(ini).name.encode()+b'\0'+marker in raw,'INI must terminate before metadata'
        print('PASS: emitted x86 loads all existing GRFs in priority order, skips missing indexes, preserves registers/stack, and retains the full isolated marker.')
    return {'entry':hex(entry),'loaded':calls,'expected':expected,'filenames':filenames,'stack_and_registers_preserved':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');p.add_argument('--ini',type=Path,required=True);p.add_argument('--expect-broken',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();result=verify(a.exe,a.ini,a.expect_broken)
    if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
