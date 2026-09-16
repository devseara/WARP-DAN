"""Build and export IDUI with real WARP in an isolated fixture, preserving profiles."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=ROOT/'2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--profile',type=Path)
    ap.add_argument('--lifecycle',choices=['remove','reapply'])
    ap.add_argument('--order',choices=['before','after'],default='after')
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    fixture=out/'warp-fixture';fixture.mkdir();(fixture/'Outputs').mkdir()
    for name in ['win32','Scripts','Tables','Patches','Inputs','Languages','Images','Styles']:
        if (ROOT/name).exists():shutil.copytree(ROOT/name,fixture/name)
    for leaf in ['AutoCombatUI','AutoSupportUI','ROGlobalZeroMenu']:
        if (ROOT/'Assets'/leaf).exists():shutil.copytree(ROOT/'Assets'/leaf,fixture/'Assets'/leaf)
    shutil.copy2(ROOT/'Patches.yml',fixture/'Patches.yml')
    marker=out/'native-manifest.json';token=uuid.uuid4().hex;target=out/'item-description.exe'
    probe='''/* IDUI isolated native export. */
ItemDescriptionBuildProbe=function(_){
 const previous=CACHE.get("ItemDescriptionUI.Native.v1");
 LIFECYCLE
 const file=new TextFile(MARKER,"w");if(!file.Valid)throw Error("Manifest unavailable");
 file.WriteLine(JSON.stringify({token:TOKEN,previousItemDescription:previous,itemDescription:CACHE.get("ItemDescriptionUI.Native.v1"),bestiary:CACHE.get("BestiaryUI.Native.v1"),sharedRoute:CACHE.get("SharedPacket0BEF.Router.v4"),extensions:CACHE.get("SharedPacket0BEF.Extensions.v1")}));file.Close();return true;
};
ItemDescriptionBuildProbe.validate=()=>true;
'''.replace('MARKER',json.dumps(str(marker))).replace('TOKEN',json.dumps(token))
    action = ''
    if args.lifecycle:
        action = 'const probeOwner=Exe.ActivePatch; Exe.SetActivePatch("ItemDescriptionUI"); ItemDescriptionUI.cleanup("ItemDescriptionUI"); Exe.ClearPatch(); Warp.SetPatchState("ItemDescriptionUI",false); '
        if args.lifecycle == 'reapply':
            action += 'Exe.SetActivePatch("ItemDescriptionUI"); Warp.SetPatchState("ItemDescriptionUI",true); ItemDescriptionUI("ItemDescriptionUI"); '
        action += 'Exe.ActivePatch=probeOwner;'
    probe=probe.replace('LIFECYCLE',action)
    (fixture/'Scripts/Patches/ItemDescriptionBuildProbe.qjs').write_bytes(probe.replace('\n','\r\n').encode())
    with (fixture/'Tables/Patch.yml').open('a',encoding='utf8')as f:f.write('\n998 : ItemDescriptionBuildProbe\n')
    with (fixture/'Patches/UI.yml').open('a',encoding='utf8') as f:
        f.write('\nItemDescriptionBuildProbeGroup:\n    title: IDUI build probe\n    patches:\n        - ItemDescriptionBuildProbe:\n            title: IDUI export probe\n            recommend: no\n            author: WARP diagnostics\n            desc: Isolated verification manifest.\n')
    profile=out/'profile.yml'
    if args.profile:
        text=args.profile.read_text(encoding='utf-8-sig')
        for key,value in [('from',str(args.source.resolve())),('to',str(target))]:
            text,count=re.subn(r'^'+key+r':[^\n]*',lambda _:key+': '+json.dumps(value),text,flags=re.M);assert count==1
        text=re.sub(r'^\s+- ItemDescriptionUI\s*$', '',text,flags=re.M)
        if args.order=='before':text=text.replace('patches:\n','patches:\n    - ItemDescriptionUI\n')
        else:text=text.rstrip()+'\n    - ItemDescriptionUI\n'
        text+='    - ItemDescriptionBuildProbe\n'
    else:
        text='from: '+json.dumps(str(args.source.resolve()))+'\nto: '+json.dumps(str(target))+'\ninputs: {}\npatches:\n    - ItemDescriptionUI\n    - ItemDescriptionBuildProbe\n'
    profile.write_text(text,encoding='utf8')
    run=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(profile)],cwd=fixture,capture_output=True,timeout=300)
    (out/'build.log').write_bytes(run.stdout+run.stderr)
    if run.returncode or b'-E-'in run.stdout+run.stderr or not target.exists() or not marker.exists():
        print((run.stdout+run.stderr).decode('utf8','replace')[-5500:]);raise RuntimeError('WARP build failed; '+str(out/'build.log'))
    manifest=json.loads(marker.read_text(encoding="utf8"));assert manifest['token']==token
    assert args.lifecycle == "remove" or manifest['itemDescription']
    report={'source':str(args.source.resolve()),'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'target':str(target),'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'build_passed':True,'live_accepted':False}
    (out/'build-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
