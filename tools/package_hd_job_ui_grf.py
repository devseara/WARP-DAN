"""Pack HD preview files or exact world test fixtures into an unencrypted GRF v2."""
from pathlib import Path
import argparse,json,struct,zlib
from dual_weapon_formats.grf_reader import GrfFile

def write_grf(files,output):
    body=bytearray();table=bytearray()
    for name,raw in sorted(files.items()):
        encoded=name.replace('/','\\').encode('cp949')
        if b'\0' in encoded:raise ValueError('Invalid GRF entry name')
        compressed=zlib.compress(raw,9)
        table+=encoded+b'\0'+struct.pack('<IIIBI',len(compressed),len(compressed),len(raw),1,len(body))
        body+=compressed
    packed=zlib.compress(table,9)
    header=b'Master of Magic\0'+bytes(range(1,15))+struct.pack('<IIII',len(body),0,len(files)+7,0x200)
    assert len(header)==46
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(header+body+struct.pack('<II',len(packed),len(table))+packed)
    check=GrfFile(output)
    try:
        assert len(check.entries)==len(files)
        for name,raw in files.items():assert check.read(name.replace('\\','/').lower())==raw
    finally:check.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,help='Generated Assets/HDJobUI folder (preview and stock only)')
    parser.add_argument('--world-config',type=Path,help='Optional exact source pairs for a separate world test archive')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();files={}
    if args.assets:
        manifest=json.loads((args.assets/'manifest.json').read_text(encoding='utf-8'))
        for row in manifest['pairs']:
            for name in row['files']:files['data/sprite/hd_job_ui/'+name]=(args.assets/name).read_bytes()
    if args.world_config:
        config=json.loads(args.world_config.read_text(encoding='utf-8'))
        for row in config['pairs']:
            spec=row['source']
            for ext in ('.spr','.act'):
                member=spec.get(ext[1:],spec)
                if 'grf' in member:
                    archive=GrfFile(member['grf'])
                    try:raw=archive.read((member['stem']+ext).lower())
                    finally:archive.close()
                else:raw=Path(member['path']+ext).read_bytes()
                if raw is None:raise ValueError('Missing world source pair')
                files['data/sprite/'+row['resource_stem']+ext]=raw
    if not files:parser.error('Specify --assets and/or --world-config')
    write_grf(files,args.output);print(json.dumps({'archive':str(args.output),'files':len(files),'bytes':args.output.stat().st_size}))
if __name__=='__main__':main()