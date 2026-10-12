"""Profile and verify the embedded GRF list of the recorded v11 test fixture."""
import struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX
REFERENCE_HASH='f0d962c64c0449eaec24010c75a331ee087a4807fb8bdd42e3d097680e99709c'

def embedded_profile(pe):
    base=pe.OPTIONAL_HEADER.ImageBase;start=0x181f2f0;pos=start;rows=[];manager=addpak=None
    while pe.get_data(pos-base,1)==b'\xe8':
        length=struct.unpack('<i',pe.get_data(pos-base+1,4))[0]
        if not 1<=length<=128:raise ValueError('Unexpected embedded filename length')
        name=pe.get_data(pos-base+5,length)
        if name[-1:]!=b'\0':raise ValueError('Unterminated embedded GRF name')
        suffix=pe.get_data(pos-base+5+length,10)
        if suffix[0]!=0xb9 or suffix[5]!=0xe8:raise ValueError('Unprofiled AddPak stub')
        m=struct.unpack_from('<I',suffix,1)[0];target=pos+5+length+10+struct.unpack_from('<i',suffix,6)[0]
        if manager is not None and (m,target)!=(manager,addpak):raise ValueError('Mixed GRF loader ABI')
        manager,addpak=m,target;rows.append(name[:-1].decode('ascii'));pos+=5+length+10
    if pe.get_data(pos-base,1)!=b'\xc3' or len(rows)!=8:raise ValueError('Unprofiled embedded list')
    calls=[]
    for section in pe.sections:
        if not section.Characteristics&0x20000000:continue
        raw=section.get_data();at=0
        while (at:=raw.find(b'\xe8',at))>=0:
            if at+5<=len(raw):
                va=base+section.VirtualAddress+at
                if va+5+struct.unpack_from('<i',raw,at+1)[0]==start:calls.append(va)
            at+=1
    if len(calls)!=1:raise ValueError('Embedded list startup call is not unique')
    return dict(start=start,call=calls[0],original=pe.get_data(calls[0]-base,5).hex(),manager=manager,addpak=addpak,old_priority=list(reversed(rows)))

def verify_loader(pe,profile,names):
    base=pe.OPTIONAL_HEADER.ImageBase;call=pe.get_data(profile['call']-base,5);entry=profile['call']+5+struct.unpack_from('<i',call,1)[0]
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
    u.mem_map(0x30000000,0x10000);sp=0x30008000;stop=0x30009000;u.mem_write(sp,struct.pack('<I',stop));u.reg_write(UC_X86_REG_ESP,sp)
    actual=[];u.mem_write(profile['addpak'],b'\xc2\x04\x00')
    def hook(machine,address,size,extra):
        if address!=profile['addpak']:return
        assert machine.reg_read(UC_X86_REG_ECX)==profile['manager']
        arg=struct.unpack('<I',machine.mem_read(machine.reg_read(UC_X86_REG_ESP)+4,4))[0]
        value=bytearray()
        for i in range(128):
            c=machine.mem_read(arg+i,1)[0]
            if c==0:break
            value.append(c)
        actual.append(value.decode('ascii'));machine.reg_write(UC_X86_REG_EAX,1)
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry,stop,count=10000)
    assert actual==list(reversed(names)),actual
    assert u.reg_read(UC_X86_REG_ESP)==sp+4
    return entry
