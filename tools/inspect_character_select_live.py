"""Read only the profiled login owner's character records; never writes memory."""
import argparse
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--sha256', required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--map', action='store_true', help='Read selected/session identity after entering a map')
    ap.add_argument('--actor', type=lambda value: int(value, 0))
    args = ap.parse_args()
    k = C.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [C.c_uint32, C.c_int, C.c_uint32]
    k.OpenProcess.restype = C.c_void_p
    k.CloseHandle.argtypes = [C.c_void_p]
    k.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    k.QueryFullProcessImageNameW.argtypes = [C.c_void_p, C.c_uint32, C.c_wchar_p, C.POINTER(C.c_uint32)]
    report = {'schema': 'character_select_read_only/v1', 'pid': args.pid}
    h = k.OpenProcess(0x1010, 0, args.pid)
    try:
        if not h:
            raise C.WinError(C.get_last_error())
        name = C.create_unicode_buffer(32768)
        count = C.c_uint32(len(name))
        if not k.QueryFullProcessImageNameW(h, 0, name, C.byref(count)):
            raise C.WinError(C.get_last_error())
        report['exe'] = name.value
        report['sha256'] = hashlib.sha256(Path(name.value).read_bytes()).hexdigest()
        assert report['sha256'] == args.sha256

        def read(address, size):
            assert 0x10000 <= address < 0x80000000 and 0 < size <= 68 * 279
            buf = C.create_string_buffer(size)
            done = C.c_size_t()
            if not k.ReadProcessMemory(h, address, buf, size, C.byref(done)):
                raise C.WinError(C.get_last_error())
            assert done.value == size
            return buf.raw

        def words(address, n=1):
            return list(struct.unpack('<' + 'I' * n, read(address, n * 4)))

        assert read(0xd2060d, 5) == bytes.fromhex('be 17 01 00 00')
        selected = words(0xd202a3)[0]
        raw = read(selected, 279)
        report['selected_record'] = {'address': selected, 'gid': struct.unpack_from('<I', raw)[0],
                                     'name': raw[108:236].split(b'\0')[0].decode('cp949', errors='replace'),
                                     'slot': raw[242], 'gender': raw[278]}
        report['session'] = {'character_id': words(0x15fb9a8)[0], 'slot': words(0x15fb240)[0],
                             'account_gender': words(0x15fb23c)[0],
                             'character_gender': words(0x15fb238)[0],
                             'character_gender_copy': words(0x15ff8f8)[0]}
        if args.map:
            mode = words(0x121333c)[0]
            report['mode'] = {'address': mode, 'vtable': words(mode)[0]}
            candidates = {args.actor} if args.actor else set()
            report['player_fields_in_mode'] = []
            for offset, pointer in enumerate(words(mode, 1024)):
                if not 0x10000000 <= pointer < 0x80000000 or pointer % 4:
                    continue
                try:
                    if words(pointer)[0] == 0x1094810:
                        report['player_fields_in_mode'].append({'offset': offset * 4, 'actor': pointer})
                        candidates.add(pointer)
                except OSError:
                    pass
            report['actors'] = []
            for actor in candidates:
                raw = read(actor, 0x600)
                report['actors'].append({'address': actor, 'gender': words(actor + 0x260)[0],
                                         'small_id_fields': {hex(i * 4): v for i, v in enumerate(struct.unpack('<384I', raw)) if v in (5, 6, 2000000, 2000001)},
                                         'louis_name_offset': raw.lower().find(b'louis'),
                                         'items': words(actor + 0x440, 2)})
            report['consumer_bytes'] = {hex(a): read(a, n).hex(' ') for a, n in
                                        [(0x79c646, 6), (0x79c761, 7), (0x79c88e, 7), (0x79f1c9, 7)]}
            return
        owner = words(0x121333c)[0]
        report['owner'] = owner
        report['vtable'] = words(owner)[0]
        report['counts'] = words(owner + 0x1cc, 4)
        n = max(report['counts'][0], report['counts'][3])
        assert 0 <= n <= 68
        report['records'] = []
        for i in range(n):
            raw = read(owner + 0x4068 + i * 279, 279)
            report['records'].append({
                'index': i, 'address': owner + 0x4068 + i * 279,
                'gid': struct.unpack_from('<I', raw)[0],
                'job': struct.unpack_from('<H', raw, 84)[0],
                'name': raw[108:236].split(b'\0')[0].decode('cp949', errors='replace'),
                'canonical': {'slot': raw[242], 'gender': raw[278], 'stats': list(raw[236:242]),
                              'map': raw[246:262].split(b'\0')[0].decode('ascii', errors='replace')},
                'stale': {'slot': raw[138], 'gender': raw[174], 'stats': list(raw[132:138])},
            })
        report['consumer_bytes'] = {hex(a): read(a, n).hex(' ') for a, n in
                                    [(0x79c646, 6), (0x79c761, 7), (0x79c88e, 7), (0x79f1c9, 7)]}
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if h:
            k.CloseHandle(h)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
