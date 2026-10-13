"""Verify and install Storage/Inventory/Cart artwork without replacing existing files.

The bundled PNG/BMP files retain the user's original pixels. A target must be supplied
explicitly; this tool never edits a game executable, profile or existing artwork.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'Assets/StorageInventoryUI'
UI_DIRECTORY = 'data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_size(path):
    data = path.read_bytes()
    if data[:2]==b'BM' and len(data)>=54:
        width,height=struct.unpack_from('<ii',data,18)
        planes,bits=struct.unpack_from('<HH',data,26)
        if width>0 and height and planes==1 and bits in (24,32) and struct.unpack_from('<I',data,30)[0]==0:
            return width,abs(height)
        raise ValueError(f'Unsupported BMP: {path}')
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise ValueError(f'Not a PNG: {path}')
    return struct.unpack('>II', data[16:24])


def safe_file(root, relative):
    part = PurePosixPath(relative)
    if '\\' in relative or ':' in relative or part.is_absolute() or '..' in part.parts:
        raise ValueError(f'Unsafe asset path: {relative}')
    path = root.joinpath(*part.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Asset path escapes root: {relative}')
    return path


def verify(bundle=BUNDLE):
    bundle = Path(bundle)
    hashes = json.loads((bundle / 'sha256.json').read_text(encoding='utf-8'))
    if not hashes:
        raise ValueError('Empty asset manifest')
    rows = []
    for relative, expected in hashes.items():
        source = safe_file(bundle, relative)
        if digest(source) != expected:
            raise ValueError(f'Bundled asset hash mismatch: {relative}')
        width, height = image_size(source)
        rows.append(dict(path=relative, sha256=expected, width=width, height=height))
    return rows


def install(target, bundle=BUNDLE, dry_run=False):
    """Preflight the complete bundle, then copy only absent destination paths."""
    bundle, target = Path(bundle), Path(target)
    rows = verify(bundle)
    texture = target / UI_DIRECTORY
    planned = []
    for row in rows:
        destination = safe_file(texture, row['path'])
        if destination.exists():
            if not destination.is_file():
                raise ValueError(f'Existing asset is not a regular file: {destination}')
            state = 'existing-original' if digest(destination) == row['sha256'] else 'preserved-custom'
        else:
            state = 'would-copy' if dry_run else 'copied'
        planned.append(dict(row, status=state))
    copied = []
    try:
        if not dry_run:
            for row in planned:
                if row['status'] != 'copied':
                    continue
                destination = safe_file(texture, row['path'])
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation protects against a concurrent custom-file write.
                with destination.open('xb') as stream:
                    copied.append(destination)
                    stream.write(safe_file(bundle, row['path']).read_bytes())
                if digest(destination) != row['sha256']:
                    raise IOError(f'Copied asset hash mismatch: {row["path"]}')
    except Exception:
        for path in reversed(copied):
            path.unlink(missing_ok=True)
        raise
    return dict(target=str(target.resolve()), dry_run=dry_run, files=planned,
                copied=sum(row['status'] == 'copied' for row in planned),
                preserved_custom=sum(row['status'] == 'preserved-custom' for row in planned))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=BUNDLE)
    parser.add_argument('--target', type=Path, help='Explicit game/staged-client directory')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--output', type=Path, help='Optional verification receipt')
    args = parser.parse_args()
    result = install(args.target, args.bundle, args.dry_run) if args.target else dict(files=verify(args.bundle))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(verified=len(result['files']), copied=result.get('copied', 0),
                         preserved_custom=result.get('preserved_custom', 0), dry_run=args.dry_run)))


if __name__ == '__main__':
    main()
