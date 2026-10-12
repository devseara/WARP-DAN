"""Verify Bestiary title awards and publish the matching client title table.

Uses the highest-priority installed GRF table unless a loose table already
exists. Existing mappings are preserved, and only configured reward IDs may
be added or renamed. Plain Lua under .lub is supported by this client's loader.
"""
from pathlib import Path
import argparse,configparser,hashlib,json,re,shutil
import yaml
from dual_weapon_formats.grf_reader import GrfFile
ROOT=Path(__file__).resolve().parents[1]
KEY='data/luafiles514/lua files/datainfo/titletable.lub'

def sha(data):return hashlib.sha256(data).hexdigest()
def table_entries(raw):
    assert not raw.startswith(b'\x1bLua'),'This tool requires the editable source form of title_tbl'
    text=raw.decode('utf-8-sig');body=re.search(r'title_tbl\s*=\s*\{(.*?)\}',text,re.S);assert body,'title_tbl was not found'
    entries={}
    for match in re.finditer(r'\[(\d+)\]\s*=\s*("(?:[^"\\]|\\.)*")',body[1]):
        id_=int(match[1]);assert id_ not in entries;entries[id_]=json.loads(match[2])
    assert entries and 'GetTitleString' in text
    return text,body,entries

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--install',action='store_true');ap.add_argument('--grf-list',type=Path,help='Use the embedded profile GRF list instead of DATA.INI');args=ap.parse_args()
    server=ROOT.parent/'BanquetOfHeroes';game=args.game.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    titles={r['ID']:r for r in yaml.safe_load((server/'db/title_db.yml').read_text(encoding='utf-8'))['Body']}
    definitions=yaml.safe_load((server/'db/bestiary_research.yml').read_text(encoding='utf-8'))['Body'];rewards=[r for r in definitions if r.get('Kind')=='Reward' and r.get('Title')]
    assert len(rewards)==7
    grf_list=args.grf_list.resolve() if args.grf_list else game/'DATA.INI'
    cfg=configparser.ConfigParser();cfg.read(grf_list);archive=None;archive_raw=None
    for _,name in sorted(cfg['Data'].items(),key=lambda pair:int(pair[0])):
        if not (game/name).is_file():continue
        grf=GrfFile(game/name)
        try:archive_raw=grf.read(KEY)
        finally:grf.close()
        if archive_raw is not None:archive=name;break
    assert archive_raw is not None
    original=(game/KEY).read_bytes() if (game/KEY).is_file() else archive_raw
    text,_body,entries=table_entries(original);updated=text;changes=[];awards=[]
    for r in rewards:
        id_=r['Title'];title=titles[id_];assert not title.get('Script'),'Bestiary titles must remain cosmetic'
        label=title['Name'];assert label.isascii();encoded=json.dumps(label)
        if entries.get(id_)!=label:
            if id_ in entries:updated,count=re.subn(r'(\['+str(id_)+r'\]\s*=\s*)"(?:[^"\\]|\\.)*"',lambda m:m[1]+encoded,updated);assert count==1
            else:
                current=re.search(r'title_tbl\s*=\s*\{(.*?)\}',updated,re.S);inner=current[1].rstrip();inner+=('' if inner.endswith(',') else ',')+'\n\t['+str(id_)+'] = '+encoded+',\n';updated=updated[:current.start(1)]+inner+updated[current.end(1):]
            changes.append(id_)
        awards.append({'reward_id':r['Id'],'title_id':id_,'name':label,'scope':r['Scope'],'target':r['Target'],'required':r['Required'],'icon':title['Icon'],'cosmetic':True})
    # Retain the exact already-working source when every label matches.
    result=original if not changes else updated.encode('utf-8')
    _,_,after=table_entries(result);assert all(after[k]==v for k,v in entries.items() if k not in changes)
    assert all(after[r['title_id']]==r['name'] for r in awards)
    target=out/KEY;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    (out/'titletable.before.lub').write_bytes(original)
    _,_,archived_entries=table_entries(archive_raw)
    proof={'passed':True,'title_db':str(server/'db/title_db.yml'),'title_db_sha256':sha((server/'db/title_db.yml').read_bytes()),'research_definitions_sha256':sha((server/'db/bestiary_research.yml').read_bytes()),'client_key':KEY,'source_archive':archive,'grf_list':str(grf_list),'grf_list_sha256':sha(grf_list.read_bytes()),'archive_table_already_matches':all(archived_entries.get(r['title_id'])==r['name'] for r in awards),'before_sha256':sha(original),'after_sha256':sha(result),'changed_title_ids':changes,'total_title_labels':len(after),'awards':awards,'grant_contract':'Claim/Claim All records kind-2 account title entitlements atomically with the receipt. Entitlements project into each character title list; Cabinet equips only owned titles through clif_change_title.','installed':False}
    if args.install:
        dest=game/KEY;assert dest.resolve().is_relative_to(game);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,dest);assert dest.read_bytes()==result;proof['installed']=True;proof['installed_path']=str(dest)
    (out/'title-verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
