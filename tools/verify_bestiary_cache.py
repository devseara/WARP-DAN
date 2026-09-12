"""Execute the actual emitted Bestiary cache/transport against delayed replies.

Native networking and drawing are mocked; no live latency claim is made.
"""
from pathlib import Path
import argparse
import json
import struct
import pefile
from verify_bestiary_journal import JournalVM, packet


def reply(request, revision=3, result=0):
    data = bytearray(packet(struct.unpack_from('<I', request, 12)[0],struct.unpack_from('<H',request,8)[0]))
    struct.pack_into('<II', data, 16, revision, result)
    for dest, src in [(24, 24), (30, 22), (40, 32), (46, 34)]:
        struct.pack_into('<H', data, dest, struct.unpack_from('<H', request, src)[0])
    for dest in [26, 42, 48]:
        struct.pack_into('<H', data, dest, 8)
    selected = struct.unpack_from('<I', request, 28)[0] or 1002
    struct.pack_into('<I', data, 36, selected)
    struct.pack_into('<II', data, 832, selected, selected)
    if selected == 1004:
        data[896:960] = b'Hornet\0'.ljust(64, b'\0')
    if len(request)>=128:
        for dest,src in [(3392,64),(3394,66),(3396,68),(3398,70),(3400,72),(3402,74),(3404,76),(3410,78),(3416,104)]:
            struct.pack_into('<H',data,dest,struct.unpack_from('<H',request,src)[0])
        for dest in [3406,3412,3418]:struct.pack_into('<H',data,dest,8)
    if result:
        data[24:] = b'\0' * (len(data) - 24)
    return bytes(data)


def verify(directory):
    manifest = json.loads((directory / 'native-manifest.json').read_text(encoding='utf-8'))['bestiary']
    pe = pefile.PE(str(directory / 'bestiary-preview.exe'), fast_load=True)
    checks = []

    def fresh():
        v = JournalVM(pe, manifest)
        v.run('sender', [1, 0, 0, 0])
        v.receive(reply(v.sent[-1]))
        return v

    def payload(v):
        return bytes(v.u.mem_read(manifest['payload']['vir'], manifest['payload']['size']))

    v = fresh()
    v.run('sender', [3, 1, 1002, 0])
    assert len(v.sent) == 1 and v.state32(152) == 0
    first = payload(v)
    v.run('sender', [3, 1, 1004, 0])
    delayed = v.sent[-1]
    assert len(v.sent) == 2 and v.state32(16) == 1 and payload(v) == first
    v.receive(reply(delayed))
    assert v.state32(28) == 1004
    v.run('sender', [3, 1, 1002, 0])
    assert len(v.sent) == 2 and v.state32(28) == 1002 and v.state32(152) == 0
    v.receive(reply(delayed))
    assert v.state32(28) == 1002, 'Delayed previous reply displaced a cache hit'
    checks.append('Cache hits send no packets; misses preserve the last display; stale replies cannot replace cache hits')

    v.state32(4, 2)
    v.run('sender', [3, 1, 1004, 0])
    assert len(v.sent) == 2 and v.state32(28) == 1004
    v.run('sender', [3, 2, 1004, 0])
    assert len(v.sent) == 3 and struct.unpack_from('<H', v.sent[-1], 26)[0] == 2
    v.receive(reply(v.sent[-1]))
    v.run('sender', [3, 3, 1004, 0])
    assert len(v.sent) == 4
    v.receive(reply(v.sent[-1]))
    checks.append('Main tab/action labels do not duplicate catalog keys; both navigation actions always reach the server')

    v = fresh()
    v.run('down', [40, 174]); v.run('up', [40, 174])
    assert v.state32(152) == 1
    v.run('down', [310, 336]); v.run('up', [310, 336])
    v.run('down', [732, 333]); v.run('up', [732, 333])
    assert v.state32(140) == 1 and v.state32(160) == 1 and len(v.sent) == 2
    if manifest.get('layoutVersion',0)>=8:
        v.state32(156,3) # Retry is exposed only after an error.
    v.run('down', [455, 39]); v.run('up', [455, 39])
    assert struct.unpack_from('<H', v.sent[-1], 10)[0] == 6 and len(v.sent) == 3
    checks.append('Info paging stays local during pending fetches; the visible recovery button sends an explicit refresh')

    for offset in [12, 120, 132, 136]:
        v = fresh()
        v.state32(offset, 1)
        v.run('sender', [3, 1, 1002, 0])
        assert len(v.sent) == 2, offset
        v.receive(reply(v.sent[-1]))
        v.state32(offset, 0)
        v.run('sender', [3, 1, 1002, 0])
        assert len(v.sent) == 2 and v.state32(offset) == 0, offset
    v = fresh()
    v.u.mem_write(manifest['query']['vir'], b'Poring\0' + b'x' * 21)
    v.run('sender', [3, 0, 0, 0])
    assert len(v.sent) == 2 and v.sent[-1][36:64] == b'Poring\0'.ljust(28, b'\0')
    v.receive(reply(v.sent[-1]))
    v.u.mem_write(manifest['query']['vir'], b'Poring\0' + b'y' * 21)
    v.run('sender', [3, 0, 0, 0])
    assert len(v.sent) == 2
    checks.append('Search, element, catalog, drop and habitat pages have isolated keys; bytes after query NUL cannot cause misses')

    v = fresh()
    before = payload(v)
    v.run('sender', [3, 1, 1004, 0])
    wire = v.sent[-1]
    for attempt in range(3):
        v.receive(reply(wire, result=2))
        assert payload(v) == before and v.state32(16) == 1
        v.now += 249
        count = len(v.sent)
        v.run('requestTick')
        assert len(v.sent) == count
        v.now += 1
        v.run('requestTick')
        assert len(v.sent) == count + 1 and v.sent[-1] == wire
    v.receive(reply(wire, result=2))
    v.now += 250
    count = len(v.sent)
    v.run('requestTick')
    assert v.state32(156) == 3 and len(v.sent) == count and payload(v) == before
    v.run('sender', [3, 1, 1004, 0])
    assert len(v.sent) == count + 1, 'BUSY response entered the cache'
    checks.append('BUSY retries preserve the exact request, stay visible, stop after three retries, and never populate cache')

    v = fresh()
    v.now += 120000
    v.run('draw')
    assert len(v.sent) == 1, 'Idle draw polled the server'
    v.run('sender', [3, 1, 1004, 0])
    old = payload(v)
    v.now += 5001
    v.run('requestTick')
    assert len(v.sent) == 2 and v.state32(152) == 0 and v.state32(156) == 3 and payload(v) == old
    v.run('sender', [6, 0, 1002, 0])
    assert len(v.sent) == 3 and payload(v) == old
    v.receive(reply(v.sent[-1], revision=4))
    v.run('sender', [3, 1, 1002, 0])
    assert len(v.sent) == 3 and v.state32(20) == 4
    v.run('sender', [1, 0, 1002, 0])
    assert len(v.sent) == (3 if manifest.get('layoutVersion',0)>=8 else 4)
    checks.append('Idle windows send no refreshes; timeout is bounded; explicit retry fetches fresh data; reopen follows the build cache contract')

    v = fresh()
    v.run('sender', [3, 1, 1004, 0])
    v.receive(reply(v.sent[-1], revision=4))
    v.run('sender', [3, 1, 1002, 0])
    assert len(v.sent) == 3, 'Old revision remained cached'
    checks.append('A server catalog revision change invalidates older cached entries')

    v = fresh()
    for i in range(80):
        query = ('q' + str(i)).encode().ljust(28, b'\0')
        v.u.mem_write(manifest['query']['vir'], query)
        v.run('sender', [3, 0, 0, 0])
        v.receive(reply(v.sent[-1]))
    assert v.read32(manifest['cache']['vir']) == 64
    assert v.read32(manifest['cache']['vir'] + 4) < 64
    count = len(v.sent)
    v.u.mem_write(manifest['query']['vir'], b'q79\0'.ljust(28, b'\0'))
    v.run('sender', [3, 0, 0, 0])
    assert len(v.sent) == count
    v.u.mem_write(manifest['query']['vir'], b'q0\0'.ljust(28, b'\0'))
    v.run('sender', [3, 0, 0, 0])
    assert len(v.sent) == count + 1
    checks.append('Fixed 64-entry ring remains bounded and evicts old pages without corrupting new entries')
    pe.close()
    result = {'passed': True, 'checks': checks, 'network_and_rendering_mocked': True, 'live_accepted': False}
    (directory / 'cache-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
