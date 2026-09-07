"""Package a verified target HUD executable, its six BMPs and the single guide."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

import pefile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--verification', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--profile', default='profiles/2025-07-16 PROFILE MAIN.yml', help='Build profile or supplied-client provenance')
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/TargetMonsterHUD.zip')
    args = parser.parse_args()
    asset_manifest = json.loads((ROOT / 'Assets/TargetMonsterHUD/assets.json').read_text(encoding='utf8'))
    verification = json.loads(args.verification.read_text(encoding='utf8'))
    digest = sha256(args.exe)
    if verification['exe_sha256'] != digest:
        raise ValueError('Verification receipt does not match this executable')
    files = [ROOT / asset_manifest['resource_root'] / tier[kind]
             for tier in asset_manifest['tiers'] for kind in ('empty', 'full')]
    source = pefile.PE(str(args.source))
    final = pefile.PE(str(args.exe))
    if final.FILE_HEADER.Machine != 0x14c or final.OPTIONAL_HEADER.Magic != 0x10b:
        raise ValueError('The HUD profile requires a 32-bit PE executable')
    anchors = {'CFile_Open': (0x573750, 0x230), 'CFile_Read': (0x573980, 0x70),
               'CFile_Destructor': (0x519200, 0x70), 'CFileMgr_Resolve': (0xa88ab0, 0x2e5)}
    for name, (va, size) in anchors.items():
        if source.get_data(va - 0x400000, size) != final.get_data(va - 0x400000, size):
            raise ValueError(f'Native resource function changed: {name}')
    def branch_target(va):
        return va + 5 + struct.unpack('<i', final.get_data(va - 0x400000 + 1, 4))[0]
    base = branch_target(branch_target(0xc76591))
    for index, path in enumerate(files):
        raw = final.get_data(base + 0xe200 + index * 256 - 0x400000, 256).split(b'\0')[0]
        key = 'data/' + raw.decode('latin1').replace('\\', '/')
        if key != path.relative_to(ROOT).as_posix():
            raise ValueError(f'Packaged asset does not match the executable key: {key}')
        deployed = args.exe.parent / path.relative_to(ROOT)
        if path.read_bytes() != deployed.read_bytes():
            raise ValueError(f'Asset copy beside the executable is stale: {path.name}')
    report = {'patch': 'TargetMonsterHealthBar', 'client_build': 20250716,
              'profile': args.profile, 'exe': args.exe.name,
              'sha256': digest, 'canvas': asset_manifest['canvas'],
              'resource_root': asset_manifest['resource_root'],
              'native_resource_functions_unchanged': list(anchors),
              'assets': {path.name: sha256(path) for path in files},
              'verification': verification}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(args.exe, args.exe.name)
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(ROOT / 'docs/target-monster-health-bar.md', 'target-monster-health-bar.md')
        server_patch = ROOT / 'Assets/TargetMonsterHUD/server-native-hp.patch'
        if server_patch.exists():
            archive.write(server_patch, 'server-native-hp.patch')
        archive.writestr('manifest.json', json.dumps(report, ensure_ascii=False, indent=2).encode('utf8'))
    args.output.with_suffix('.manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f'Packaged {args.output.name}: executable, six BMPs, guide and manifest')


if __name__ == '__main__':
    main()
