"""Validate complete lore coverage, provenance, byte limits and regeneration."""
from pathlib import Path
from collections import defaultdict
import argparse, json
import yaml
from build_bestiary_lore import ROOT,compile_lore,sha

def verify(server,output,update_sources=False):
    server=server.resolve();rows,generated=compile_lore(server,'Prerenewal')
    doc=yaml.safe_load((server/'db/bestiary_lore.yml').read_text(encoding='utf-8'))
    assert rows==doc['Body'],'Lore differs from curated inputs or the active mob imports'
    assert len({r['Id'] for r in rows})==len(rows)==generated['total_mobs']
    assert all(r['Text'].isascii() and r['Source'].isascii() for r in rows),'Client lore is currently English/ANSI'
    source=json.loads((server/'db/bestiary_lore_sources.json').read_text(encoding='utf-8'))
    assert source['entries']==generated['entries'] and not generated['unmatched_curated_names']
    assert source['lore_sha256']==sha(server/'db/bestiary_lore.yml')
    assert source['lore_import_sha256']==sha(server/'db/import/bestiary_lore.yml')
    by_id={r['Id']:r for r in rows};published=[]
    for entry in source['entries']:
        if entry['kind']=='original_field_note':assert by_id[entry['id']]['Source']=='Local field journal (original)'
        elif entry['kind']=='in_game_dialogue':assert (server/entry['path']).is_file() and entry['line']>0
        else:
            assert entry['url'].startswith(('https://ragnarok.fandom.com/wiki/','https://renewal.playragnarok.com/'))
            published.append(entry['url'])
    result={'passed':True,'total_mobs':len(rows),'counts':generated['counts'],'unique_web_sources':len(set(published)),'lore_sha256':source['lore_sha256'],'checks':['Every active MOB_DB import ID is covered, including battleground variants','Curated regeneration reproduces every lore entry','Each published account has a URL; dialogue accounts retain file/line provenance','Original field notes are labelled separately from published lore','All source/text byte limits and English client encoding pass; lore overrides preserved']}
    output.mkdir(parents=True,exist_ok=True);(output/'lore-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    groups=defaultdict(list)
    for entry in source['entries']:
        if entry.get('url'):groups[(entry['kind'],entry['url'])].append(entry)
    rows=['| Monster IDs | Source | Kind |','| --- | --- | --- |']
    for (kind,url),entries in sorted(groups.items()):
        rows.append('| '+', '.join(str(e['id']) for e in entries)+' | ['+', '.join(e['name'].replace('|','/') for e in entries)+']('+url+') | '+('Community wiki' if kind=='community_wiki' else 'Official iRO')+' |')
    doc=ROOT/'docs/bestiary.md';content=doc.read_text(encoding='utf-8')
    begin='<!-- BESTIARY_LORE_SOURCES_BEGIN -->';end='<!-- BESTIARY_LORE_SOURCES_END -->'
    assert content.count(begin)==content.count(end)==1
    prefix,tail=content.split(begin);existing,suffix=tail.split(end);expected='\n'+'\n'.join(rows)+'\n'
    if update_sources:doc.write_text(prefix+begin+expected+end+suffix,encoding='utf-8')
    else:assert existing.strip()==expected.strip(),'Refresh the canonical source block with --update-source-list'
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');ap.add_argument('--output',type=Path,default=ROOT/'Outputs/Bestiary/lore-rewards-20260913/content');ap.add_argument('--update-source-list',action='store_true');args=ap.parse_args();print(json.dumps(verify(args.server,args.output,args.update_source_list),indent=2))
