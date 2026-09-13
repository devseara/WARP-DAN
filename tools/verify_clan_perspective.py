"""Verify the clan-only final-quad bridge at its independent native boundary."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=0xc4a63e
ORIGINAL=bytes.fromhex('8B 45 D8 0B 88 24 01 00 00')

def verify(pe,data,required=False):
    path=ROOT/'Inputs/ClanBodySkins/perspective.bin'
    raw=path.read_bytes();meta=json.loads(path.with_suffix('.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==meta['sha256'] and raw[-1]==0xc3
    assert hashlib.sha256((ROOT/meta['source']).read_bytes()).hexdigest()==meta['source_sha256']
    def read(va,size):
        off=pe.get_offset_from_rva(va-0x400000);return data[off:off+size]
    def target(va):
        b=read(va,5);assert b[0]==0xe9
        return va+5+struct.unpack_from('<i',b,1)[0]
    try:
        start=target(SITE);found=read(start,len(raw)-1)==raw[:-1]
    except (AssertionError,ValueError):found=False
    if not found:
        assert not required,'Missing clan-only perspective bridge'
        return None
    stolen=start+len(raw)-1
    assert read(stolen,9)==ORIGINAL
    assert target(stolen+9)==SITE+9
    assert read(SITE+5,4)==bytes([0x90])*4
    return dict(bridge_va=start,bridge_bytes=len(raw)+13,continuation_va=SITE+9,
                continuation='independent_native_boundary',allocation_end=start+len(raw)+13,
                canonical_code_matches=True,original_instructions_replayed=True)
