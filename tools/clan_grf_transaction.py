"""Replace named GRF records atomically while retaining exact rollback bytes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent / 'dual_weapon_formats'))
from grf_reader import GrfFile, GRF_HEADER_SIZE


def digest(path, start=0, length=None):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        stream.seek(start)
        while length is None or length:
            block = stream.read(1024 * 1024 if length is None else min(length, 1024 * 1024))
            if not block:
                assert length is None, 'Truncated digest range'
                break
            result.update(block)
            if length is not None:
                length -= len(block)
    return result.hexdigest()


def table_records(path):
    with Path(path).open('rb') as stream:
        header = stream.read(GRF_HEADER_SIZE)
        offset, seed, count, version = struct.unpack_from('<IIII', header, 30)
        assert header[:16] == b'Master of Magic\0' and version == 0x200
        stream.seek(GRF_HEADER_SIZE + offset)
        packed, unpacked = struct.unpack('<II', stream.read(8))
        table = GrfFile._inflate(stream.read(packed), unpacked, 'table')
    records, position = [], 0
    for _ in range(count - seed - 7):
        end = table.index(b'\0', position)
        name = table[position:end].decode('cp949').replace('\\', '/').lower()
        stop = end + 18
        records.append((name, table[position:stop]))
        position = stop
    assert position == len(table)
    assert len({name for name, _ in records}) == len(records), 'Duplicate GRF paths'
    return header, records


def replace_records(target, desired, receipt, remove=()):
    """Write only specified replacements/removals; retain all other records."""
    target, receipt = Path(target).resolve(), Path(receipt)
    pending = target.with_name(target.name + '.clan-release.pending')
    assert not pending.exists(), f'Inspect existing pending archive: {pending}'
    assert not (set(desired) & set(remove))
    before, length = digest(target), target.stat().st_size
    base = GrfFile(target)
    try:
        assert base.format == 'master_of_magic' and base.version == 0x200
        removed = set(remove) & set(base.entries)
        changes = {name: raw for name, raw in desired.items()
                   if name not in base.entries or base.read(name) != raw}
        if not changes and not removed:
            return dict(status='already_current', target=str(target), sha256=before)
        header, records = table_records(target)
        kept = [raw for name, raw in records if name not in changes and name not in removed]
        added = set(changes) - set(base.entries)
        shutil.copyfile(target, pending)
        with pending.open('r+b') as stream:
            stream.seek(0, 2)
            table = bytearray(b''.join(kept))
            for name, raw in sorted(changes.items()):
                packed = zlib.compress(raw, 9)
                offset = stream.tell() - GRF_HEADER_SIZE
                stream.write(packed)
                table += name.replace('/', '\\').encode('cp949') + b'\0'
                table += struct.pack('<IIIBI', len(packed), len(packed), len(raw), 1, offset)
            offset = stream.tell() - GRF_HEADER_SIZE
            packed = zlib.compress(table, 9)
            stream.write(struct.pack('<II', len(packed), len(table)) + packed)
            updated = bytearray(header)
            _, seed, count, version = struct.unpack_from('<IIII', header, 30)
            struct.pack_into('<IIII', updated, 30, offset, seed, count + len(added) - len(removed), version)
            stream.seek(0)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        check = GrfFile(pending)
        try:
            assert set(check.entries) == (set(base.entries) | set(desired)) - removed
            for name, entry in base.entries.items():
                if name not in changes and name not in removed:
                    assert check.entries[name] == entry, name
            for name, raw in desired.items():
                assert check.read(name) == raw, name
            count = check.file_count
        finally:
            check.close()
        assert digest(target) == before, 'Source archive changed during preparation'
        assert digest(target, GRF_HEADER_SIZE, length - GRF_HEADER_SIZE) == digest(pending, GRF_HEADER_SIZE, length - GRF_HEADER_SIZE)
        after = digest(pending)
        restored = hashlib.sha256(header)
        with pending.open('rb') as stream:
            stream.seek(GRF_HEADER_SIZE)
            remaining = length - GRF_HEADER_SIZE
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                assert block
                restored.update(block)
                remaining -= len(block)
        assert restored.hexdigest() == before
        result = dict(status='prepared', target=str(target), pending=str(pending),
                      before_sha256=before, after_sha256=after,
                      original_length=length, original_header_hex=header.hex(),
                      added=sorted(added), replaced=sorted(set(changes) - added),
                      removed=sorted(removed), entries=count,
                      unrelated_records_preserved=len(kept),
                      original_compressed_bytes_preserved=True,
                      rollback_reconstruction_sha256=restored.hexdigest())
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(result, indent=2), encoding='utf8')
    finally:
        base.close()
    try:
        os.replace(pending, target)
    except PermissionError as error:
        raise RuntimeError(f'Verified archive ready at {pending}; close the application holding {target.name}. Receipt: {receipt}') from error
    assert digest(target) == after
    result['status'] = 'installed'
    receipt.write_text(json.dumps(result, indent=2), encoding='utf8')
    return result


def finish(receipt):
    receipt = Path(receipt)
    row = json.loads(receipt.read_text(encoding='utf8'))
    assert row['status'] == 'prepared'
    assert digest(row['target']) == row['before_sha256']
    assert digest(row['pending']) == row['after_sha256']
    os.replace(row['pending'], row['target'])
    row['status'] = 'installed'
    receipt.write_text(json.dumps(row, indent=2), encoding='utf8')


def rollback(receipt):
    row = json.loads(Path(receipt).read_text(encoding='utf8'))
    target = Path(row['target'])
    assert digest(target) == row['after_sha256'], 'Archive changed after this transaction'
    pending = target.with_name(target.name + '.clan-rollback.pending')
    assert not pending.exists()
    shutil.copyfile(target, pending)
    with pending.open('r+b') as stream:
        stream.write(bytes.fromhex(row['original_header_hex']))
        stream.truncate(row['original_length'])
        stream.flush()
        os.fsync(stream.fileno())
    assert digest(pending) == row['before_sha256']
    os.replace(pending, target)
