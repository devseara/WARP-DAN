"""Portable integrity/ABI check; no game executable or private profile required."""
import hashlib
import json
from pathlib import Path
import struct
import zlib

root=Path(__file__).resolve().parents[1]
payload=(root/'Inputs/VipUI/runtime.bin').read_bytes()
meta=json.loads((root/'Inputs/VipUI/runtime.json').read_text())
source=(root/'Scripts/Runtime/VipUI/runtime.cpp').read_bytes().replace(b'\r\n',b'\n')
assert hashlib.sha256(source).hexdigest()==meta['source_sha256']
assert hashlib.sha256(payload).hexdigest()==meta['payload_sha256']
magic,version,size,count,api,_,_,crc=struct.unpack_from('<8I',payload)
assert magic==0x32504956 and version==meta['version']==2 and meta['client']==20250716
assert 32+count*4+size==len(payload) and size==meta['size'] and meta['api_size']==372
assert zlib.crc32(payload[32:])==crc and api==meta['exports']['VipApi'] and api+372<=size
assert not meta['runtime_imports']
offsets=struct.unpack_from('<'+'I'*count,payload,32)
assert len(set(offsets))==count
for offset in offsets:
    assert offset+4<=size and struct.unpack_from('<I',payload,32+count*4+offset)[0]<size
for name,offset in meta['exports'].items():assert 0<=offset<size,name
qjs=(root/'Scripts/Patches/VipUI.qjs').read_bytes()
assert qjs.startswith(b'/*') and b'\n' not in qjs.replace(b'\r\n',b'')
assert b'VipUI.v4' in qjs and b'a.word(2664)' in qjs
assert b'VipQuestOpen' in source and b'sizeof(Snapshot)==2664' in source
print('PASS: source/payload SHA-256, VIPU v4 ABI, bounded relocations/exports, no imports, QJS CRLF/no BOM.')
