"""Shared HUD design catalog and executable resource-key identification."""
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Assets/TargetMonsterHUD'


def load_designs():
    catalog = json.loads((ASSETS / 'designs.json').read_text(encoding='utf8'))
    designs = {name: json.loads((ASSETS / filename).read_text(encoding='utf8'))
               for name, filename in catalog.items()}
    for name, manifest in designs.items():
        width, height = manifest['canvas']
        assert [tier['name'] for tier in manifest['tiers']] == ['normal', 'mini', 'mvp'], name
        assert manifest['pixel_offset'] == 122 and manifest['bmp_header'] == 'BITMAPV4HEADER', name
        for tier in manifest['tiers']:
            left, top, right, bottom = tier['fill']
            assert 0 <= left < right <= width and 0 <= top < bottom <= height, (name, tier['name'])
    return designs


def identify_design(pe):
    """Resolve all six embedded keys; reject a partial or mixed design."""
    image_base = pe.OPTIONAL_HEADER.ImageBase
    def target(va):
        return va + 5 + struct.unpack('<i', pe.get_data(va - image_base + 1, 4))[0]
    base = target(target(0xc76591))
    actual = [pe.get_data(base + 0xe200 + index * 256 - image_base, 256).split(b'\0')[0]
              for index in range(6)]
    for name, manifest in load_designs().items():
        prefix = manifest['resource_root'].removeprefix('data/').replace('/', chr(92))
        expected = [(prefix + chr(92) + tier[kind]).encode('latin1')
                    for tier in manifest['tiers'] for kind in ('empty', 'full')]
        if actual == expected:
            return name, manifest
    raise ValueError('Executable resource keys do not match a complete HUD design')
