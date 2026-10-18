"""Routing-only checks for Barter's added BRTR envelope; no gameplay suites."""
import argparse
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack


def verify(exe, selected):
    m = Machine(exe, Path('.'))
    data = m.pe.get_memory_mapped_image(); marker = data.find(b'SharedPacket0BF6.v1\0')
    assert marker >= 0
    record = data.find(pack(m.base+marker)); assert record >= 0
    entry, router, bpui, gcha, fallback, brtr = struct.unpack_from('<6I', data, record+4)
    assert entry == 0xCAD0EC and m.r(entry) == router
    cells = {'bpui':bpui, 'gcha':gcha, 'brtr':brtr}
    called = []
    def boundary(name):
        def call():
            assert m.u.reg_read(UC_X86_REG_EAX) == 0x12345678
            assert m.u.reg_read(UC_X86_REG_ECX) == 0x23456789
            called.append(name); m.ret(0)
        return call
    for name, cell in cells.items():
        assert bool(m.r(cell)) == (name in selected), name
        if name in selected: m.stub(m.r(cell), boundary(name))
    m.stub(m.r(fallback), boundary('stock')); m.stub(0xC9E1DD, boundary('ignored'))
    def receive(magic, length=8, opcode=0xbf6):
        m.u.mem_write(0x15E8198, struct.pack('<HHI',opcode,length,magic))
        m.u.reg_write(UC_X86_REG_EAX,0x12345678); m.invoke(m.r(entry),0x23456789)
    for name, magic in [('bpui',0x49555042),('gcha',0x41484347),('brtr',0x52545242)]:
        receive(magic); assert called[-1] == (name if name in selected else 'ignored')
    for magic, length, op in [(0x12345678,8,0xbf6),(0x52545242,7,0xbf6),(0x49555042,8,0xbef)]:
        receive(magic,length,op); assert called[-1] == 'stock'
    print('PASS: installed route, '+','.join(sorted(selected))+' ownership, absent-feature/foreign fallback and registers: '+str(exe))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('exe',type=Path)
    ap.add_argument('--selected',default='brtr'); args = ap.parse_args()
    verify(args.exe, set(args.selected.split(',')))
