"""Build and verify the two-client item/grade matrix with real WARP.

Runs in a fresh isolated fixture. Records actual patch invocation order without
replacing the patch functions. The temporary feature group must be non-mutex.
This is an offline PE gate; it does not replace live screenshot acceptance.
"""
from pathlib import Path
import argparse,json,subprocess,itertools,sys,hashlib,shutil,re
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-2025',type=Path,default=root/'2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe')
parser.add_argument('--source-2026',type=Path)
parser.add_argument('--only-2025',action='store_true',help='Verify all eleven configurations for the currently supported 2025 client only')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if not args.only_2025 and args.source_2026 is None: parser.error("--source-2026 is required unless --only-2025 is selected")
if args.only_2025 and args.source_2026 is not None: parser.error("--only-2025 cannot be combined with --source-2026")
out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);fixture=out/'fixture'

for folder in ('win32','Scripts','Tables','Patches','Inputs','Languages','Styles'):shutil.copytree(root/folder,fixture/folder,dirs_exist_ok=True)
shutil.copy2(root/'Patches.yml',fixture/'Patches.yml')
with (fixture/'Tables/Patch.yml').open('a') as f:f.write('\n65002 : TestItemGradeMatrix\n')
special=(fixture/'Patches/Special.yml').read_text()
names={'item':'CustomColoredItemName','grade':'CustomColoredEnchantGradeName','labels':'CustomEnchantGradeLabels'}
blocks={}
for short,name in names.items():
 pattern=r'^        - '+name+r':\n.*?(?=^        - |\Z)'
 source_path=fixture/'Patches'/('UI.yml' if short=='labels' else 'Special.yml')
 text=source_path.read_text() if short=='labels' else special
 match=re.search(pattern,text,re.M|re.S);assert match,name
 blocks[short]=match[0];text=text[:match.start()]+text[match.end():]
 if short=='labels': source_path.write_text(text)
 else: special=text
 path=fixture/'Scripts/Patches'/f'{name}.qjs'
 code=path.read_text()
 entry=f'{name} = function(_)\n{{'
 trace=f'\n\tconst matrixSeen=CACHE.get("MatrixOrder") || []; matrixSeen.push("{short}"); CACHE.put("MatrixOrder",matrixSeen);'
 assert entry in code,name
 code=code.replace(entry,entry+trace,1)
 path.write_bytes(code.replace('\n','\r\n').encode())
sources={2025:args.source_2025.resolve()}
if not args.only_2025: sources[2026]=args.source_2026.resolve()
orders=[('item','stock',('item',))]+[('item','custom',o) for o in itertools.permutations(('item','labels'))]+[('grade','stock',o) for o in itertools.permutations(('item','grade'))]+[('grade','custom',o) for o in itertools.permutations(('item','grade','labels'))]
cases=[]
for version,source in sources.items():
 for mode,labels,order in orders:
  key=f'{version}/{mode}/{labels}/'+ '-'.join(order);stem=key.replace('/','_');target=out/(stem+'.exe');marker=out/(stem+'.json')
  tree=special+'\nItemGradeMatrixFeatures:\n    title: Matrix order\n    mutex: false\n    patches:\n'+''.join(blocks[k] for k in order)
  tree+='''\nItemGradeMatrixProbe:\n    title: Matrix probe\n    mutex: false\n    patches:\n        - TestItemGradeMatrix:\n            title: Record matrix order\n            recommend: no\n            author: WARP diagnostics\n            desc: Record native framework invocation order.\n'''
  (fixture/'Patches/Special.yml').write_text(tree)
  code='''/* Isolated native-WARP order recorder. */
TestItemGradeMatrix = function(_) {
 const file=new TextFile(MARKER,"w"); if(!file.Valid) throw Error("matrix marker failed");
 file.WriteLine(JSON.stringify({order:CACHE.get("MatrixOrder"),complete:true})); file.Close(); return true;
};
TestItemGradeMatrix.validate=function() {return true;};
ItemGradeMatrixProbe=TestItemGradeMatrix;
'''.replace('MARKER',json.dumps(marker.as_posix()))
  (fixture/'Scripts/Patches/ItemGradeMatrixProbe.qjs').write_bytes(code.replace('\n','\r\n').encode())
  inputs={'$enchantGradeMap':{'data':'','display':'Inputs/enchant_grade.yml','type':10}}
  selected=(['CustomExtName'] if version==2025 else [])+[names[x] for x in order]+['TestItemGradeMatrix']
  profile=out/(stem+'.yml');profile.write_text('from: '+json.dumps(str(source))+'\nto: '+json.dumps(str(target))+'\ninputs: '+json.dumps(inputs)+'\npatches:\n'+''.join('    - '+s+'\n' for s in selected))
  r=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(profile)],cwd=fixture,capture_output=True,timeout=180)
  (out/(stem+'.log')).write_bytes(r.stdout+r.stderr)
  seen=json.loads(marker.read_text())['order'] if marker.exists() else None
  passed=r.returncode==0 and target.exists() and b'Patch Error' not in r.stdout+r.stderr and seen==list(order)
  print(('BUILT ' if passed else 'FAIL ')+key+' observed='+str(seen),flush=True)
  cases.append({'case':key,'path':str(target),'built':passed,'observed_order':seen,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
(out/'build-summary.json').write_text(json.dumps(cases,indent=2)+'\n')
assert len(cases)==11*len(sources)
args=[sys.executable,str(root/'tools/verify_item_grade_color_contract.py')]
if len(sources)==2: args+=['--strict-matrix']
for c in cases:args+=['--case',c['case']+'='+c['path']]
with (out/'matrix-validation.log').open('wb') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=600)
print((out/'matrix-validation.log').read_text(),flush=True)
raise SystemExit(r.returncode if all(c['built'] for c in cases) else 1)
