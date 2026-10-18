"""Read-only live weather/process sampling; does not hook, suspend or write the client."""
import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import struct
import time

import pefile

ROOT = Path(__file__).resolve().parents[1]


class MemoryCounters(c.Structure):
    _fields_ = [('cb', c.c_uint32), ('PageFaultCount', c.c_uint32)] + [
        (name, c.c_size_t) for name in ['PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                      'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                                      'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('--client', type=Path, default=Path(
        r'C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.exe'))
    parser.add_argument('--seconds', type=float, default=8)
    parser.add_argument('--interval', type=float, default=.01)
    parser.add_argument('--census', action='store_true', help='Count private weather vtables in native world lists at sample end')
    parser.add_argument('--runtime-meta', type=Path, default=ROOT / 'Inputs/CelestialDial/runtime.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.seconds <= 45
    assert .01 <= args.interval <= 1
    pe = pefile.PE(str(args.client))
    image = pe.get_memory_mapped_image()
    marker = image.index(b'CelestialDial.v3\0')
    record = image.index(struct.pack('<I', pe.OPTIONAL_HEADER.ImageBase + marker))
    api, state = struct.unpack_from('<2I', image, record + 4)
    meta = json.loads(args.runtime_meta.read_text())
    runtime = api - meta['exports']['CelestialApi']
    for offset, name in [(8, 'CelestialState'), (12, '_CelestialFrame@4'),
                         (16, '_CelestialReset@0'), (20, '_CelestialReceive@4')]:
        assert struct.unpack_from('<I', image, record + offset)[0] == runtime + meta['exports'][name], \
            'Runtime metadata does not match this client; supply its exact --runtime-meta'
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [c.c_uint32, c.c_int, c.c_uint32]
    kernel.OpenProcess.restype = c.c_void_p
    kernel.ReadProcessMemory.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    kernel.GetProcessTimes.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p]
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    kernel.QueryPerformanceCounter.argtypes = [c.POINTER(c.c_int64)]
    kernel.QueryPerformanceFrequency.argtypes = [c.POINTER(c.c_int64)]
    kernel.CloseHandle.argtypes = [c.c_void_p]
    psapi = c.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32]
    handle = kernel.OpenProcess(0x1010, False, args.pid)
    assert handle, c.get_last_error()
    qpc_frequency = c.c_int64()
    assert kernel.QueryPerformanceFrequency(c.byref(qpc_frequency))

    def read(address, size):
        data = c.create_string_buffer(size)
        count = c.c_size_t()
        if not kernel.ReadProcessMemory(handle, address, data, size, c.byref(count)) or count.value != size:
            raise ValueError(hex(address))
        return data.raw

    def u32(address):
        return struct.unpack('<I', read(address, 4))[0]

    # The code/constant region precedes CelestialApi, the first mutable data
    # section. Bind this read-only sample to the actual payload on disk, even
    # if an EXE was renamed/replaced while an older process remained alive.
    immutable_size = meta['exports']['CelestialApi']
    expected_code = image[runtime - pe.OPTIONAL_HEADER.ImageBase:api - pe.OPTIONAL_HEADER.ImageBase]
    try:
        assert len(expected_code) == immutable_size and read(runtime, immutable_size) == expected_code, \
            'Loaded weather payload differs from the selected EXE'
    except BaseException:
        kernel.CloseHandle(handle)
        raise

    def cpu():
        values = [c.c_uint64() for _ in range(4)]
        assert kernel.GetProcessTimes(handle, *(c.byref(value) for value in values))
        return (values[2].value + values[3].value) / 10000000

    def census():
        tables = {runtime + meta['exports']['CelestialRainVtable'] + 4: 'parents',
                  runtime + meta['exports']['CelestialRainPrimVtable'] + 4: 'primitives'}
        world = u32(state + 8)
        if not world:
            return {'stable': True, 'parents': 0, 'primitives': 0, 'world': 0}
        result = {'stable': False, 'parents': 0, 'primitives': 0, 'world': world}
        roots = []
        seen = set()
        for offset in [8, 16]:
            head, count = struct.unpack('<2I', read(world + offset, 8))
            if count > 4096 or not head:
                return result
            roots.append((offset, head, count))
            node = u32(head)
            for _ in range(count):
                if not node or node == head or node in seen:
                    return result
                seen.add(node)
                next_node, _, obj = struct.unpack('<3I', read(node, 12))
                if obj:
                    kind = tables.get(u32(obj))
                    if kind:
                        result[kind] += 1
                node = next_node
            if node != head:
                return result
        result['stable'] = world == u32(state + 8) and all(
            struct.unpack('<2I', read(world + offset, 8)) == (head, count) for offset, head, count in roots)
        return result

    samples = []
    errors = []
    started = time.perf_counter()
    cpu_start = cpu()
    try:
        while time.perf_counter() - started < args.seconds:
            try:
                qpc_before = c.c_int64()
                assert kernel.QueryPerformanceCounter(c.byref(qpc_before))
                data = read(state, 204)
                world, tick, ready = (struct.unpack_from('<I', data, offset)[0] for offset in [8, 32, 44])
                row = {'elapsed': time.perf_counter() - started, 'frame_tick': tick, 'ready': ready,
                       'weather': struct.unpack_from('<I', data, 132)[0],
                       'protocol': struct.unpack_from('<I', data, 136)[0],
                       'snapshot_flags': struct.unpack_from('<H', data, 70)[0],
                       'rain_effect': struct.unpack_from('<I', data, 144)[0],
                       'lease_ms': struct.unpack_from('<I', data, 160)[0],
                       'snapshot_age_ms': (tick - struct.unpack_from('<I', data, 28)[0]) & 0xffffffff}
                qpc_after = c.c_int64()
                assert kernel.QueryPerformanceCounter(c.byref(qpc_after))
                row['qpc_before'], row['qpc_after'] = qpc_before.value, qpc_after.value
                renderer = u32(0x12515F8)
                if renderer:
                    row['viewport'] = list(struct.unpack('<2I', read(renderer + 0x28, 8)))
                flash_tick = struct.unpack_from('<I', data, 200)[0]
                row['flash_active'] = bool(flash_tick and ((tick - flash_tick) & 0xffffffff) < 350 and row['weather'] & 256)
                if world:
                    player = u32(world + 0x2c)
                    row.update(world=world, world_effects=u32(world + 12), world_primitives=u32(world + 20))
                    if player:
                        row.update(player_effects=u32(player + 0x148), position=struct.unpack('<3f', read(player + 0x10, 12)))
                if ready:
                    row['map'] = data[112:128].split(b'\0')[0].decode('ascii', errors='replace')
                    row['phase'] = data[98]
                    row['local_night'] = data[99]
                    row['phase_duration_ms'], row['phase_remaining_ms'] = struct.unpack_from('<2I', data, 100)
                samples.append(row)
            except (ValueError, OSError) as error:
                errors.append(str(error))
            time.sleep(args.interval)
        elapsed = time.perf_counter() - started
        cpu_seconds = cpu() - cpu_start
        counters = MemoryCounters()
        counters.cb = c.sizeof(counters)
        assert psapi.GetProcessMemoryInfo(handle, c.byref(counters), counters.cb)
        handles = c.c_uint32()
        assert kernel.GetProcessHandleCount(handle, c.byref(handles))
        owned = None
        if args.census:
            for _ in range(3):
                try:
                    owned = census()
                    if owned['stable']:
                        break
                except (ValueError, OSError) as error:
                    owned = {'stable': False, 'error': str(error)}
    finally:
        kernel.CloseHandle(handle)
    def bounds(name):
        values = [row[name] for row in samples if name in row]
        return [min(values), max(values)] if values else None
    # Polling at 10 ms can miss frames; this is a sampled update-rate indicator, not GPU FPS.
    ticks = [row['frame_tick'] for row in samples]
    changes = sum(a != b for a, b in zip(ticks, ticks[1:]))
    positions = [row['position'] for row in samples if 'position' in row]
    summary = {'pid': args.pid, 'client_sha256': hashlib.sha256(args.client.read_bytes()).hexdigest(),
               'read_only': True, 'seconds': elapsed, 'cpu_percent_one_core': cpu_seconds / elapsed * 100,
               'weather_payload_matches_disk': True,
               'qpc_frequency': qpc_frequency.value,
               'private_bytes': counters.PrivateUsage, 'working_set_bytes': counters.WorkingSetSize,
               'handles': handles.value, 'world_effects_range': bounds('world_effects'),
               'world_primitives_range': bounds('world_primitives'), 'actor_effects_range': bounds('player_effects'),
               'observed_frame_tick_changes': changes, 'not_a_gpu_fps_measurement': True,
               'maps': sorted({row['map'] for row in samples if 'map' in row}),
               'position_bounds': [[min(point[axis] for point in positions), max(point[axis] for point in positions)]
                                   for axis in range(3)] if positions else None,
               'weather_masks': sorted({row['weather'] for row in samples}),
               'rain_instances_observed': len({row['rain_effect'] for row in samples if row['rain_effect']}),
               'read_errors': errors, 'last': samples[-1] if samples else None, 'owned_census': owned}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'summary': summary, 'samples': samples}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
