"""Reproduce the state/code collision, then execute caves after native lifecycle writes."""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import UcError, UC_HOOK_MEM_INVALID
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_XMM4, UC_X86_REG_XMM5, UC_X86_REG_XMM6, UC_X86_REG_XMM7
from test_celestial_dial import Machine, ROOT
from verify_floor_safe_sprite_depth import Image

def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def scalar(value):return struct.unpack('<f',struct.pack('<I',value&0xffffffff))[0]

def ownership(client):
    im=Image(client);meta=json.loads((ROOT/'Inputs/CelestialDial/runtime.json').read_text())
    base=im.u32(0x109481C)-meta['exports']['@CelestialPlayerShadowDraw@12']
    cave=im.jmp_target(0xC40F9F)-16
    return im,base,base+meta['size'],cave,cave+0xA0

def reproduce(client):
    im,start,end,cave,limit=ownership(client)
    assert cave<end and limit>start,'The regression fixture must overlap weather runtime'
    m=Machine(client);shadow=im.jmp_target(0xC49FEE)
    before=bytes(m.u.mem_read(shadow,12));m.invoke(m.c['reset'])
    after=bytes(m.u.mem_read(shadow,12));assert before!=after
    faults=[]
    def fault(uc,access,address,size,value,unused):
        faults.append(dict(pc=hex(uc.reg_read(UC_X86_REG_EIP)),address=hex(address)));return False
    m.u.hook_add(UC_HOOK_MEM_INVALID,fault);m.u.reg_write(UC_X86_REG_EAX,0)
    try:m.u.emu_start(shadow,0xC4A004,count=100)
    except UcError:pass
    assert faults and faults[0]==dict(pc=hex(shadow),address='0x0'),faults
    return dict(shadow=hex(shadow),state=hex(m.c['state']),offset_in_state=shadow-m.c['state'],before=before.hex(),after_reset=after.hex(),fault=faults[0])

def verify(client):
    im,start,end,cave,limit=ownership(client)
    assert not(cave<end and limit>start),'Render caves overlap weather runtime'
    sec=im.pe.get_section_by_rva(cave-im.base)
    assert sec and sec.Characteristics&0x20000000,'Cave section is not executable'
    m=Machine(client);original=bytes(m.u.mem_read(cave,0xA0));actor=m.alloc(0x200)
    m.w(actor,0x1094810);m.u.mem_write(actor+0x12,b'\x7f')
    cases=0
    def render():
        nonlocal cases
        assert bytes(m.u.mem_read(cave,0xA0))==original,'Native state update overwrote cave bytes'
        sp=0x40008000;bp=0x40009000
        m.u.mem_write(bp+0x1c,struct.pack('<f',300.0))
        m.u.reg_write(UC_X86_REG_ESP,sp);m.u.reg_write(UC_X86_REG_EBP,bp);m.u.reg_write(UC_X86_REG_EDI,actor)
        m.u.reg_write(UC_X86_REG_EAX,0x1234);m.u.reg_write(UC_X86_REG_EFLAGS,0x242)
        m.u.reg_write(UC_X86_REG_XMM4,bits(25.0));m.u.reg_write(UC_X86_REG_XMM5,bits(210.0))
        m.u.emu_start(im.jmp_target(0xC40F9F),0xC40FA4,count=100)
        assert scalar(m.u.reg_read(UC_X86_REG_XMM4))==0 and scalar(m.u.reg_read(UC_X86_REG_XMM5))==-90.0
        assert m.u.reg_read(UC_X86_REG_ESP)==sp and m.u.reg_read(UC_X86_REG_EAX)==0x1234
        assert m.u.reg_read(UC_X86_REG_EFLAGS)&0x40
        m.u.reg_write(UC_X86_REG_EAX,0x37);m.u.reg_write(UC_X86_REG_ECX,0xAB00)
        m.u.reg_write(UC_X86_REG_XMM7,bits(-20.0));m.u.reg_write(UC_X86_REG_XMM6,bits(20.0))
        m.u.emu_start(im.jmp_target(0xC49FEE),0xC4A004,count=100)
        assert scalar(m.u.reg_read(UC_X86_REG_XMM7))==0
        assert abs(scalar(m.u.reg_read(UC_X86_REG_XMM6))-3.2)<1e-6
        assert m.u.reg_read(UC_X86_REG_ECX)==0xAB37 and m.u.reg_read(UC_X86_REG_EAX)==0x7F
        cases+=2
    m.invoke(m.c['reset']);render()
    for name in [b'new_1-1\0',b'prt_fild08\0']:
        m.frame();m.receive(m.snapshot(map_name=name,flags=3,duration=3600000,remaining=3600000));m.frame();render()
        m.invoke(m.c['reset']);render()
    return dict(client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(),cave=[hex(cave),hex(limit)],weather_runtime=[hex(start),hex(end)],section=sec.Name.decode().rstrip('\0'),native_cave_executions_after_state_writes=cases,cave_bytes_unchanged=True,passed=True,live_client_observed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bad',type=Path,required=True);p.add_argument('--fixed',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();result=dict(reproduction=reproduce(a.bad),fixed=verify(a.fixed))
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
