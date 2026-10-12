"""Compile attributed lore and original field notes for every loaded local mob.

Follows the selected MOB_DB footer/import chain. Only scalar monster properties
are used; drop-list merge semantics are intentionally outside this tool.
Published summaries are assigned once to the base encounter. Variants receive
original field notes, so a shared display name does not imply identical history.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse, copy, hashlib, json, re
import yaml
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tools/fixtures/bestiary/lore'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def roster(server,mode='Prerenewal'):
    mobs={};inputs={};stack=[]
    def read(relative):
        p=(server/relative).resolve()
        if p in stack:raise ValueError('Cyclic mob import: '+str(p))
        stack.append(p);inputs[p.relative_to(server).as_posix()]=sha(p)
        doc=yaml.safe_load(p.read_text(encoding='utf-8-sig'))
        assert doc['Header']['Type']=='MOB_DB'
        for row in doc.get('Body') or []:
            value=mobs.setdefault(row['Id'],{})
            for k,v in row.items():
                if isinstance(v,dict):value.setdefault(k,{}).update(copy.deepcopy(v))
                elif not isinstance(v,list):value[k]=v
        for entry in doc.get('Footer',{}).get('Imports',[]):
            if entry.get('Mode',mode).lower()==mode.lower():read(entry['Path'])
        stack.pop()
    read('db/mob_db.yml')
    assert all('Name' in m and 'AegisName' in m for m in mobs.values())
    return mobs,inputs

def habitats(server,mode):
    files={};seen=set();inputs={}
    def visit(relative):
        p=(server/relative).resolve()
        if p in seen:return
        seen.add(p)
        if not p.is_file():raise FileNotFoundError(p)
        inputs[p.relative_to(server).as_posix()]=sha(p)
        for raw in p.read_text(encoding='utf-8-sig',errors='replace').splitlines():
            line=raw.split('//',1)[0].strip()
            m=re.match(r'(npc|delnpc|import):\s*(.+)',line)
            if not m:continue
            kind,target=m.groups()
            if kind=='import':visit(target)
            elif kind=='npc':files[target]=True
            else:files.pop(target,None)
    visit('npc/'+('pre-re' if mode=='Prerenewal' else 're')+'/scripts_main.conf')
    result=defaultdict(list)
    for name in files:
        p=server/name
        if not p.is_file():continue
        inputs[p.relative_to(server).as_posix()]=sha(p)
        # Remove comments, retaining line numbers for source provenance.
        raw=p.read_text(encoding='utf-8-sig',errors='replace')
        raw=re.sub(r'/\*.*?\*/',lambda m:'\n'*m[0].count('\n'),raw,flags=re.S)
        for line_no,line in enumerate(raw.splitlines(),1):
            line=line.split('//',1)[0]
            m=re.match(r'^([^,\s]+),[^\t]+\tmonster\t[^\t]+\t(\d+),(\d+)',line)
            if m and int(m[3]):result[int(m[2])].append({'map':m[1],'path':name,'line':line_no})
    return result,inputs

REGIONS=[('prt_','Prontera country'),('mjolnir_','Mount Mjolnir'),('pay_','Payon country'),('moc_','Morocc country'),('gef_','Geffen country'),('gl_','Glastheim'),('in_sphinx','the Sphinx'),('mjo_','the coal mines'),('iz_','the waters off Izlude'),('xmas_','Lutie'),('c_tower','Aldebaran Clock Tower'),('alde_','Aldebaran country'),('yuno_','Juno country'),('mag_','Nogg Road'),('ein_','Einbroch country'),('lhz_','Lighthalzen'),('jupe','Juperos'),('ayo_','Ayothaya'),('ama_','Amatsu'),('gon_','Gonryun'),('lou_','Louyang'),('mosk_','Moscovia'),('bra_','Brasilis'),('ra_','Rachel country'),('ice_','the Ice Cave'),('ve_','Veins country'),('abbey','Nameless Island'),('nameless','Nameless Island'),('hu_','Hugel country'),('odin_','Odin Shrine'),('abyss_','Abyss Lake'),('um_','Umbala country'),('nif_','Niflheim'),('comodo','Comodo'),('cmd_','Comodo country'),('beach_','Comodo country'),('tur_','Turtle Island'),('tha_','Thanatos Tower'),('spl_','Splendide'),('man_','Manuk'),('nyd_','Nidhoggr\'s domain')]
RACE_NOTES={'Demon':'A demon belongs in a different chapter from ordinary wildlife; an inviting appearance is a poor measure of its intentions.','Undead':'Here the field journal passes beyond living nature. A careful observer records what remains without assuming the old life survives unchanged.','Angel':'Its angelic classification is a reminder that a radiant encounter deserves the same careful observation as a shadowy one.','Dragon':'The dragon chapter rewards attention to the whole creature, beyond the first striking feature that catches the eye.','Plant':'Botanical research in Midgard demands more than a pressed leaf: the subject may be an active participant in the encounter.','Insect':'Small details of an insect sighting often matter more than its first impression. The journal leaves room for close observation.','Fish':'The aquatic chapter reminds researchers that familiar shapes can conceal unfamiliar ways of surviving.','Brute':'A beast\'s familiar outline can encourage hasty assumptions. The field journal begins with observation before comparison.','DemiHuman':'A humanoid silhouette alone tells little about an encounter. Researchers distinguish what they observe from what they merely recognize.','Formless':'This subject resists the shapes by which travelers usually recognize living things, earning a place among the formless encounters.'}

def field_note(mob,base,places):
    name=mob['Name'];race=mob.get('Race','Formless');element=mob.get('Element','Neutral')
    if mob['Id']!=base['Id']:
        text=f"This encounter is recorded separately from the familiar {base['Name']}. Similar names do not guarantee the same nature or strength."
    else:text=RACE_NOTES.get(race,'The field journal records this unusual encounter through careful observation, leaving its untold history open to future research.')
    text+=f" {name} is classified as {mob.get('Size','Small').lower()}, with {element.lower()} affinity."
    regions=[]
    for place in places:
        region=next((label for prefix,label in REGIONS if place['map'].startswith(prefix)),None)
        if region and region not in regions:regions.append(region)
    if regions:text+=' Local sightings include '+ ' and '.join(regions[:2])+'.'
    elif mob.get('Class') in ['Boss','Guardian','Battlefield']:text+=' Its '+mob['Class'].lower()+' classification calls for a deliberate approach.'
    return text

def compile_lore(server,mode):
    mobs,inputs=roster(server,mode);spawns,spawn_inputs=habitats(server,mode)
    families=defaultdict(list)
    for mob in sorted(mobs.values(),key=lambda m:m['Id']):families[mob['Name']].append(mob)
    assigned={};unmatched=[]
    for filename in ['curated-00.json','curated-01.json','curated-official.json','curated-dialogue.json']:
        p=FIXTURES/filename
        for note in json.loads(p.read_text(encoding='utf-8')):
            choices=families.get(note['name'],[])
            if 'id' in note:target=mobs.get(note['id'])
            else:target=choices[0] if choices else None
            if target is None:unmatched.append(note['name']);continue
            assigned[target['Id']]=note
    rows=[];provenance=[]
    for id_,mob in sorted(mobs.items()):
        note=assigned.get(id_);base=families[mob['Name']][0]
        if note:
            text=note['summary'];label=note['attribution'];kind=note['source_kind']
            evidence={k:v for k,v in note.items() if k in ['url','path','line']}
        else:
            text=field_note(mob,base,spawns.get(id_,[]));label='Local field journal (original)';kind='original_field_note'
            evidence={'database_inputs':list(inputs),'habitats':spawns.get(id_,[]),'base_encounter':base['Id']}
        assert text and len(text.encode('utf-8'))<=16384 and len(label.encode('utf-8'))<=63 and '\0' not in text+label
        rows.append({'Id':id_,'Source':label,'Text':text})
        provenance.append({'id':id_,'name':mob['Name'],'kind':kind,**evidence})
    return rows,{'mode':mode,'counts':dict(Counter(p['kind'] for p in provenance)),'total_mobs':len(mobs),'unique_names':len(families),'unmatched_curated_names':sorted(set(unmatched)),'mob_inputs_sha256':inputs,'habitat_inputs_sha256':spawn_inputs,'curated_inputs_sha256':{p.name:sha(p) for p in sorted(FIXTURES.glob('curated-*.json'))},'entries':provenance}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');ap.add_argument('--mode',choices=['Prerenewal','Renewal'],default='Prerenewal');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--install',action='store_true');args=ap.parse_args()
    server=args.server.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    rows,report=compile_lore(server,args.mode)
    original=(server/'db/bestiary_lore.yml').read_text(encoding='utf-8-sig')
    header=original.split('Header:',1)[0].replace('# Original editorial lore displayed separately from database-derived stats.','# Attributed summaries and original field notes; see bestiary_lore_sources.json.')
    data={'Header':{'Type':'BESTIARY_LORE_DB','Version':1},'Body':rows,'Footer':{'Imports':[{'Path':'db/import/bestiary_lore.yml'}]}}
    text=header+yaml.safe_dump(data,allow_unicode=True,sort_keys=False,width=96)
    (out/'bestiary_lore.yml').write_text(text,encoding='utf-8')
    report['lore_sha256']=sha(out/'bestiary_lore.yml');report['lore_import_sha256']=sha(server/'db/import/bestiary_lore.yml');report['complete']=len(rows)==report['total_mobs'];report['source_policy']='Original paraphrases; community wiki is attributed, not treated as official canon. Original field notes fill undocumented and duplicate-name encounters. No copied wiki introductions are shipped.'
    (out/'bestiary_lore_sources.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.install:
        import shutil
        for name in ['bestiary_lore.yml','bestiary_lore_sources.json']:shutil.copy2(out/name,server/'db'/name)
    print(json.dumps({k:report[k] for k in ['total_mobs','unique_names','counts','complete','unmatched_curated_names','lore_sha256']},indent=2))
if __name__=='__main__':main()
