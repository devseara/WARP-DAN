"""Execute the emitted WENV v6 map-eligibility gate and legacy precipitation compatibility."""
import argparse
from pathlib import Path
import struct

from test_celestial_dial import Machine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', type=Path)
    args = parser.parse_args()
    m = Machine(args.client)
    state = m.c['state']
    created = []
    def factory():
        effect = m.alloc(0x12000)
        m.w(effect, 0x1088de8)
        head = m.r(m.player + 0x144)
        if not head:
            head = m.alloc(16)
            m.w(head, head)
            m.w(m.player + 0x144, head)
        node = m.alloc(16)
        m.w(node, m.r(head))
        m.w(node + 8, effect)
        m.w(head, node)
        m.w(m.player + 0x148, m.r(m.player + 0x148) + 1)
        created.append(effect)
        m.ret(20, effect)
    m.stub(0xc44540, factory)
    m.frame()
    assert struct.unpack_from('<H', m.sent[-1], 8)[0] == 6
    m.receive(m.snapshot(protocol=6))
    m.frame()
    sequence = m.r(state + 20)
    for values in [dict(protocol=6, flags=2, map_name=b'prt_fild01\0'),
                   dict(protocol=6, flags=2, map_name=b'prt_fild08\0'),
                   dict(protocol=5, flags=6, map_name=b'prt_fild08\0'),
                   dict(protocol=5, flags=2, map_name=b'prt_fild01\0'),
                   dict(protocol=6, flags=2, map_name=b'prt_in\0')]:
        m.receive(m.snapshot(weather=128, rain_remaining=180000, push=True, **values))
        assert m.r(state + 20) == sequence and not created
    m.receive(m.snapshot(protocol=6, flags=6, weather=128, rain_remaining=180000,
                         map_name=b'prt_fild01\0', push=True))
    m.frame()
    assert m.r(state + 132) == 128 and len(created) == 1 and 'Rain' in m.draw()
    effect = m.r(state + 144)
    process = m.r(m.r(effect) + 4)
    m.receive(m.snapshot(protocol=6, flags=2, weather=0, rain_remaining=0,
                         map_name=b'prt_fild01\0', generation=2, push=True))
    m.frame()
    assert m.r(state + 144) == 0 and m.invoke(process, ecx=effect) == 0
    # Legacy v5 storm/flash remains valid on its original prototype map.
    m.now += 1000  # Keep the existing emitter recreation throttle authoritative.
    m.receive(m.snapshot(protocol=5, flags=2, weather=128 | 256 | 512, rain_remaining=120000,
                         map_name=b'prt_fild08\0', generation=3, push=True))
    m.frame()
    labels = m.draw()
    assert 'Storm' in labels and len(created) == 2, (labels, created)
    m.invoke(m.c['reset'])
    assert not m.r(state + 144) and not m.r(state + 44)
    print('PASS: v6 server-authorized map eligibility, indoor/unlisted rejection, profile disable cleanup, v5 storm/flash compatibility and reset')


if __name__ == '__main__':
    main()
