"""Build/deploy an isolated native ACT UI test EXE and exact HD Swordman GRF."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import pefile
from build_native_act_job_ui import ROOT
sys.path.insert(0,str(ROOT/'Outputs/native-act-ui-deps'))
from native_act_test_archives import embedded_profile, verify_loader, REFERENCE_HASH
from verify_native_act_job_ui_warp import fixture_at, export, verify
from dual_weapon_formats.grf_reader import GrfFile
from hd_job_ui_assets import act_layers
from package_hd_job_ui_grf import write_grf


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--client-dir',type=Path,required=True)
    ap.add_argument('--fixture',type=Path)
    ap.add_argument('--label',default='v1',choices=['v1','v2','v3','v4','v5'])
    ap.add_argument('--deploy',action='store_true')
    ap.add_argument('--monk-clan-test-alias',action='store_true',help='Explicitly substitute clan Swordman artwork on Monk for renderer diagnostics')
    args=ap.parse_args();client=args.client_dir.resolve();source=client/'clan-skins-v11-check.exe'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==REFERENCE_HASH
    profile=embedded_profile(pefile.PE(str(source)))
    out=Path(tempfile.mkdtemp(prefix='native-act-live-'+args.label+'-',dir=ROOT/'Outputs'))
    fixture=args.fixture.resolve() if args.fixture else fixture_at(out)
    archive_name='native_act_hd_'+args.label+'.grf';exe_name='native-act-hd-'+args.label+'.exe'
    names=[archive_name]+profile['old_priority']
    assert len(names)<=10 and all((client/n).is_file() for n in names[1:])
    if args.deploy:
        assert not (client/archive_name).exists() and not (client/exe_name).exists(),'Choose a fresh label; never overwrite a test release'
    files={};resources=[];g=GrfFile(client/'update.grf')
    try:
        for sex in ['남','여']:
            stem='data/sprite/clan_skins/1/인간족/몸통/'+sex+'/검사_'+sex
            pair={ext:g.read(stem+ext) for ext in ['.spr','.act']}
            assert all(pair.values()),'Missing complete installed HD Swordman pair'
            layers,_=act_layers(pair['.act'])
            scales=sorted(set((l['sx'],l['sy']) for l in layers if l['index']>=0))
            assert scales==[(.25,.25)],scales
            # Exact world bytes at both the clan and ordinary Swordman paths.
            # The alias lets an ordinary Swordman exercise the HD test without
            # requiring server-selected clan body state. This is fixture-only.
            destinations=[stem,stem.replace('clan_skins/1/','')]
            if args.monk_clan_test_alias:
                for suffix in ['', '_h']:
                    destinations.append('data/sprite/인간족/몸통/'+sex+'/몽크'+suffix+'_'+sex)
            for destination in destinations:
                for ext,raw in pair.items():files[destination+ext]=raw
            resources.append(dict(source_grf='update.grf',source=stem,destinations=destinations,scales=scales,
                                  files={ext:hashlib.sha256(raw).hexdigest() for ext,raw in pair.items()}))
    finally:g.close()
    write_grf(files,out/archive_name)
    code='''/* Isolated test EXE archive list; preserves every existing archive. */
NativeActTestArchives = function(_) {
 const profile=PROFILE,names=NAMES;
 const at=Exe.Vir2Phy(profile.call);
 if(Exe.GetHex(at,5).replace(/ /g,'').toLowerCase()!==profile.original)
  throw Error('NativeActTestArchives: unsupported startup call');
 const [phy,vir]=Exe.Allocate(1+names.reduce((n,s)=>n+s.length+16,0),0x10);
 let bytes=[];const put32=x=>{for(const shift of [0,8,16,24])bytes.push((x>>>shift)&255);};
 for(const name of names.slice().reverse()) {
  bytes.push(0xe8);put32(name.length+1);for(const c of name)bytes.push(c.charCodeAt(0));bytes.push(0);
  bytes.push(0xb9);put32(profile.manager);bytes.push(0xe8);put32((profile.addpak-(vir+bytes.length+4))>>>0);
 }
 bytes.push(0xc3);Exe.SetHex(phy,bytes.map(b=>b.toString(16).padStart(2,'0')).join(' '));
 const delta=(vir-profile.call-5)>>>0;
 Exe.SetHex(at,'E8 '+[0,8,16,24].map(s=>((delta>>>s)&255).toString(16).padStart(2,'0')).join(' '));
 return true;
};
NativeActTestArchives.validate=()=>Exe.BuildDate===20250716;
'''.replace('PROFILE',json.dumps(profile)).replace('NAMES',json.dumps(names))
    (fixture/'Scripts/Patches/NativeActTestArchives.qjs').write_bytes('\r\n'.join(('\t'*(len(line)-len(line.lstrip(' '))))+line.lstrip(' ') for line in code.splitlines()).encode())
    table=fixture/'Tables/Patch.yml'
    with table.open('a',encoding='utf-8') as f:f.write('\n64982 : NativeActTestArchives\n')
    premium=fixture/'Patches/Premium.yml'
    if premium.read_text(encoding='utf-8').strip()=='{}':
        premium.write_text('',encoding='utf-8')
    with premium.open('a',encoding='utf-8') as f:
        f.write('\nNativeActTest:\n    title: Native ACT isolated test\n    patches:\n        - NativeActTestArchives:\n            title: Native ACT test archives\n            recommend: no\n            author: Louis T Steinhil\n            desc: Isolated fixture archive list.\n')
    # WARP restores its own patch metadata when reopening an exported EXE.
    # Apply both changes in one export so the archive-list edit stays active.
    target=export(fixture,out/'native-stage',source,['NativeActTestArchives','NativeActJobPreviews'])
    final=pefile.PE(str(target));archive_entry=verify_loader(final,profile,names)
    archive_size=1+sum(len(name)+16 for name in names)
    result=verify(source,target,extra_writes=[(profile['call'],5)],extra_allocations=[(archive_entry,archive_size)])
    old=pefile.PE(str(source))
    previous=old.get_data(archive_entry-0x400000,archive_size) if old.get_section_by_rva(archive_entry-0x400000) else b''
    assert not any(previous),'Archive stub overwrote existing bytes'
    shutil.copy2(target,out/exe_name)
    report=dict(label=args.label,exe=exe_name,grf=archive_name,exe_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                grf_sha256=hashlib.sha256((out/archive_name).read_bytes()).hexdigest(),embedded_priority=names,
                source_sha256=REFERENCE_HASH,resources=resources,generated_previews=False,monk_clan_test_alias=args.monk_clan_test_alias,
                live_acceptance='pending',pe_verification=result)
    (out/'release.json').write_text(json.dumps(report,indent=2))
    appearance=('This explicitly substitutes HD clan Swordman artwork on male/female Monk for diagnostics.\n' if args.monk_clan_test_alias else
                'Monk retains its original artwork from the existing archives. HD clan artwork is restricted to Swordman paths.\n')
    notes=('Run '+exe_name+' from this game folder. It loads '+archive_name+' first through its own embedded archive list.\n'
           +appearance+
           'Compare world, Alt+Q standing and Alt+S seated previews, head alignment, directions and repeated reopening.\n'
           'No generated UI pairs are included or required. DATA.INI and the existing game EXEs were not changed.\n'
           'This is a prototype; live visual acceptance is pending.\n')
    (out/'README.txt').write_text(notes)
    if args.deploy:
        for name in [archive_name,exe_name]:shutil.copy2(out/name,client/name)
        shutil.copy2(out/'release.json',client/('native-act-hd-'+args.label+'-release.json'))
        (client/('native-act-hd-'+args.label+'-README.txt')).write_text(notes)
        assert hashlib.sha256((client/exe_name).read_bytes()).hexdigest()==report['exe_sha256']
        assert hashlib.sha256((client/archive_name).read_bytes()).hexdigest()==report['grf_sha256']
    print(json.dumps(dict(output=str(out),deployed=args.deploy,client=str(client),exe=exe_name,grf=archive_name)),flush=True)


if __name__=='__main__':main()
