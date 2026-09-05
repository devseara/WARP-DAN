"""GRF seeded-count and strict Event Horizon v0x300 format regressions."""
import struct,tempfile,unittest,zlib,sys
from unittest.mock import patch
from pathlib import Path
sys.dont_write_bytecode=True
from dual_weapon_formats.grf_reader import GrfFile,SIGNATURE,EVENT_HORIZON_SIGNATURE
class Counts(unittest.TestCase):
    def test_seeded_and_unseeded(self):
        for seed in [0,0xee6d]:
            with self.subTest(seed=seed),tempfile.TemporaryDirectory() as temp:
                contents=[b"first",b"second",b"last"]
                payload=bytearray(); table=bytearray()
                for i,raw in enumerate(contents):
                    packed=zlib.compress(raw); offset=len(payload);payload.extend(packed)
                    table.extend(("data/%d.bin"%i).encode()+b"\0"+
                                 struct.pack("<IIIBI",len(packed),len(packed),len(raw),1,offset))
                packed_table=zlib.compress(table)
                header=SIGNATURE+b"\0"*14+struct.pack("<IIII",len(payload),seed,seed+len(contents)+7,0x200)
                f=Path(temp)/"seed.grf"
                f.write_bytes(header+payload+struct.pack("<II",len(packed_table),len(table))+packed_table)
                grf=GrfFile(f)
                try:
                    self.assertEqual(grf.version,0x200)
                    self.assertEqual(grf.file_count,3)
                    self.assertEqual(len(grf.entries),3)
                    for i,raw in enumerate(contents):self.assertEqual(grf.read("data/%d.bin"%i),raw)
                finally:grf.close()


def event_fixture(*, version=0x300, reserved=0, count=None, table_delta=0,
                  file_size_delta=0, entry_offset=None, truncate_entry=False):
    contents = [b'first Event Horizon payload', b'middle\0payload', b'last payload']
    payload, table = bytearray(), bytearray()
    for i, raw in enumerate(contents):
        packed = zlib.compress(raw)
        offset = len(payload) if entry_offset is None else entry_offset
        payload.extend(packed)
        table.extend(('data/%d.bin' % i).encode() + b'\0' +
                     struct.pack('<IIIBQ', len(packed), len(packed),
                                 len(raw) + file_size_delta, 1, offset))
    # Real archive has a directory marker among its directly-counted records.
    table.extend(b'data/empty\0' + struct.pack('<IIIBQ', 0, 0, 0, 128, 0))
    if truncate_entry:
        table = table[:-1]
    compressed = zlib.compress(table)
    header = EVENT_HORIZON_SIGNATURE + bytes(14) + struct.pack('<QII', len(payload), 4 if count is None else count, version)
    return header + payload + struct.pack('<III', reserved, len(compressed), len(table) + table_delta) + compressed, contents


class SparseStream:
    """Sparse read-only fixture: exercise >4GiB offsets without a huge file."""
    def __init__(self, segments):
        self.segments, self.position, self.closed = segments, 0, False
        self.size = max(offset + len(data) for offset, data in segments.items())

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def tell(self):
        return self.position

    def read(self, size):
        size = max(0, min(size, self.size - self.position))
        result = bytearray(size)
        for offset, data in self.segments.items():
            begin, end = max(self.position, offset), min(self.position + size, offset + len(data))
            if begin < end:
                result[begin - self.position:end - self.position] = data[begin - offset:end - offset]
        self.position += size
        return bytes(result)

    def close(self):
        self.closed = True


class EventHorizon(unittest.TestCase):
    def test_direct_count_and_payloads(self):
        data, contents = event_fixture()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'event.grf'; path.write_bytes(data)
            grf = GrfFile(path)
            try:
                self.assertEqual(grf.format, 'event_horizon_300')
                self.assertEqual(grf.version, 0x300)
                self.assertEqual(grf.file_count, 4)
                self.assertEqual(len(grf.entries), 4)
                for i, raw in enumerate(contents):
                    self.assertEqual(grf.read('data/%d.bin' % i), raw)
                self.assertIsNone(grf.read('data/empty'))
                self.assertIsNone(grf.read('data/missing.act'))
            finally:
                grf.close()

    def test_both_offsets_are_64_bit(self):
        table_offset, file_offset = 0x200000023, 0x100000019
        raw = b'payload beyond the 32-bit address boundary'
        packed = zlib.compress(raw)
        table = b'data/large.bin\0' + struct.pack('<IIIBQ', len(packed), len(packed), len(raw), 1, file_offset)
        compressed = zlib.compress(table)
        header = EVENT_HORIZON_SIGNATURE + bytes(14) + struct.pack('<QII', table_offset, 1, 0x300)
        stream = SparseStream({0: header, 46 + file_offset: packed,
                               46 + table_offset: struct.pack('<III', 0, len(compressed), len(table)) + compressed})
        with patch('builtins.open', return_value=stream):
            grf = GrfFile('sparse-event.grf')
        try:
            self.assertEqual(grf.entries['data/large.bin']['offset'], file_offset)
            self.assertEqual(grf.read('data/large.bin'), raw)
        finally:
            grf.close()
        self.assertTrue(stream.closed)

    def test_rejects_unprofiled_or_malformed_headers_and_tables(self):
        good, _ = event_fixture()
        cases = [
            ('version', event_fixture(version=0x301)[0], 'version'),
            ('reserved', event_fixture(reserved=1)[0], 'reserved'),
            ('low direct count', event_fixture(count=3)[0], 'consume table exactly'),
            ('high direct count', event_fixture(count=5)[0], 'truncated GRF table entry'),
            ('entry truncated', event_fixture(truncate_entry=True)[0], 'truncated GRF table entry'),
            ('table size', event_fixture(table_delta=1)[0], 'size mismatch'),
            ('header truncated', good[:45], 'truncated GRF header'),
            ('table truncated', good[:-1], 'truncated GRF compressed table'),
            ('signature', b'Event Horizon\0d\0' + good[16:], 'signature'),
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.grf'
            for name, data, error in cases:
                with self.subTest(case=name):
                    path.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, error):
                        GrfFile(path)

    def test_checks_file_size_and_payload_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad-payload.grf'
            for data, message in [(event_fixture(file_size_delta=1)[0], 'size mismatch'),
                                  (event_fixture(entry_offset=0x100000000)[0], 'truncated GRF file')]:
                with self.subTest(message=message):
                    path.write_bytes(data)
                    grf = GrfFile(path)
                    try:
                        with self.assertRaisesRegex(ValueError, message):
                            grf.read('data/0.bin')
                    finally:
                        grf.close()

if __name__=="__main__":unittest.main()
