"""Prove emitted VIP references match the complete canonical image inventory."""
import argparse
from pathlib import Path
import re
import struct
import pefile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    args = parser.parse_args()
    pe = pefile.PE(str(args.exe))
    data = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    marker = data.find(b'VipUI.v4\0')
    assert marker >= 0
    needle = struct.pack('<I', base + marker)
    records = [i for i in range(len(data)) if data.startswith(needle, i)]
    assert len(records) == 1
    api = struct.unpack_from('<I', data, records[0] + 4)[0] - base
    # ABI remains 372 bytes. Only the item requirement box uses the old slots.
    for offset in [28 + i * 4 for i in range(12) if i != 2] + [88, 92]:
        assert struct.unpack_from('<I', data, api + offset)[0] == 0, offset
    item = struct.unpack_from('<I', data, api + 36)[0] - base
    assert data[item:data.index(b'\0', item)].endswith(b'vipui\\item_main_bg.png')
    names = {s.decode('ascii') for s in re.findall(rb'vipui\\([^\x00\\]+\.png)\x00', data)}
    expected = {p.name for p in (ROOT / 'Assets/VipUI').iterdir()}
    assert len(expected) == 63 and names == expected, (names - expected, expected - names)
    assert all('readable_' not in name for name in names)
    print('PASS: all 63 emitted resource references exist, no stale names or unused assets, stable API slots.')

if __name__ == '__main__':
    main()
