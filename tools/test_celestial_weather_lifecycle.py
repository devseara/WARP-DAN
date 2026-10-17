"""Stress emitted rain ownership and bounded primitives; engine allocation/free remain explicit boundaries."""
import argparse
import json
from pathlib import Path
import struct

from test_celestial_dial import Machine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    m = Machine(args.client)
    state = m.c['state']
    parents, disposed, children, free_children = [], [], {}, []
    render = {'enabled': True, 'quads': 0, 'lookups': 0}

    def append(owner, offset, value):
        head = m.r(owner + offset)
        if not head:
            head = m.alloc(16)
            m.w(head, head)
            m.w(head + 4, head)
            m.w(owner + offset, head)
        tail = m.r(head + 4)
        node = m.alloc(16)
        for address, value_ in [(node, head), (node + 4, tail), (node + 8, value), (tail, node), (head + 4, node)]:
            m.w(address, value_)
        m.w(owner + offset + 4, m.r(owner + offset + 4) + 1)

    def unlink(owner, offset, value):
        head = m.r(owner + offset)
        node = m.r(head)
        for _ in range(m.r(owner + offset + 4)):
            if m.r(node + 8) == value:
                m.w(m.r(node + 4), m.r(node))
                m.w(m.r(node) + 4, m.r(node + 4))
                m.w(owner + offset + 4, m.r(owner + offset + 4) - 1)
                return
            node = m.r(node)
        raise AssertionError('Attempted to retire unrelated native weather')

    def factory():
        assert m.ecx() == m.player and m.args(5) == [857, 0, 0, 0, 0]
        parent = m.alloc(0x12000)
        m.w(parent, 0x1088DE8)
        m.w(parent + 0x168, 857)
        m.w(parent + 0x138, m.player)
        append(m.player, 0x144, parent)
        append(m.world, 8, parent)
        parents.append(parent)
        m.ret(20, parent)

    def emit():
        parent = m.ecx()
        child = free_children.pop() if free_children else m.alloc(0x900)
        m.u.mem_write(child, bytes(0x900))
        for address, value in [(child, 0x1088C48), (child + 0x140, parent), (child + 0x1d0, 157),
                               (child + 0x204, 1), (parent + 0x11c84, child)]:
            m.w(address, value)
        m.u.mem_write(child + 0x10, struct.pack('<3f', 0., -20., 0.))
        texture = m.alloc(4)
        m.w(texture, 0x1111)
        m.w(child + 0x144, texture)
        for i in range(4):
            m.w(child + 0x3e8 + i * 0xb4, 1)
        children[child] = parent
        m.ret(8)

    def destructor():
        parent = m.ecx()
        assert m.args(1) == [1] and parent not in disposed
        disposed.append(parent)
        unlink(m.player, 0x144, parent)
        m.ret(4, parent)

    def texture():
        render['lookups'] += 1
        m.ret(20, 0x2222)

    def queue():
        count = m.args(1)[0]
        render['quads'] += 1
        m.w(count, m.r(count) + 1)
        m.ret(104)

    def packet(on=True, **extra):
        values = dict(weather=133 if on else 5, rain_remaining=180000 if on else 0,
                      map_name=b'prt_fild08\0', push=bool(m.r(state + 44)))
        values.update(extra)
        return m.snapshot(**values)

    def retire(parent):
        head = m.r(m.world + 8)
        node = m.r(head)
        while node != head and m.r(node + 8) != parent:
            node = m.r(node)
        assert node != head
        from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESP
        for register, value in [(UC_X86_REG_EBX, m.world), (UC_X86_REG_EDI, node),
                                (UC_X86_REG_EBP, 0x4000e000), (UC_X86_REG_ESP, 0x4000d000)]:
            m.u.reg_write(register, value)
        m.u.emu_start(0xa6bae0, 0xa6bb7e, count=100000)
        assert m.u.reg_read(UC_X86_REG_EIP) == 0xa6bb7e

    m.stub(0xc44540, factory)
    m.stub(0xc0d5b0, emit)
    m.stub(0xba2d80, destructor)
    m.stub(0xdbbc7f, lambda: m.ret(0))
    m.stub(0xd9d020, lambda: m.ret(0, int(render['enabled'])))
    m.stub(0xb7f8d0, lambda: m.ret(0, 1))
    m.stub(0x568760, texture)
    m.stub(0xb7c4e0, queue)
    ground, resource, cells = m.alloc(32), m.alloc(0x200), m.alloc(160 * 160 * 20)
    terrain = struct.pack('<4fI', -7., -7., -7., -7., 0) * (160 * 160)
    m.u.mem_write(cells, terrain)
    for address, value in [(m.world + 0x28, ground), (ground + 4, resource), (ground + 8, 80),
                           (ground + 12, 80), (resource + 0x110, 160), (resource + 0x114, 160),
                           (resource + 0x11c, cells)]:
        m.w(address, value)
    m.u.mem_write(ground + 16, struct.pack('<f', 10.))
    ambient = m.alloc(0x200)
    m.w(ambient + 0x168, 162)
    append(m.player, 0x144, ambient)
    m.w(0x15c57d8 + 0x44, ambient)
    m.w(0x15c57d8 + 0x10, m.player)
    head = m.alloc(16)
    m.w(head, head)
    m.w(head + 4, head)
    m.w(m.world + 0x10, head)
    m.w(0x1602aa4, 1)
    m.frame()
    m.receive(packet())
    m.frame()
    parent = parents[-1]
    particle_step = m.r(m.r(parent) + 0x3c)
    peak_children = peak_quads = peak_lookups = 0
    # Ten simulated seconds exceed the 72-tick lifetime many times without changing server timing.
    for age in range(600):
        m.now += 16
        if age and age % 100 == 0:
            m.receive(packet())
            m.frame()
        m.w(parent + 0x178, age)
        assert m.invoke(particle_step, ecx=parent) & 255 == 1
        peak_children = max(peak_children, len(children))
        assert len(children) <= 96, 'Unbounded native primitive creation'
        for child in list(children):
            if not m.invoke(m.r(m.r(child) + 4), ecx=child):
                del children[child]
                free_children.append(child)
        if age % 30 == 0:
            render.update(enabled=(age // 60) % 2 == 0, quads=0, lookups=0)
            for child in children:
                m.invoke(m.r(m.r(child) + 12), (m.renderer,), ecx=child)
            assert render['enabled'] or render['quads'] == render['lookups'] == 0
            peak_quads = max(peak_quads, render['quads'])
            peak_lookups = max(peak_lookups, render['lookups'])
            assert render['quads'] <= 96 * 8 + 24
        assert len(parents) == 1, '/effect or repeated snapshots duplicated the emitter'
    # Repeated stop, map packet reset, and UIWindow destruction use the real CWorld retirement branch.
    for cycle in range(36):
        parent = parents[-1]
        old_cookie = m.r(state + 12)
        stale = packet()
        if cycle % 3 == 0:
            m.receive(packet(False))
            m.frame()
        elif cycle % 3 == 1:
            m.invoke(m.r(0xcaa2e0 + (0x91 - 0x73) * 4))
        else:
            m.invoke(m.c['destroy'], (1,), ecx=m.r(state))
        for child in list(children):
            assert m.invoke(m.r(m.r(child) + 4), ecx=child) == 0
            del children[child]
            free_children.append(child)
        assert m.invoke(m.r(m.r(parent) + 4), ecx=parent) == 0
        retire(parent)
        assert m.r(m.world + 12) == 0 and m.r(m.player + 0x148) == 1
        assert m.r(0x15c57d8 + 0x44) == ambient and m.r(ambient + 0x168) == 162
        m.frame()
        m.receive(stale)
        if cycle % 3:
            assert m.r(state + 12) != old_cookie and not m.r(state + 44), 'Old-session weather survived reset'
        if cycle < 35:
            m.now += 1000
            m.receive(packet())
            m.frame()
            assert m.r(m.player + 0x148) == 2
    assert len(disposed) == 36 and not children
    assert bytes(m.u.mem_read(cells, len(terrain))) == terrain
    report = {'passed': True, 'simulated_ticks': 600, 'lifecycle_cycles': 36, 'peak_owned_children': peak_children,
              'peak_submitted_quads': peak_quads, 'peak_texture_lookups_per_sampled_frame': peak_lookups,
              'engine_allocation_and_destructors_are_test_boundaries': True, 'not_a_gpu_or_heap_leak_benchmark': True}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
