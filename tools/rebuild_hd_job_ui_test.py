"""Rebuild the profiled v11 test client with its current GRF list embedded.
This deployment repair is separate from the nine UI-only preview call hooks.
It preserves the supplied v11 input and all original embedded-list code.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX
ROOT=Path(__file__).resolve().parents[1]
REFERENCE_HASH='f0d962c64c0449eaec24010c75a331ee087a4807fb8bdd42e3d097680e99709c'

def embedded_profile(pe):
    base=pe.OPTIONAL_HEADER.ImageBase;start=0x181f2f0;pos=start;rows=[];manager=addpak=None
    while pe.get_data(pos-base,1)==b'\xe8':
        length=struct.unpack('<i',pe.get_data(pos-base+1,4))[0]
        if not 1<=length<=128:raise ValueError('Unexpected embedded filename length')
        name=pe.get_data(pos-base+5,length)
        if name[-1:]!=b'\0':raise ValueError('Unterminated embedded GRF name')
        suffix=pe.get_data(pos-base+5+length,10)
        if suffix[0]!=0xb9 or suffix[5]!=0xe8:raise ValueError('Unprofiled AddPak stub')
        m=struct.unpack_from('<I',suffix,1)[0];target=pos+5+length+10+struct.unpack_from('<i',suffix,6)[0]
        if manager is not None and (m,target)!=(manager,addpak):raise ValueError('Mixed GRF loader ABI')
        manager,addpak=m,target;rows.append(name[:-1].decode('ascii'));pos+=5+length+10
    if pe.get_data(pos-base,1)!=b'\xc3' or len(rows)!=8:raise ValueError('Unprofiled embedded list')
    calls=[]
    for section in pe.sections:
        if not section.Characteristics&0x20000000:continue
        raw=section.get_data();at=0
        while (at:=raw.find(b'\xe8',at))>=0:
            if at+5<=len(raw):
                va=base+section.VirtualAddress+at
                if va+5+struct.unpack_from('<i',raw,at+1)[0]==start:calls.append(va)
            at+=1
    if len(calls)!=1:raise ValueError('Embedded list startup call is not unique')
    return dict(start=start,call=calls[0],original=pe.get_data(calls[0]-base,5).hex(),manager=manager,addpak=addpak,old_priority=list(reversed(rows)))

def verify_loader(pe,profile,names):
    base=pe.OPTIONAL_HEADER.ImageBase;call=pe.get_data(profile['call']-base,5);entry=profile['call']+5+struct.unpack_from('<i',call,1)[0]
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
    u.mem_map(0x30000000,0x10000);sp=0x30008000;stop=0x30009000;u.mem_write(sp,struct.pack('<I',stop));u.reg_write(UC_X86_REG_ESP,sp)
    actual=[];u.mem_write(profile['addpak'],b'\xc2\x04\x00')
    def hook(machine,address,size,extra):
        if address!=profile['addpak']:return
        assert machine.reg_read(UC_X86_REG_ECX)==profile['manager']
        arg=struct.unpack('<I',machine.mem_read(machine.reg_read(UC_X86_REG_ESP)+4,4))[0]
        value=bytearray()
        for i in range(128):
            c=machine.mem_read(arg+i,1)[0]
            if c==0:break
            value.append(c)
        actual.append(value.decode('ascii'));machine.reg_write(UC_X86_REG_EAX,1)
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry,stop,count=10000)
    assert actual==list(reversed(names)),actual
    assert u.reg_read(UC_X86_REG_ESP)==sp+4
    return entry

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--client-dir',type=Path,required=True)
    ap.add_argument('--warp-root',type=Path,default=ROOT);ap.add_argument('--deploy',action='store_true')
    ap.add_argument('--label',required=True,help='Unique v<number> output label; existing outputs are never overwritten')
    ap.add_argument('--only-check',action='store_true')
    ap.add_argument('--data-ini',type=Path,help='Explicit test archive list; defaults to client DATA.INI')
    args=ap.parse_args()
    if not re.fullmatch(r'v[0-9]+',args.label):raise ValueError('Expected v<number> label')
    source=args.source.resolve();client=args.client_dir.resolve();raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=REFERENCE_HASH:raise ValueError('Expected the verified ClanBodySkins v11 input')
    pe=pefile.PE(data=raw,fast_load=True);profile=embedded_profile(pe)
    text=(args.data_ini or client/'DATA.INI').read_text(encoding='ascii');rows=re.findall(r'^(\d+)\s*=\s*([^\r\n]+)',text,re.M)
    if not 1<=len(rows)<=10 or len({int(i) for i,n in rows})!=len(rows):raise ValueError('Expected unique GRF priorities, at most ten')
    names=[name.strip() for index,name in sorted(rows,key=lambda row:int(row[0]))]
    if len(set(n.lower() for n in names))!=len(names):raise ValueError('Duplicate GRF entries')
    for name in names:
        if not name.isascii() or len(name)>120 or Path(name).name!=name or not name.lower().endswith('.grf'):raise ValueError('Expected local ASCII GRF basename')
        if not (client/name).is_file():raise FileNotFoundError(client/name)
    if not set(profile['old_priority']).issubset(names):raise ValueError('Current INI omits a previously embedded archive')
    out=Path(tempfile.mkdtemp(prefix='hd-job-ui-'+args.label+'-',dir=ROOT/'Outputs'));fixture=out/'fixture';fixture.mkdir()
    for name in ('win32','Scripts','Tables','Patches','Inputs','Languages','Styles','Assets','Images'):
        shutil.copytree(args.warp_root/name,fixture/name,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(args.warp_root/'Patches.yml',fixture/'Patches.yml')
    code='''/* Refresh only the verified v11 startup GRF list from the supplied DATA.INI. */
RefreshHDJobTestGRFs = function(_) {
 const profile=PROFILE, names=NAMES;
 const at=Exe.Vir2Phy(profile.call);
 if(Exe.GetHex(at,5).replace(/ /g,'').toLowerCase()!==profile.original)
  throw Error('RefreshHDJobTestGRFs: startup call bytes differ');
 const size=1+names.reduce((n,s)=>n+16+s.length,0);
 const [phy,vir]=Exe.Allocate(size,0x10);let bytes=[];
 const put32=x=>{for(const shift of [0,8,16,24])bytes.push((x>>>shift)&255);};
 for(const name of names.slice().reverse()) {
  bytes.push(0xe8);put32(name.length+1);
  for(const c of name)bytes.push(c.charCodeAt(0));bytes.push(0);
  bytes.push(0xb9);put32(profile.manager);
  bytes.push(0xe8);put32((profile.addpak-(vir+bytes.length+4))>>>0);
 }
 bytes.push(0xc3);
 Exe.SetHex(phy,bytes.map(b=>b.toString(16).padStart(2,'0')).join(' '));
 const delta=(vir-profile.call-5)>>>0;
 Exe.SetHex(at,'E8 '+[0,8,16,24].map(s=>((delta>>>s)&255).toString(16).padStart(2,'0')).join(' '));
 return true;
};
RefreshHDJobTestGRFs.validate=()=>Exe.BuildDate===20250716;
'''.replace('PROFILE',json.dumps(profile)).replace('NAMES',json.dumps(names))
    (fixture/'Scripts/Patches/RefreshHDJobTestGRFs.qjs').write_bytes('\n'.join(re.sub(r'^ +',lambda m:'\t'*len(m[0]),line) for line in code.splitlines()).replace('\n','\r\n').encode())
    with (fixture/'Tables/Patch.yml').open('a') as f:f.write('\n64981 : RefreshHDJobTestGRFs\n')
    with (fixture/'Patches/Premium.yml').open('a') as f:f.write('\nHDTestArchiveRefresh:\n    title: HD test archive refresh\n    patches:\n        - RefreshHDJobTestGRFs:\n            title: Refresh verified v11 archive list\n            recommend: no\n            author: Codex\n            desc: Isolated deployment fixture.\n')
    results=[]
    cases=[('check',['RefreshHDJobTestGRFs','HDJobSpritePreviews'])]
    if not args.only_check:cases.append(('control',['RefreshHDJobTestGRFs']))
    for label,patches in cases:
        folder=out/label;folder.mkdir();target=folder/f'hd-job-ui-{args.label}-{label}.exe';file=folder/'profile.yml'
        file.write_text('from: '+json.dumps(str(source))+'\nto: '+json.dumps(str(target))+'\ninputs: {}\npatches:\n'+''.join('    - '+n+'\n' for n in patches))
        run=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(file)],cwd=fixture,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        log=run.stdout+run.stderr;(folder/'warp.log').write_bytes(log)
        if run.returncode or b'-E-' in log or not target.exists():raise RuntimeError(log.decode(errors='replace'))
        final=pefile.PE(str(target),fast_load=True);entry=verify_loader(final,profile,names)
        ui=[0x7acd71,0x7acdb1,0x7aec6b,0x7aed3f,0x974b20,0x974b56,0x974b76,0x974d35,0x974e04]
        changed={profile['call']+i for i in range(5)}
        if label=='check':changed.update(v+i for v in ui for i in range(5))
        # Verify the existing .text and every pre-existing nonzero code byte.
        for section in pe.sections:
            if not section.Characteristics&0x20000000:continue
            before=section.get_data();after=final.get_data(section.VirtualAddress,len(before))
            bad=[0x400000+section.VirtualAddress+i for i,(a,b) in enumerate(zip(before,after)) if a!=b and (a!=0 or section.Name.rstrip(b'\0')==b'.text') and 0x400000+section.VirtualAddress+i not in changed]
            assert not bad,[hex(v) for v in bad[:10]]
        if args.deploy:
            destination=client/target.name
            if destination.exists():raise FileExistsError(destination)
            shutil.copy2(target,destination)
            if (folder/'data').exists():shutil.copytree(folder/'data',client/'data',dirs_exist_ok=True)
        result={'case':label,'file':str(client/target.name if args.deploy else target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'embedded_priority':names,'loader':hex(entry),'startup_call':hex(profile['call']),'ui_hook_enabled':label=='check'}
        results.append(result);print(json.dumps(result),flush=True)
    assert source.read_bytes()==raw
    (out/'results.json').write_text(json.dumps(results,indent=2));print('PASS '+str(out))
if __name__=='__main__':main()