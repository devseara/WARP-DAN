import struct
import zlib

GRF_HEADER_SIZE = 0x2E
SIGNATURE = b'Master of Magic\x00'


class GrfFile:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        header = self.f.read(GRF_HEADER_SIZE)
        if header[:16] != SIGNATURE:
            raise ValueError('not a GRF file (bad signature): %r' % header[:16])
        file_table_offset, seed, files_count_a, files_count_b = struct.unpack_from('<IIII', header, 0x1E)
        self.version = None
        file_count = files_count_a - files_count_b - 7
        self.file_count = file_count
        self.f.seek(GRF_HEADER_SIZE + file_table_offset)
        table_compressed_size, table_real_size = struct.unpack('<II', self.f.read(8))
        table_compressed = self.f.read(table_compressed_size)
        table = zlib.decompress(table_compressed, bufsize=table_real_size)
        assert len(table) == table_real_size, (len(table), table_real_size)
        self.entries = {}
        pos = 0
        for _ in range(file_count):
            end = table.index(b'\x00', pos)
            name = table[pos:end].decode('cp949', errors='replace')
            pos = end + 1
            compressed_size, compressed_size_aligned, uncompressed_size, flags, offset = struct.unpack_from('<IIIBI', table, pos)
            pos += 17
            self.entries[name.replace('\\', '/').lower()] = {
                'name': name,
                'compressed_size': compressed_size,
                'uncompressed_size': uncompressed_size,
                'flags': flags,
                'offset': offset,
            }

    def list_matching(self, substring):
        substring = substring.lower()
        return [e['name'] for k, e in self.entries.items() if substring in k]

    def read(self, name_lower_key):
        entry = self.entries.get(name_lower_key)
        if entry is None:
            return None
        if not (entry['flags'] & 1):
            return None  # directory entry, not a file
        self.f.seek(GRF_HEADER_SIZE + entry['offset'])
        raw = self.f.read(entry['compressed_size'])
        data = zlib.decompress(raw)
        if len(data) != entry['uncompressed_size']:
            raise ValueError('size mismatch for %s: got %d expected %d' % (name_lower_key, len(data), entry['uncompressed_size']))
        return data

    def close(self):
        self.f.close()
