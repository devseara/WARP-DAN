"""Execute real WARP-emitted GrayMap x86; native GPU boundaries are mocked.

Checks command routing, ABI, on/off restoration, and the original terrain
producer. This does not establish live DirectX or visual acceptance.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS)
from unicorn.x86_const import UC_X86_REG_XMM0
from build_graymap import SOURCE

REGS = [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
        UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]


class Machine:
    def __init__(self, path):
        self.pe = pefile.PE(str(path))
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(0x400000, (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.u.mem_write(0x400000, self.pe.get_memory_mapped_image())
        self.u.mem_map(0x60000000, 0x200000)
        self.stop, self.sp, self.heap = 0x60000000, 0x60010000, 0x60020000
        self.stubs, self.events, self.options = {}, [], {0x77: 1, 10002: 1}
        self.stub(0x68EA70, 0, lambda args: self.options.get(args[0], 0), argc=1)
        self.stub(0x68FD50, 0, self.set_option, argc=2)
        self.stub(0x550B10, 8, lambda args: self.submit(args, 32))
        self.stub(0x550A50, 8, lambda args: self.submit(args, 40))
        self.stub(0x53ADD0, 0, lambda args: self.polygon())
        self.stub(0x554380, 12, self.project)
        self.stub(0xDBBBD4, 0, lambda args: 0)  # stock security-cookie epilogue
        self.stub(0x55FFE0, 0, lambda args: 0)  # recycled two-texture poly reset
        self.renderer = self.alloc(0x1000)
        self.put(0x12515F8, self.renderer)
        self.put(self.renderer + 0x28, 640)
        self.put(self.renderer + 0x2C, 480)
        self.put(self.renderer + 0x38, 1)

    def alloc(self, size):
        p = self.heap
        self.heap += (size + 15) & ~15
        return p

    def put(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))

    def get(self, address):
        return struct.unpack('<I', self.u.mem_read(address, 4))[0]

    def stub(self, address, pop, callback, argc=None):
        if address not in self.stubs:
            self.u.hook_add(UC_HOOK_CODE, self.step, begin=address, end=address)
        self.stubs[address] = (pop, callback, pop // 4 if argc is None else argc)
        self.u.mem_write(address, b'\xc3')

    def set_option(self, args):
        self.options[args[0]] = args[1]
        return 1

    def step(self, u, address, size, user):
        if address in self.stubs:
            pop, callback, argc = self.stubs[address]
            sp = u.reg_read(UC_X86_REG_ESP)
            args = [self.get(sp + 4 + i * 4) for i in range(argc)]
            value = callback(args)
            u.reg_write(UC_X86_REG_EAX, value or 0)
            u.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
            u.reg_write(UC_X86_REG_EIP, self.get(sp))

    def run(self, entry, args=(), pop=None, ecx=0x12345678, ebp=0x778899AA, eax=0x11223344):
        for reg, value in zip(REGS, [eax, 0x22334455, ecx, 0x44556677,
                                    0x55667788, 0x66778899, ebp]):
            self.u.reg_write(reg, value)
        saved = [self.u.reg_read(r) for r in REGS]
        self.u.reg_write(UC_X86_REG_ESP, self.sp)
        self.u.reg_write(UC_X86_REG_EFLAGS, 0x246)
        self.u.mem_write(self.sp, struct.pack('<' + 'I' * (len(args) + 1), self.stop, *args))
        self.u.emu_start(entry, self.stop, count=30000000)
        assert self.u.reg_read(UC_X86_REG_EIP) == self.stop, 'native continuation missing'
        assert self.u.reg_read(UC_X86_REG_ESP) == self.sp + 4 + (len(args) * 4 if pop is None else pop), 'stack imbalance'
        for i in (1, 4, 5, 6):
            assert self.u.reg_read(REGS[i]) == saved[i], 'callee-saved register clobbered'
        return self.u.reg_read(UC_X86_REG_EAX)

    def dispatch(self, text, settings=False):
        bp, sp, caller, string = self.sp, self.sp - 0x100, self.sp + 0x200, self.sp + 0x400
        self.u.mem_write(string, text.encode() + b'\0')
        self.put(sp, 0x12341234)
        self.put(bp, caller)
        self.put(bp + 8, string)
        self.put(caller + 4, 0x68FCE8 if settings else 0x500000)
        self.u.reg_write(UC_X86_REG_EBP, bp)
        self.u.reg_write(UC_X86_REG_ESP, sp)
        self.u.emu_start(0xD5CDF4, 0xD5CDFA, count=30000000)
        assert self.u.reg_read(UC_X86_REG_EIP) == 0xD5CDFA
        assert self.u.reg_read(UC_X86_REG_ESP) == sp + 4
        assert self.u.reg_read(UC_X86_REG_EDI) == 0x12341234
        return self.u.reg_read(UC_X86_REG_EAX)

    def polygon(self):
        poly, vertices = self.alloc(0x28), self.alloc(160)
        self.put(poly, vertices)
        self.put(poly + 4, 4)
        return poly

    def submit(self, args, stride):
        poly, flags = args
        self.events.append(dict(flags=flags, stride=stride,
            texture=self.get(poly + (8 if stride == 32 else 16)),
            texture2=self.get(poly + 20) if stride == 40 else None,
            vertices=bytes(self.u.mem_read(self.get(poly), stride * 4)).hex()))
        return 0

    def project(self, args):
        source, transform, dest = args
        x, y, z = struct.unpack('<fff', self.u.mem_read(source, 12))
        self.u.mem_write(dest, struct.pack('<ffff', x, y, z, 1.0))
        return 0

    def quad(self):
        quad = self.alloc(0xA0)
        for i, (x, y) in enumerate([(10., 10.), (30., 10.), (30., 30.), (10., 30.)]):
            self.u.mem_write(quad + 32 * i, struct.pack('<fffIffff', x, y, .5,
                0xFF112233 + i * 0x10101, 0., 0., 1., 1.))
        self.put(quad + 0x84, 0x11110000)
        self.put(quad + 0x88, 0x22220000)
        return quad

    def producer(self, quad, dual, option):
        self.events.clear()
        self.options[0x77] = option
        self.u.mem_write(0x11DCEC4, bytes([dual]))
        # Native combined-texture ring pool, one reusable polygon at index 0.
        poly, table, owner = self.polygon(), self.alloc(256), self.alloc(4)
        ring = self.renderer + 0x90
        self.put(table, poly)
        self.put(owner, ring)
        for off, value in ((4, table), (8, 64), (12, 0), (16, 1), (20, owner), (28, 0)):
            self.put(ring + off, value)
        self.run(0xA63E10, [0, quad, 0])
        return list(self.events)

    def alternate(self, quad):
        self.events.clear()
        ground, cells, rect = self.alloc(0xB0), self.alloc(0x54), self.alloc(16)
        self.put(ground + 8, 1)
        self.put(ground + 12, 1)
        self.put(ground + 0x7C, cells)
        for off in (0x40, 0x44, 0x48):
            self.put(cells + off, quad)
        self.run(0xA63A80, [0, rect, 0], ecx=ground)
        return list(self.events)


def verify(folder):
    m = json.loads((folder / 'manifest.json').read_text())
    path = folder / 'graymap.exe'
    vm = Machine(path)
    source = Path(m.get('source', SOURCE))
    original = pefile.PE(str(source))
    def imports(pe):
        return [(d.dll, [(i.name, i.ordinal) for i in d.imports]) for d in pe.DIRECTORY_ENTRY_IMPORT]
    assert imports(vm.pe) == imports(original), 'import table changed'
    state = m['graymap']
    if not state:
        for hook in m['previous']['hooks']:
            rva = hook['site'] - 0x400000
            size=hook.get('size',5)
            assert vm.pe.get_data(rva, size) == original.get_data(rva, size), 'removed hook remains'
        assert vm.dispatch('/graymap') == 3, 'removed slash command remains'
        return dict(build=str(folder), removed=True, passed=True)
    flag = state['state']['vir']
    assert vm.get(flag) == 0, 'must start disabled'
    if state.get('dispatch'):
        # Incremental installs must delegate every existing command with the
        # exact original registers, flags and saved-EDI stack slot intact.
        for command, settings in [('/fps', False), ('/ping', False),
                                  ('/shownpcname', False), ('/graymap_extra', False),
                                  ('/graymap', True)]:
            bp, sp, text, caller = vm.sp, vm.sp - 0x100, vm.sp + 0x400, vm.sp + 0x200
            vm.u.mem_write(text, command.encode() + b'\0')
            vm.put(bp, caller); vm.put(bp + 8, text)
            vm.put(caller + 4, 0x68FCE8 if settings else 0x500000)
            vm.put(sp, 0x12341234)
            for reg, value in zip(REGS, [11, 22, 33, 44, 55, 66, bp]):
                vm.u.reg_write(reg, value)
            vm.u.reg_write(UC_X86_REG_ESP, sp)
            vm.u.reg_write(UC_X86_REG_EFLAGS, 0x246)
            saved = [vm.u.reg_read(r) for r in REGS]
            previous = state['dispatch']['previousVir']
            vm.u.emu_start(0xD5CDF4, previous, count=10000)
            assert vm.u.reg_read(UC_X86_REG_EIP) == previous, 'existing command was intercepted'
            assert [vm.u.reg_read(r) for r in REGS] == saved
            assert vm.u.reg_read(UC_X86_REG_ESP) == sp and vm.get(sp) == 0x12341234
            assert vm.u.reg_read(UC_X86_REG_EFLAGS) == 0x246
            assert vm.get(flag) == 0
    if '/fps' in [entry['command'] for group in m['commands'].values() for entry in group]:
        for expected in (0, 1):
            assert vm.dispatch('/fps') == 0
            assert vm.options[10002] == expected and vm.get(flag) == 0, 'slash-command ownership collision'
    assert vm.dispatch('/graymap_extra') == 3 and vm.get(flag) == 0
    assert vm.dispatch('/unknown') == 3 and vm.get(flag) == 0
    assert vm.dispatch('/graymap', settings=True) == 3 and vm.get(flag) == 0, 'settings lookup toggled terrain'
    for expected in [1, 0, 1, 0]:
        assert vm.dispatch('/graymap') == 0
        assert vm.get(flag) == expected
    for expected in [1, 0]:
        vm.run(state['toggle']['vir'])
        assert vm.get(flag) == expected
        assert vm.u.reg_read(UC_X86_REG_EFLAGS) == 0x246, 'toggle clobbered flags'
    # All three terrain call sites share the same ABI and guarded submission.
    for hook in state['hooks']:
        site = hook['site']
        if hook.get('encoding')=='pointer':
            actual=struct.unpack('<I',vm.pe.get_data(site-0x400000,4))[0]
        else:
            assert vm.pe.get_data(site - 0x400000, 1) == (b'\xe9' if hook.get('encoding')=='jump' else b'\xe8')
            actual = site + 5 + struct.unpack('<i', vm.pe.get_data(site - 0x400000 + 1, 4))[0]
        assert actual == hook.get('target',state.get(hook['kind'],{}).get('vir'))
    for enabled in (0, 1, 0):
        vm.put(flag, enabled)
        for option in (0, 1):
            vm.options[0x77] = option
            assert vm.run(state['option']['vir'], [0x77], pop=0) == (0 if enabled else option)
        poly = vm.polygon()
        vertices = vm.get(poly)
        payload = bytearray(range(128))
        for i, alpha in enumerate([0xFF, 0x80, 0x40, 0]):
            struct.pack_into('<I', payload, i * 32 + 16, (alpha << 24) | 0x123456)
        vm.u.mem_write(vertices, bytes(payload))
        vm.put(poly + 8, 0x12345678)
        vm.events.clear()
        frame=vm.alloc(256)+160
        vm.put(frame+12,vm.quad())
        xmm_values=[0x3F8000003F8000003F8000003F800000+i for i in range(8)]
        for i,value in enumerate(xmm_values):vm.u.reg_write(UC_X86_REG_XMM0+i,value)
        vm.run(state['submit']['vir'], [poly, 0x800],ebp=frame)
        assert [vm.u.reg_read(UC_X86_REG_XMM0+i) for i in range(8)]==xmm_values,'submission changed producer SSE temporaries'
        event = vm.events[0]
        expected = bytearray(payload)
        if enabled:
            for i in range(4):
                expected[i * 32 + 16:i * 32 + 19] = b'\x80' * 3
        assert event['vertices'] == expected.hex(), 'gray bridge altered unrelated vertex fields'
        assert event['texture'] == (0 if enabled else 0x12345678)
        assert event['flags'] == (0 if enabled else 0x800)
    # Execute the original terrain builder, including both native lighting
    # branches. A baseline machine retains the original five call targets.
    baseline = Machine(source)
    quad, native_quad = vm.quad(), baseline.quad()
    original_quad = bytes(vm.u.mem_read(quad, 0xA0))
    vectors = 0
    for dual in (0, 1):
        for option in (0, 1):
            expected = baseline.producer(native_quad, dual, option)
            assert expected, 'terrain fixture emitted no geometry'
            for enabled in (0, 1, 0):
                vm.put(flag, enabled)
                events = vm.producer(quad, dual, option)
                assert bytes(vm.u.mem_read(quad, 0xA0)) == original_quad, 'map-owned data mutated'
                assert vm.options[0x77] == option, 'native lightmap option mutated'
                if not enabled:
                    assert events == expected, 'off did not reproduce original terrain submissions'
                else:
                    assert len(events) == 1, 'gray mode emitted a shadow/combined pass'
                    assert events[0]['flags'] == 0 and events[0]['texture'] == 0
                    verts = bytes.fromhex(events[0]['vertices'])
                    assert all(verts[i * 32 + 16:i * 32 + 19] == b'\x80' * 3 for i in range(4))
                vectors += 1
    # The alternate ground path emits its top and both side surfaces through
    # separate call sites, with native half-alpha. Exercise all three together.
    expected = baseline.alternate(native_quad)
    assert len(expected) == 3, 'alternate terrain fixture missed a surface'
    for enabled in (0, 1, 0):
        vm.put(flag, enabled)
        events = vm.alternate(quad)
        assert len(events) == 3
        assert bytes(vm.u.mem_read(quad, 0xA0)) == original_quad
        if not enabled:
            assert events == expected, 'alternate off path differs from original'
        else:
            for event in events:
                assert event['flags'] == 0 and event['texture'] == 0
                verts = bytes.fromhex(event['vertices'])
                assert all(verts[i * 32 + 16:i * 32 + 20] == b'\x80' * 4 for i in range(4)), 'alternate gray lost native alpha'
        vectors += 1
    style_vectors=verify_style(vm,state) if state.get('style') else 0
    return dict(build=str(folder), passed=True, producer_vectors=vectors, style_vectors=style_vectors,live_accepted=False)


def verify_style(vm,m):
    flag=m['state']['vir']
    assert vm.get(flag+4)==1 and vm.get(flag+8)==1
    ground,res,gat,quad=vm.alloc(0xB0),vm.alloc(0x140),vm.alloc(8*8*20),vm.quad()
    vm.put(ground+4,res);vm.put(ground+8,4);vm.put(ground+12,4)
    vm.u.mem_write(ground+16,struct.pack('<f',10.0))
    vm.put(res+0x110,8);vm.put(res+0x114,8);vm.put(res+0x11C,gat)
    vm.put(flag+12,ground);vm.put(flag+16,0x11110000)
    for i,(x,z) in enumerate([(-10.,0.),(0.,0.),(-10.,10.),(0.,10.)]):
        vm.u.mem_write(quad+i*32,struct.pack('<fff',x,0.,z))
    vectors=0
    for mask in range(16):
        for bit in range(4):
            index=(4+(bit//2))*8+2+(bit%2)
            vm.put(gat+index*20+16,5 if mask&(1<<bit) else 0)
        for grid in (0,1):
            vm.put(flag+4,grid)
            poly=vm.polygon();vertices=vm.get(poly)
            for i in range(4):
                vm.put(vertices+i*32+16,0x80112233)
            assert vm.run(m['material']['vir'],[poly,quad])==0x800
            assert vm.get(poly+8)==0x11110000
            expected=struct.unpack('<4f',vm.u.mem_read(m['style']['uvVir']+(mask+grid*16)*16,16))
            for i in range(4):
                assert vm.get(vertices+i*32+16)==0x80FFFFFF,'atlas lost vertex alpha'
                uv=struct.unpack('<2f',vm.u.mem_read(vertices+i*32+24,8))
                assert uv==(expected[2 if i&1 else 0],expected[3 if i&2 else 1]),(mask,grid,i,uv,expected)
            vectors+=1
    # Native GAT 1 and 5 block; 0/2/3/4/6 walk. High water flag is masked.
    for cell_type in [0,1,2,3,4,5,6,0x80000003,7]:
        vm.put(gat+(4*8+2)*20+16,cell_type)
        for bit in (1,2,3):vm.put(gat+((4+bit//2)*8+2+bit%2)*20+16,0)
        poly=vm.polygon();vm.put(flag+4,0)
        vm.run(m['material']['vir'],[poly,quad])
        expected_mask=1 if cell_type in [1,5,7] else 0
        expected=struct.unpack('<f',vm.u.mem_read(m['style']['uvVir']+expected_mask*16,4))[0]
        assert struct.unpack('<f',vm.u.mem_read(vm.get(poly)+24,4))[0]==expected
        vectors+=1
    # Execute real native control flow, including the culled-object branch
    # into 0xA7B2FC which the original eight-byte CALL replacement destroyed.
    seen=[];table=vm.alloc(64);native=vm.alloc(16);obj=vm.alloc(0x180)
    vm.put(table+0x1C,native);vm.put(obj,table)
    def draw(args):
        seen.append((tuple(args),vm.u.reg_read(UC_X86_REG_ESP)))
        assert vm.u.reg_read(UC_X86_REG_ECX)==obj
        return 0
    vm.stub(native,8,draw)
    if m.get('sceneryBridges'):
        for enabled,hide in [(0,0),(0,1),(1,0),(1,1),(0,1)]:
            for mode in (0,1,2):
                vm.put(flag,enabled);vm.put(flag+8,hide);seen.clear()
                sp,bp=vm.sp,vm.sp+0x400
                vm.put(bp-20,mode);vm.put(bp-8,0x1234)
                for reg,value in [(UC_X86_REG_ESP,sp),(UC_X86_REG_EBP,bp),(UC_X86_REG_EDX,obj)]:vm.u.reg_write(reg,value)
                vm.u.emu_start(0xA7B2D6,0xA7B301,count=1000)
                expected_draw=mode!=0 and not(enabled and hide)
                assert vm.u.reg_read(UC_X86_REG_EIP)==0xA7B301
                assert vm.u.reg_read(UC_X86_REG_ESP)==sp
                assert vm.u.reg_read(UC_X86_REG_EAX)==vm.renderer
                assert seen==([((0x1234,mode-1),sp-12)] if expected_draw else [])
                vectors+=1
            vm.put(flag,enabled);vm.put(flag+8,hide);seen.clear()
            sp=vm.sp
            for reg,value in [(UC_X86_REG_ESP,sp),(UC_X86_REG_EDX,obj),(UC_X86_REG_EAX,table),(UC_X86_REG_EDI,0x1234)]:vm.u.reg_write(reg,value)
            vm.u.emu_start(0xA7B408,0xA7B417,count=1000)
            assert vm.u.reg_read(UC_X86_REG_ESP)==sp
            assert vm.u.reg_read(UC_X86_REG_EAX)==vm.renderer
            assert seen==([] if enabled and hide else [((0x1234,0),sp-12)])
            vectors+=1
    else:
        for enabled,hide in [(0,0),(0,1),(1,0),(1,1),(0,1)]:
            vm.put(flag,enabled);vm.put(flag+8,hide);seen.clear()
            result=vm.run(m['scenery']['vir'],[0x1234,0],eax=table,ecx=obj)
            assert result==vm.renderer
            assert [x[0] for x in seen]==([] if enabled and hide else [(0x1234,0)])
            vectors+=1
    # Ground scope captures a fresh receiver and rechecks the cached texture
    # per pass, allowing the native texture manager to own map/device lifetime.
    loaded=[]
    vm.stub(0x568760,20,lambda args:loaded.append(args) or 0x11110000)
    vm.stub(m['colors']['exports']['_GrayPrepare@0'],0,lambda args:0)
    vm.stub(0xA63680,12,lambda args:0x55)
    for enabled in (0,1,0):
        vm.put(flag,enabled);loaded.clear()
        vm.run(m['ground']['vir'],[11,22,33],ecx=ground)
        assert len(loaded)==enabled
        if enabled:assert vm.get(flag+12)==ground and vm.get(flag+16)==0x11110000
        vectors+=1
    # Actual renderer-consumer branches, not just the producer's option reads.
    # Gray queues 32-byte vertices, so combined/lightmap consumers must also
    # choose their single-texture paths while leaving the saved option intact.
    for enabled in (0,1,0):
        for lightmap in (0,1):
            vm.put(flag,enabled);vm.options[0x77]=lightmap
            for start,single,combined in [(0x55D8DD,0x55DB39,0x55D8EF),(0x5530AC,0x553340,0x5530BE)]:
                found=[]
                def branch(u,address,size,user):
                    if address in (single,combined):found.append(address);u.emu_stop()
                hook=vm.u.hook_add(UC_HOOK_CODE,branch)
                vm.u.reg_write(UC_X86_REG_ESP,vm.sp)
                try:vm.u.emu_start(start,vm.stop,count=1000)
                finally:vm.u.hook_del(hook)
                assert found==[single if enabled or not lightmap else combined], 'renderer/producer queue mismatch'
                assert vm.u.reg_read(UC_X86_REG_ESP)==vm.sp and vm.options[0x77]==lightmap
                vectors+=1
    # Root constructor remains a chained thiscall(width,height), RET8; the
    # detailed child/scroll/capture lifecycle runs in verify_graymap_colors.py.
    ui=m['ui'];settings,page=vm.alloc(512),vm.alloc(512)
    vm.put(settings+0xE0,page);attached=[]
    vm.stub(ui['previousCreate'],8,lambda args:0x55)
    vm.stub(m['colors']['exports']['_GrayAttach@4'],4,lambda args:attached.append(args))
    assert vm.run(ui['create']['vir'],[400,288],ecx=settings)==0x55
    assert attached==[[page]]
    return vectors+2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('builds', type=Path, nargs='+')
    args = ap.parse_args()
    print(json.dumps([verify(p.resolve()) for p in args.builds], indent=2))


if __name__ == '__main__':
    main()
