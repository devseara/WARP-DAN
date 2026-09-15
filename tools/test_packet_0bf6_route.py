"""Verify the installed packet dispatcher, not privately allocated UI handlers.

Explicit protocol-boundary doubles check ownership; actual Gacha opening is
also executed through the real dispatcher when Gacha is selected.
"""
import argparse
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack
from test_gacha_ui import GachaMachine, snapshot


def route_contract(m):
    data=m.pe.get_memory_mapped_image();marker=data.find(b'SharedPacket0BF6.v1\0')
    assert marker>=0, 'No shared 0x0BF6 route: independently installed feature handlers can overwrite each other'
    key=pack(m.base+marker);positions=[];at=0
    while (at:=data.find(key,at))>=0:positions.append(at);at+=1
    assert len(positions)==1,positions
    return dict(zip(('entry','router','bpuiCell','gchaCell','fallbackCell'),struct.unpack_from('<5I',data,positions[0]+4)))


def verify(exe,expected):
    m=Machine(exe,Path('.'));r=route_contract(m)
    assert r['entry']==0xCAD0EC and m.r(r['entry'])==r['router'],'dispatcher was overwritten after shared-route installation'
    selected=set(expected.split(','))
    for name in ('gcha','bpui'):
        assert bool(m.r(r[name+'Cell']))==(name in selected),(name,'wrong selected feature registration')
    called=[]
    def boundary(name):
        def call():
            assert m.u.reg_read(UC_X86_REG_EAX)==0x12345678
            assert m.u.reg_read(UC_X86_REG_ECX)==0x23456789
            called.append(name);m.ret(0)
        return call
    for name in selected:m.stub(m.r(r[name+'Cell']),boundary(name))
    m.stub(m.r(r['fallbackCell']),boundary('stock'))
    m.stub(0xC9E1DD,boundary('ignored'))
    def receive(magic,length=8,opcode=0xBF6):
        p=struct.pack('<HHI',opcode,length,magic)
        m.u.mem_write(0x15E8198,p);m.u.reg_write(UC_X86_REG_EAX,0x12345678)
        m.invoke(m.r(r['entry']),0x23456789)
    for name,magic in [('gcha',0x41484347),('bpui',0x49555042)]:
        receive(magic);assert called[-1]==(name if name in selected else 'ignored')
    for magic,length,opcode in [(0x54534554,8,0xBF6),(0x41484347,7,0xBF6),(0x49555042,8,0xBEF)]:
        receive(magic,length,opcode);assert called[-1]=='stock'
    if 'gcha' in selected:
        g=GachaMachine(exe);p=snapshot()
        struct.pack_into('<I',p,52,0);p[672:1824]=bytes(1152) # actual initial NPC snapshot has no previous rewards
        g.receive(p);window=g.r(g.c['state'])
        assert window and g.r(window+0x28)==1,'initial empty NPC snapshot did not open Gacha through the actual dispatcher'
        g.invoke(g.c['down'],window,(746,9));g.invoke(g.c['up'],window,(746,9))
        assert g.r(window+0x28)==0
        struct.pack_into('<I',p,16,88);g.receive(p)
        assert g.r(window+0x28)==1 and g.r(g.c['state']+64+16)==88,'fresh NPC session did not reopen the window'
    print('PASS: installed 0x0BF6 dispatcher, independent '+expected+' handlers, absent-feature/stock fallback, register preservation'+
          (', real empty NPC open/close/reopen' if 'gcha' in selected else ''))
    print('Offline protocol/native-boundary checks; no live packets or purchases sent.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('exe')
    parser.add_argument('--expect',choices=('gcha','bpui','bpui,gcha'),required=True)
    args=parser.parse_args();verify(args.exe,args.expect)
