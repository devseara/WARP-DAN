"""Read a bounded mounted-Mage state/resource snapshot; never writes the client."""

import argparse
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path

import pefile

EXPECTED = 'c37834047287a8257cf7bb9481ac700923a273871087ffa19912dc8128eb3958'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument(
        '--expected-sha256',
        default=EXPECTED,
        help='Exact inspected client hash; structural/code guards still apply.',
    )
    args = ap.parse_args()
    k = C.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [C.c_uint32, C.c_int, C.c_uint32]
    k.OpenProcess.restype = C.c_void_p
    k.CloseHandle.argtypes = [C.c_void_p]
    k.ReadProcessMemory.argtypes = [
        C.c_void_p,
        C.c_void_p,
        C.c_void_p,
        C.c_size_t,
        C.POINTER(C.c_size_t),
    ]
    k.QueryFullProcessImageNameW.argtypes = [
        C.c_void_p,
        C.c_uint32,
        C.c_wchar_p,
        C.POINTER(C.c_uint32),
    ]
    handle = k.OpenProcess(0x1010, False, args.pid)
    if not handle:
        raise C.WinError(C.get_last_error())
    result = dict(
        schema='mounted_mage_read_only/v1',
        pid=args.pid,
        atomic_snapshot=False,
        game_files_changed=False,
        process_writes=False,
    )
    try:
        name = C.create_unicode_buffer(32768)
        length = C.c_uint32(len(name))
        if not k.QueryFullProcessImageNameW(handle, 0, name, C.byref(length)):
            raise C.WinError(C.get_last_error())
        path = Path(name.value)
        result.update(exe=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        assert (
            result['sha256'] == args.expected_sha256.lower()
        ), 'Different executable: stop before reading profiled structures.'

        def read(address, size):
            # This 32-bit client is large-address-aware on 64-bit Windows.
            assert 0x10000 <= address < 0x100000000 and 0 < size <= 0x10000
            assert address + size <= 0x100000000
            buffer = C.create_string_buffer(size)
            count = C.c_size_t()
            if not k.ReadProcessMemory(handle, address, buffer, size, C.byref(count)):
                raise C.WinError(C.get_last_error())
            assert count.value == size
            return buffer.raw

        def words(address, count=1):
            return list(struct.unpack('<' + 'I' * count, read(address, count * 4)))

        pe = pefile.PE(str(path), fast_load=True)
        sections = [
            s
            for s in pe.sections
            if s.Name.rstrip(b'\0') in [b'.mgfix', b'.mgfix2', b'.mgfix3', b'.mgfix4']
        ]
        assert sections
        for section in sections:
            address = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
            assert (
                read(address, section.Misc_VirtualSize)
                == section.get_data()[: section.Misc_VirtualSize]
            ), 'Loaded payload differs from disk.'
        for va, size in [
            (0xD36676, 5),
            (0xD3EA1B, 8),
            (0xD40465, 13),
            (0x604328, 16),
            (0xD36ED0, 40),
            (0x6043E8, 5),
            (0xD41E90, 5),
            (0xD41EE2, 5),
            (0xC40F9F, 5),
        ]:
            assert read(va, size) == pe.get_data(va - 0x400000, size), hex(va)
        result['loaded_code_matches_disk'] = True
        image = pe.get_memory_mapped_image()
        marker = image.index(b'CelestialDial.v3\0')
        record = image.index(struct.pack('<I', 0x400000 + marker))
        state = struct.unpack_from('<I', image, record + 8)[0]
        world = words(state + 8)[0]
        actor = words(world + 0x2C)[0]
        result.update(state=hex(state), world=hex(world), actor=hex(actor))
        print('Native pointers:', result['state'], result['world'], result['actor'], flush=True)
        assert actor and words(actor)[0] == 0x1094810, 'Not on a map with a profiled CPlayer.'
        fields = {
            'action': 0x38,
            'frame': 0x3C,
            'appearance_job': 0x25C,
            'sex': 0x260,
            'actual_job': 0x2C0,
            'hair': 0x438,
            'weapon_right': 0x440,
            'weapon_left': 0x444,
            'body_job': 0x4C8,
            'body_view': 0x4CC,
        }
        result.update(
            actor=hex(actor),
            fields={name: words(actor + off)[0] for name, off in fields.items()},
            all_riding=read(actor + 0x2CC, 1)[0],
        )
        result['render_state'] = dict(
            vtable=hex(words(actor)[0]),
            reversed_depth_9c=read(actor + 0x9C, 1)[0],
            actor_scale=struct.unpack('<f', read(actor + 0x50, 4))[0],
        )
        resources = []
        sprite_slots = {}
        for kind, offset in [('spr', 0x4AC), ('act', 0x4B8)]:
            begin, end = words(actor + offset, 2)
            assert begin and end >= begin and (end - begin) % 4 == 0 and (end - begin) // 4 <= 32
            for slot, pointer in enumerate(words(begin, (end - begin) // 4)):
                if kind == 'spr':
                    sprite_slots[slot] = pointer
                row = dict(kind=kind, slot=slot, pointer=hex(pointer))
                if pointer:
                    try:
                        row['name'] = (
                            read(pointer + 20, 240)
                            .split(b'\0')[0]
                            .decode('cp949', errors='replace')
                        )
                        if kind == 'act':
                            start, finish = words(pointer + 0x110, 2)
                            row['actions'] = (finish - start) // 12
                            ai = result['fields']['action']
                            if start and 0 <= ai < row['actions'] <= 512:
                                first, last = words(start + 12 * ai, 2)
                                row['current_action_frames'] = (last - first) // 68
                            row['frame_probes'] = []
                            for action, index in [
                                (ai, result['fields']['frame']),
                                (33, 0),
                                (33, 3),
                                (82, 3),
                                (85, 3),
                            ]:
                                if not start or not 0 <= action < row['actions'] <= 512:
                                    continue
                                first, last = words(start + action * 12, 2)
                                if not first or not 0 <= index < (last - first) // 68 <= 256:
                                    continue
                                frame = first + index * 68
                                layer_begin = words(frame + 0x20)[0]
                                layer_count = words(frame + 0x2C)[0]
                                assert layer_count <= 32
                                probe = dict(action=action, frame=index, layers=[])
                                for li in range(layer_count):
                                    layer = list(
                                        struct.unpack('<4iI2f2i', read(layer_begin + li * 36, 36))
                                    )
                                    item = dict(
                                        x=layer[0],
                                        y=layer[1],
                                        image=layer[2],
                                        mirror=layer[3],
                                        scale_x=layer[5],
                                        scale_y=layer[6],
                                        rotation=layer[7],
                                        kind=layer[8],
                                    )
                                    sprite = sprite_slots.get(slot, 0)
                                    if sprite and layer[2] >= 0 and layer[8] in [0, 1]:
                                        images, images_end = words(
                                            sprite + 0x510 + layer[8] * 12, 2
                                        )
                                        if (
                                            images
                                            and 0 <= layer[2] < (images_end - images) // 4 <= 65536
                                        ):
                                            image = words(images + 4 * layer[2])[0]
                                            item['native_image_header'] = list(
                                                struct.unpack('<2H2h', read(image, 8))
                                            )
                                    probe['layers'].append(item)
                                row['frame_probes'].append(probe)
                    except (OSError, AssertionError) as error:
                        row['read_error'] = str(error)
                resources.append(row)
        result['resources'] = resources
        result['actor_still_current'] = words(world + 0x2C)[0] == actor
    finally:
        k.CloseHandle(handle)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
        )
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
