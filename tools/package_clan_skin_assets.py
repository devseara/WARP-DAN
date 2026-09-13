"""Pack supplied complete SPR/ACT pairs without generating or changing artwork."""
from pathlib import Path
import argparse,hashlib,json,struct,sys,zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/dual_weapon_formats'))
from grf_reader import GrfFile

def pack(data_dir,output):
    skin_root=data_dir/'sprite/clan_skins';files={};records=[]
    for spr in sorted(skin_root.rglob('*.spr')):
        rel=spr.relative_to(skin_root);sid=int(rel.parts[0]);assert 1<=sid<=255
        act=spr.with_suffix('.act');assert act.is_file(),f'Missing ACT: {spr}'
        for path in [spr,act]:
            raw=path.read_bytes();assert raw[:2]==(b'SP' if path.suffix=='.spr' else b'AC')
            key='data/'+path.relative_to(data_dir).as_posix();key.encode('cp949')
            files[key]=raw;records.append({'entry':key,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    for act in skin_root.rglob('*.act'):assert act.with_suffix('.spr').is_file(),f'Missing SPR: {act}'
    assert files,'No complete sprite pairs found'
    return pack_payloads(files,output)


def pack_payloads(files,output):
    """Pack verified resource bytes directly, avoiding duplicate staging files."""
    assert files
    payload=bytearray();table=bytearray()
    for name,raw in sorted(files.items()):
        blob=zlib.compress(raw,9);offset=len(payload);payload+=blob
        table+=name.replace('/','\\').encode('cp949')+b'\0'+struct.pack('<IIIBI',len(blob),len(blob),len(raw),1,offset)
    compressed=zlib.compress(table,9);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(b'Master of Magic\0'+bytes(14)+struct.pack('<IIII',len(payload),0,len(files)+7,0x200)+payload+struct.pack('<II',len(compressed),len(table))+compressed)
    check=GrfFile(output);assert set(check.entries)==set(files)
    for name,raw in files.items():assert check.read(name)==raw
    check.close()
    records=[{'entry':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(files.items())]
    report={'grf_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'entries':records,'gameplay_jobs_added':0,'job_lua_files_added':0}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({'grf':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':report['grf_sha256']}))
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,default=ROOT/'Outputs/clan-body-skins/client/data')
    ap.add_argument('--out',type=Path,default=ROOT/'Outputs/clan-body-skins/clan_skins.grf')
    args=ap.parse_args()
    pack(args.data,args.out)
