"""Verify the actual WARP-built clan-skin PE and its relocated static payload."""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
import pefile
ROOT=Path(__file__).resolve().parents[1]
HOOKS=[(0xB43AF0,5,'@ClanBodyHook@32'),(0xB42910,5,'@ClanAlternateBodyHook@32'),(0xD99150,7,'@ClanBodyMapHook@20'),(0xD999D0,6,'@ClanPaletteHook@20')]

# UI resource loading belongs to NativeActJobPreviews; these calls stay stock.
PREVIEW_CALLS=[(0x7ACD71,'e87a0c2e00'),(0x7ACDB1,'e83a0c2e00'),
               (0x7AEC6B,'e880ed2d00'),(0x7AED3F,'e8acec2d00'),
               (0x974B20,'e87b891100'),(0x974B56,'e845891100'),
               (0x974B76,'e825891100'),(0x974D35,'e866871100'),
               (0x974E04,'e897861100')]


def verify(path,source=None,verbose=True,payload_path=None,runtime_source=None):
    payload_path=payload_path or ROOT/'Inputs/ClanBodySkins/runtime.cskb'
    raw=payload_path.read_bytes();meta=json.loads(payload_path.with_suffix('.json').read_text(encoding='utf8'))
    assert hashlib.sha256(raw).hexdigest()==meta['payload_sha256']
    assert hashlib.sha256((runtime_source or ROOT/'Scripts/Runtime/ClanBodySkins/runtime.cpp').read_bytes()).hexdigest()==meta['source_sha256']
    magic,version,size,nreloc,api,_,_,crc=struct.unpack_from('<8I',raw)
    assert magic==0x4E4B5343 and version==1 and zlib.crc32(raw[32:])==crc
    qjs=(ROOT/'Scripts/Patches/ClanBodySkins.qjs').read_bytes();assert qjs.startswith(b'/*') and b'\n' not in qjs.replace(b'\r\n',b'')
    pe=pefile.PE(str(path));data=path.read_bytes();base=pe.OPTIONAL_HEADER.ImageBase
    assert pe.FILE_HEADER.Machine==0x14c and base==0x400000 and not pe.OPTIONAL_HEADER.DllCharacteristics&0x40
    def read(va,n):return data[pe.get_offset_from_rva(va-base):pe.get_offset_from_rva(va-base)+n]
    def target(va):
        b=read(va,5);assert b[0]==0xE9;return va+5+struct.unpack_from('<i',b,1)[0]
    payload=target(HOOKS[0][0])-meta['exports'][HOOKS[0][2]]
    section=next(s for s in pe.sections if s.VirtualAddress<=payload-base<s.VirtualAddress+s.Misc_VirtualSize)
    assert section.Characteristics&0x20000000 and section.Characteristics&0x80000000
    expected=bytearray(raw[32+4*nreloc:]);assert len(expected)==size
    for i in range(nreloc):
        offset=struct.unpack_from('<I',raw,32+i*4)[0];value=struct.unpack_from('<I',expected,offset)[0];struct.pack_into('<I',expected,offset,value+payload)
    assert meta['api_version']==2 and meta['api_size']==40
    native_api=list(struct.unpack('<10I',read(payload+api,40)))
    assert native_api[0]==2 and native_api[5:]==[0x4F1940,0x4F08F0,0x573750,0x573060,0xFD3074]
    for i,(va,stolen,entry) in enumerate(HOOKS):
        assert target(va)==payload+meta['exports'][entry]
        assert read(va+5,stolen-5)==b'\x90'*(stolen-5)
        assert target(native_api[i+1]+stolen)==va+stolen
    expected[api:api+40]=struct.pack('<10I',*native_api)
    for va,stock in PREVIEW_CALLS:
        assert read(va,5)==bytes.fromhex(stock),'Clan patch changed a UI resource call'
    assert read(payload,size)==expected,'Relocated payload or native API table differs'
    if source:
        old=pefile.PE(str(source));olddata=source.read_bytes()
        s0=next(s for s in old.sections if s.Name.startswith(b'.text'));s1=next(s for s in pe.sections if s.Name.startswith(b'.text'))
        before=s0.get_data();after=bytearray(s1.get_data());assert len(after)==len(before)
        for i,(va,stolen,_) in enumerate(HOOKS):
            off=old.get_offset_from_rva(va-base);original=olddata[off:off+stolen]
            assert read(native_api[i+1],stolen)==original
            relative=va-base-s0.VirtualAddress;after[relative:relative+stolen]=original
        assert bytes(after)==before,'Unrelated native code changed'
    result={'client':str(path),'sha256':hashlib.sha256(data).hexdigest(),'payload_va':hex(payload),'payload_bytes':size,'hooks':4,'preview_calls':0,'stock_ui_calls_verified':len(PREVIEW_CALLS),'native_api':native_api,'relocated_payload_matches':True,'unrelated_native_code_unchanged':bool(source),'live_game_tested':False}
    if verbose:print(json.dumps(result,indent=2))
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--source',type=Path);ap.add_argument('--report',type=Path);args=ap.parse_args();result=verify(args.exe,args.source)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,indent=2),encoding='utf8')
