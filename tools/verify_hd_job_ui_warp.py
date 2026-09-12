"""Verify real WARP exports: pristine, ClanBodySkins v11, and Alt Q/A integration."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess,tempfile
import pefile
ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--warp-root',type=Path,default=ROOT,help='WARP installation to exercise in isolation')
 parser.add_argument('--clan-client',type=Path,required=True,help='Verified ClanBodySkins v11 reference EXE')
 parser.add_argument('--profile-client',type=Path,default=ROOT/'2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe')
 args=parser.parse_args();warp_root=args.warp_root.resolve()
 out=Path(tempfile.mkdtemp(prefix='hd-job-ui-warp-',dir=ROOT/'Outputs'));fixture=out/'fixture';fixture.mkdir()
 for name in ('win32','Scripts','Tables','Patches','Inputs','Languages','Styles','Assets','Images'):
  shutil.copytree(warp_root/name,fixture/name,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copy2(warp_root/'Patches.yml',fixture/'Patches.yml')
 clean=args.profile_client.resolve();clan=args.clan_client.resolve()
 manifest=json.loads((ROOT/'Assets/HDJobUI/manifest.json').read_text());blob=json.loads((ROOT/'Outputs/hd-job-ui/native/blob.json').read_text())
 sites={v:s for s,vs in [(True,[0x7acd71,0x7acdb1,0x7aec6b,0x7aed3f]),(False,[0x974b20,0x974b56,0x974b76,0x974d35,0x974e04])] for v in vs}
 rows=[]
 for label,source,patches in [('clean',clean,['HDJobSpritePreviews']),('clan-v11',clan,['HDJobSpritePreviews']),('altqa',clean,['RedesignedEquipmentWindow','RedesignedStatusWindow','HDJobSpritePreviews'])]:
  folder=out/label;folder.mkdir();target=folder/'client.exe';profile=folder/'profile.yml'
  original=source.read_bytes();before=pefile.PE(data=original,fast_load=True)
  profile.write_text('from: '+json.dumps(str(source))+'\nto: '+json.dumps(str(target))+'\ninputs: '+json.dumps({'$copyRedesignedEquipmentAssets':{'data':'','display':'true','type':10}})+'\npatches:\n'+''.join('    - '+x+'\n' for x in patches))
  process=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(profile)],cwd=fixture,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
  log=process.stdout+process.stderr;(folder/'warp.log').write_bytes(log)
  if process.returncode or b'-E-' in log or not target.exists():
   print(log.decode(errors='replace')[-7000:]);raise AssertionError('WARP failed: '+str(folder))
  after=pefile.PE(str(target),fast_load=True);base=after.OPTIONAL_HEADER.ImageBase;payload=None
  for va,is_string in sites.items():
   call=after.get_data(va-base,5);assert call[0]==0xe8
   destination=va+5+struct.unpack('<i',call[1:])[0]
   candidate=destination-blob['exports']['@HDJobStringHook@32' if is_string else '@HDJobResourceHook@12']
   if payload is None:payload=candidate
   assert payload==candidate
  expected=bytearray.fromhex(blob['hex'])
  for off in blob['relocations']:
   value=struct.unpack_from('<I',expected,off)[0];struct.pack_into('<I',expected,off,(value+payload-blob['imageBase'])&0xffffffff)
  at=blob['exports']['HDJobConfig'];actual=after.get_data(payload-base,len(expected))
  version,count,table,char_hook,string_hook=struct.unpack_from('<5I',actual,at)
  assert version==1 and count==len(manifest['pairs'])
  assert (char_hook,string_hook)==((0x1967bf0,0x1967c30) if label=='clan-v11' else (0xa8d4a0,0xa8d9f0))
  expected[at:at+20]=actual[at:at+20];assert bytes(expected)==actual,'Injected payload/relocations differ'
  section=after.get_section_by_rva(payload-base);assert section.Characteristics&0xe0000000==0xe0000000,'Payload must be RWX (cache and code)'
  def read_string(pointer):return after.get_data(pointer-base,384).split(b'\0',1)[0]
  allocations=[(payload,len(expected)),(table,count*12)]
  for i,row in enumerate(manifest['pairs']):
   pointers=struct.unpack('<3I',after.get_data(table-base+i*12,12))
   allocations.extend((p,len(read_string(p))+1) for p in pointers)
   assert list(map(read_string,pointers))==[bytes.fromhex(row['resource_hex']),row['preview'].encode(),row['fallback'].encode()]
   for name,sha in row['files'].items():
    assert hashlib.sha256((folder/'data/sprite/hd_job_ui'/name).read_bytes()).hexdigest()==sha
  # On HD-only builds the entire pre-existing executable code is unchanged,
  # except these nine verified UI call operands (including all clan world code).
  changed=[]
  if label!='altqa':
   allowed={va+j for va in sites for j in range(5)}
   for s in before.sections:
    if not s.Characteristics&0x20000000:continue
    raw=s.get_data();new=after.get_data(s.VirtualAddress,len(raw))
    changed.extend(base+s.VirtualAddress+j for j,(a,b) in enumerate(zip(raw,new)) if a!=b)
   unexpected=[va for va in changed if va not in allowed and not any(p<=va<p+n for p,n in allocations)]
   for p,n in allocations:
    old=before.get_data(p-base,n) if before.get_section_by_rva(p-base) else b''
    assert not any(old),'WARP allocation overwrote nonzero existing content'
   assert not unexpected,'Unexpected original executable bytes modified: '+str([hex(v) for v in unexpected[:20]])
  assert source.read_bytes()==original
  result=dict(case=label,target=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),ui_calls=9,payload=hex(payload),deployed_pairs=count,changed_original_call_bytes=sum(va in {site+j for site in sites for j in range(5)} for va in changed))
  rows.append(result);print(json.dumps(result),flush=True)
 (out/'results.json').write_text(json.dumps(rows,indent=2));print('PASS '+str(out),flush=True)
if __name__=='__main__':main()