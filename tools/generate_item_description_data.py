"""Generate Banquet display metadata from effective server YAML, never run scripts.

Only proven constant bonus statements and top-level grade predicates are translated.
Untranslated gameplay remains explicitly available through Original. Import overrides
remain the last layer. Run after changing item/option scripts; --check detects drift.
Requires PyYAML. Does not read or change itemInfo Lua.
"""
from pathlib import Path
import argparse, ast, hashlib, json, re, operator
import yaml
from item_description_db_header import database_header
from item_description_script import ScriptReader, mask_script, continues, reachable_units

ROOT = Path(__file__).resolve().parents[1]
GRADES = {'RARE': 1, 'EPIC': 2, 'MYTHIC': 3, 'LEGENDARY': 4, 'S': 5}
SINGLE = {
    'bMaxHP': ('Max HP', ''), 'bMaxSP': ('Max SP', ''),
    **{'b'+x.title(): (x, '') for x in ['STR','AGI','VIT','INT','DEX','LUK','POW','SPL','STA','WIS','CON','CRT']},
    'bAllStats': ('All stats', ''), 'bAtk': ('ATK', ''), 'bBaseAtk': ('ATK', ''),
    'bMatk': ('MATK', ''), 'bAtkRate': ('ATK', '%'), 'bMatkRate': ('MATK', '%'),
    'bMaxHPrate': ('Max HP', '%'), 'bMaxSPrate': ('Max SP', '%'),
    'bHPrecovRate': ('HP recovery', '%'), 'bSPrecovRate': ('SP recovery', '%'),
    'bHit': ('HIT', ''), 'bFlee': ('FLEE', ''), 'bFlee2': ('Perfect Dodge', ''),
    'bCritical': ('Critical', ''), 'bDef': ('DEF', ''), 'bMdef': ('MDEF', ''),
    'bDef2': ('VIT-based DEF', ''), 'bMdef2': ('INT-based MDEF', ''),
    'bAspd': ('ASPD', ''), 'bAspdRate': ('Attack speed', '%'),
    'bCastrate': ('Cast time', '%'), 'bVariableCastrate': ('Cast time', '%'),
    'bDelayrate': ('After-cast delay', '%'), 'bUseSPrate': ('SP consumption', '%'),
    'bLongAtkRate': ('Ranged physical damage', '%'), 'bShortAtkRate': ('Melee physical damage', '%'),
    'bLongAtkDef': ('Ranged damage resistance', '%'), 'bNearAtkDef': ('Melee damage resistance', '%'),
    'bCritAtkRate': ('Critical damage', '%'), 'bCritDefRate': ('Critical damage resistance', '%'),
    'bHealPower': ('Healing power', '%'), 'bHealPower2': ('Healing received', '%'),
    'bSpeedRate': ('Movement speed (highest bonus)', '%'),
    'bHPGainValue': ('HP gained per melee kill', ''), 'bSPGainValue': ('SP gained per melee kill', ''),
    'bAtkRange': ('Attack range', ''), 'bReduceDamageReturn': ('Reflected damage resistance', '%'),
    **{'b'+x: (x.upper(), '') for x in ['PAtk','SMatk','Res','MRes','HPlus','CRate']},
}
DOUBLE = {
    'bSubEle': ('{target} damage resistance', '%'),
    'bSubDefEle': ('Physical resistance to {target} targets', '%'),
    'bMagicSubDefEle': ('Magic resistance to {target} targets', '%'),
    'bAddEle': ('Physical damage to {target} targets', '%'),
    'bMagicAddEle': ('Magic damage to {target} targets', '%'),
    'bSubRace': ('Resistance to {target}', '%'), 'bAddRace': ('Physical damage to {target}', '%'),
    'bMagicAddRace': ('Magic damage to {target}', '%'), 'bCriticalAddRace': ('Critical against {target}', ''),
    'bIgnoreDefRaceRate': ('Ignore {target} DEF', '%'), 'bIgnoreMdefRaceRate': ('Ignore {target} MDEF', '%'),
    'bAddClass': ('Physical damage to {target}', '%'), 'bSubClass': ('Resistance to {target}', '%'),
    'bMagicAddClass': ('Magic damage to {target}', '%'), 'bIgnoreDefClassRate': ('Ignore {target} DEF', '%'),
    'bIgnoreMdefClassRate': ('Ignore {target} MDEF', '%'),
    'bAddSize': ('Physical damage to {target} targets', '%'), 'bSubSize': ('Resistance to {target} targets', '%'),
    'bMagicAddSize': ('Magic damage to {target} targets', '%'), 'bMagicSubSize': ('Magic resistance to {target} targets', '%'),
    'bMagicAtkEle': ('{target} magic damage', '%'), 'bExpAddRace': ('EXP from {target}', '%'),
    'bDropAddRace': ('Drop rate from {target}', '%'),
}

def target(value):
    if not re.fullmatch(r'(?:RC|Ele|Size|Class|Eff)_\w+', value): return None
    label = value.split('_',1)[1]
    return {'DemiHuman':'Demi-Human','Player_Human':'Human players','Player_Doram':'Doram players',
            'NonBoss':'non-Boss','All':'all'}.get(label,label.replace('_',' '))

def number(expr, divisor=1):
    if re.fullmatch(r'-?\d+', expr):
        value=int(expr)/divisor
        return f'{value:+g}'
    tokens={'getrandomoptinfo(ROA_VALUE)':'signed_value', '-(getrandomoptinfo(ROA_VALUE))':'neg_value',
            'getrandomoptinfo(ROA_VALUE)/10':'value_div10'}
    if expr not in tokens: return None
    token=tokens[expr]
    if divisor != 1:
        if token!='signed_value': return None
        token={10:'value_tenths',100:'value_hundredths'}[divisor]
    return '{'+token+'}'

def translate(stmt, docs, skills=None):
    # Item-script skill grants: names are resolved from the same effective server
    # skill DB as gameplay. Commands are case-insensitive; data names stay exact.
    grant=re.fullmatch(r'(skill|addtoskill)\s+("[A-Za-z0-9_]+"|\d+)\s*,\s*(\d+)(?:\s*,\s*(\d+|SKILL_PERM|SKILL_TEMP|SKILL_TEMPLEVEL|SKILL_PERM_GRANT))?\s*;',stmt.strip(),re.I)
    if grant:
        token=grant[2];key=token[1:-1] if token.startswith('"') else int(token)
        skill=(skills or {}).get(key);level=int(grant[3])
        if not skill or not 0<level<=skill.get('MaxLevel',0):return None
        flags={'SKILL_PERM':0,'SKILL_TEMP':1,'SKILL_TEMPLEVEL':2,'SKILL_PERM_GRANT':3}
        flag=grant[4]
        flag=(flags.get(flag.upper()) if not flag.isdigit() else int(flag)) if flag else (2 if grant[1].lower()=='addtoskill' else 1)
        name=skill.get('Description',skill['Name'])
        if flag==1:return f'Enables {name} Lv. {level}'
        if flag==0:return f'Permanently grants {name} Lv. {level}'
        if flag==2:return f'{name} skill level +{level}'
        if flag==3:return f'Permanently grants {name} Lv. {level} independent of the skill tree'
        return None
    noarg=re.fullmatch(r'bonus\s+(bUnbreakableWeapon|bUnbreakableArmor)\s*;',stmt.strip(),re.I)
    if noarg:return 'Indestructible weapon' if noarg[1].lower()=='bunbreakableweapon' else 'Indestructible armor'
    m=re.fullmatch(r'bonus([2-5]?)\s+(\w+)\s*,\s*(.*?)\s*;',stmt.strip(),re.S|re.I)
    if not m: return None
    name=m[2]
    for canonical in (*SINGLE,*DOUBLE,'bAddMaxWeight','bAtkEle','bDefEle','bNoSizeFix','bUnbreakableWeapon','bUnbreakableArmor','bResEff','bHPDrainRate','bSPDrainRate'):
        if canonical.lower()==name.lower():name=canonical;break
    args=[x.strip() for x in m[3].split(',')]; arity=int(m[1] or 1)
    if len(args)!=arity:return None
    if arity==2 and name in ('bHPDrainRate','bSPDrainRate') and all(re.fullmatch(r'\d+',x) for x in args):
        chance,amount=map(int,args)
        if 0<=chance<=1000 and 0<amount<=2147483647:
            resource='HP' if name=='bHPDrainRate' else 'SP'
            return f'{chance/10:g}% chance to drain {resource} equal to {amount}% of damage dealt when attacking'
        return None
    if arity==1 and name in SINGLE:
        num=number(args[0]); label,unit=SINGLE[name]
        return label+' '+num+unit if num is not None else None
    if arity==1 and name=='bAddMaxWeight':
        num=number(args[0],10);return 'Weight capacity '+num if num is not None else None
    if arity==1 and name in ['bAtkEle','bDefEle']:
        t=target(args[0]);return ('Weapon element: ' if name=='bAtkEle' else 'Armor element: ')+t if t else None
    fixed={'bNoSizeFix':'Ignore weapon size penalty','bUnbreakableWeapon':'Indestructible weapon','bUnbreakableArmor':'Indestructible armor'}
    if arity==1 and name in fixed and args[0]=='1':return fixed[name]
    if arity in (2,3) and name in DOUBLE:
        if arity==3 and not (name=='bSubRace' and args[2]=='BF_WEAPON'):return None
        t=target(args[0]);num=number(args[1]);label,unit=DOUBLE[name]
        if t and num is not None:return ('Physical ' if arity==3 else '')+label.format(target=t)+' '+num+unit
    if arity==2 and name=='bResEff':
        t=target(args[0]);num=number(args[1],100)
        if t and num is not None:return t+' resistance '+num+'%'
    # Exact documented constant bonus signatures cover less common grade effects.
    # Do not substitute dynamic expressions or guess undocumented parameter units.
    doc=docs.get((name,arity))
    if doc is None:doc=next((v for (key,n),v in docs.items() if n==arity and key.lower()==name.lower()),None)
    if not doc or any(not re.fullmatch(r'-?\d+|(?:RC|Ele|Size|Class|Eff)_\w+',x) for x in args):return None
    params,text=doc
    for param,arg in zip(params,args):
        if not re.fullmatch(r'[a-z]',param):return None
        if re.fullmatch(r'-?\d+',arg):
            text=re.sub(r'\b'+param+r'/(10|100|1000)\b',lambda m:f'{int(arg)/int(m[1]):g}',text)
        text=re.sub(r'\b'+param+r'\b',target(arg) or arg,text)
    return text

def translate_block(block,docs,skills=None):
    # A complete statically-known block. Conditionals are kept together and are
    # never flattened into always-on effects by splitting on semicolons.
    try:
        units=list(ScriptReader(block).units())
    except ValueError:return None
    lines=[translate(unit,docs,skills) for _,_,unit in units]
    return lines if lines and all(x is not None for x in lines) else None

def translate_static(script,docs,skills=None):
    """Keep known unconditional effects while marking only untranslated content."""
    lines=[];untranslated=[]
    try:
        reader=ScriptReader(script);units=iter(reader.units())
        for start,end,unit in units:
            text=translate(unit,docs,skills)
            if text is not None:lines.append(text)
            else:untranslated.append(unit.strip())
            if not continues(unit):
                tail=reader.clean[end:].strip()
                if tail:untranslated.append(tail)
                break
    except ValueError:
        # Known prefix statements are still valid; the malformed/unsupported tail
        # is visible in the audit and retains the Original fallback.
        untranslated.append(script)
    return lines,untranslated

def grade_unit_ranges(script):
    ranges=set()
    try:
        for start,end,unit in reachable_units(script):
            ranges.add((start,end))
            # A top-level grade if/else has an independently provable true arm.
            # Keep the untranslated else in the fallback instead of losing the
            # grade preview that was already supported by earlier data versions.
            match=re.match(r'if\s*\(\s*\.@g\s*(?:==|>=)\s*ENCHANTGRADE_\w+\s*\)\s*\{[^{}]*\}',unit,re.S)
            if match and re.match(r'\s*else\b',unit[match.end():]):ranges.add((start,start+match.end()))
    except ValueError:pass
    return ranges

def grade_integer(expr, grade):
    """Evaluate only bounded integer arithmetic in a captured grade bonus argument."""
    tree=ast.parse(expr.replace('.@g',str(grade)).strip(),mode='eval')
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            v=visit(n.operand);return -v if isinstance(n.op,ast.USub) else v
        if isinstance(n,ast.BinOp) and type(n.op) in (ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Mod):
            a,b=visit(n.left),visit(n.right)
            if type(n.op) in (ast.Div,ast.Mod):
                if not b:raise ValueError('division by zero')
                q=abs(a)//abs(b)*(1 if (a>=0)==(b>=0) else -1)
                v=q if isinstance(n.op,ast.Div) else a-q*b
            else:v={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul}[type(n.op)](a,b)
            if abs(v)>2147483647:raise ValueError('overflow')
            return v
        raise ValueError('unsupported expression')
    if sum(1 for _ in ast.walk(tree))>40:raise ValueError('expression too complex')
    return visit(tree.body)

def inline_grade_effects(script, docs, skills=None):
    # Only a complete top-level single-statement if; no else, nesting, script calls,
    # or character-dependent expression can be promoted to an active grade effect.
    pattern=re.compile(r'if\s*\(\s*\.@g\s*(>=|<=|==|!=|>|<)\s*(\d+|ENCHANTGRADE_\w+)\s*\)\s*(bonus[2-5]?\s+\w+\s*,[^;{}]+;)')
    effects=[];remaining=script;ranges=grade_unit_ranges(script)
    compare={'>':operator.gt,'<':operator.lt,'>=':operator.ge,'<=':operator.le,'==':operator.eq,'!=':operator.ne}
    for m in pattern.finditer(script):
        if (m.start(),m.end()) not in ranges:continue
        bound=GRADES.get(m[2].replace('ENCHANTGRADE_','')) if m[2].startswith('ENCHANTGRADE_') else int(m[2])
        if bound is None:continue
        output=[]
        for grade in range(6):
            if not compare[m[1]](grade,bound):continue
            statement=m[3];head,args=statement[:-1].split(',',1)
            try:
                values=[str(grade_integer(a,grade)) if '.@g' in a else a.strip() for a in args.split(',')]
                line=translate(head+','+','.join(values)+';',docs,skills)
            except (ValueError,SyntaxError,RecursionError):line=None
            if line is None:output=[];break
            label=next((k.title() for k,v in GRADES.items() if v==grade),'None')
            output.append({'Section':'Grade','Label':label,'MinGrade':grade,'MaxGrade':grade,'Text':line})
        if output:effects.extend(output);remaining=remaining.replace(m[0],'',1)
    return effects,remaining

def load_db(server,relative,mode,sources,entries=None):
    if entries is None:entries={}
    path=server/relative;raw=path.read_bytes();sources[relative]=hashlib.sha256(raw).hexdigest()
    data=yaml.safe_load(raw)
    for row in data.get('Body',[]) or []:entries.setdefault(row['Id'],{}).update(row)
    for imp in data.get('Footer',{}).get('Imports',[]):
        if imp.get('Mode',mode).lower()!=mode.lower():continue
        load_db(server,imp['Path'],mode,sources,entries)
    return entries

def generate(server):
    sources={};items=load_db(server,'db/item_db.yml','Prerenewal',sources)
    options=load_db(server,'db/item_randomopt_db.yml','Prerenewal',sources)
    skill_rows=load_db(server,'db/skill_db.yml','Prerenewal',sources)
    skills={key:row for row in skill_rows.values() for key in (row['Id'],row['Name'])}
    raw=(server/'doc/item_bonus.txt').read_text(encoding='utf8');docs={}
    sources['doc/item_bonus.txt']=hashlib.sha256((server/'doc/item_bonus.txt').read_bytes()).hexdigest()
    sources['doc/script_commands.txt']=hashlib.sha256((server/'doc/script_commands.txt').read_bytes()).hexdigest()
    for m in re.finditer(r'^bonus([2-5]?)\s+(\w+),([^;]+);[ \t]+([^\n]+)',raw,re.M):
        # Ignore descriptions that visibly continue onto another line.
        if m[4].count('(')!=m[4].count(')'):continue
        docs[(m[2],int(m[1] or 1))]=(m[3].split(','),m[4].strip())
    body=[];untranslated=[];grade_count=0;native_count=0;script_gaps=[];capped=[]
    pattern=re.compile(r'if\s*\(\.@g\s*(==|>=)\s*ENCHANTGRADE_(RARE|EPIC|MYTHIC|LEGENDARY|S)\)\s*\{([^{}]*)\}',re.S)
    for id,it in sorted(items.items()):
        script=mask_script(it.get('Script',''));effects=[];remaining=script
        ranges=grade_unit_ranges(script)
        if 'getenchantgrade' in script:
            inline,remaining=inline_grade_effects(script,docs,skills);effects.extend(inline)
            for m in pattern.finditer(script):
                # A nested condition cannot be promoted to an unconditional tier effect.
                if (m.start(),m.end()) not in ranges:continue
                lines=translate_block(m[3],docs,skills)
                if not lines:continue
                grade=GRADES[m[2]]
                effect={'Section':'Grade','Label':m[2].title()+(' / S' if m[2]=='LEGENDARY' and m[1]=='>=' else ''),
                        'MinGrade':grade,'MaxGrade':grade if m[1]=='==' else 255,'Text':'; '.join(lines)}
                effects.append(effect);remaining=remaining.replace(m[0],'',1)
            remaining=re.sub(r'\.@g\s*=\s*getenchantgrade\(\)\s*;','',remaining)
            if effects:grade_count+=1
            if '.@g' in remaining or 'getenchantgrade' in remaining:
                untranslated.append(id)
                effects.append({'Section':'Grade','Unknown':True,'Text':'Additional conditional grade effects are shown in Original.'})
        # Simple complete static effects (not arbitrary script simulation), including cards.
        lines,gaps=translate_static(remaining,docs,skills) if remaining.strip() else ([],[])
        legacy=bool(gaps)
        if gaps:script_gaps.append({'id':id,'shown_effects':len(lines),'remaining':gaps})
        if lines:
            effects=[{'Section':'NativeEffects','Text':line} for line in lines]+effects;native_count+=1
        if len(effects)>64:
            capped.append(id);effects=effects[:64];legacy=True
        if effects:body.append({'Id':id,'Legacy':legacy,'Effects':effects})
    option_issues=[]
    for id,opt in sorted(options.items()):
        script=opt.get('Script','');lines=translate_block(script,docs)
        if id==35 and re.fullmatch(r'for\(\.@i = Ele_Water; \.@i < Ele_Undead; \+\+\.@i\)\s*bonus2 bSubEle,\.@i,getrandomoptinfo\(ROA_VALUE\);\s*',script):
            lines=['Element resistance (except Neutral and Undead) {signed_value}%']
        effect={'Text':'; '.join(lines)} if lines else {'Unknown':True,'Text':'Effect unavailable: this server definition needs review.'}
        if not lines:option_issues.append({'id':id,'script':script})
        label=opt['Option'].replace('_',' ').title()
        body.append({'Id':id,'Kind':'RandomOption','Label':label[:47],'Effects':[effect]})
    data={'Header':{'Type':'ITEM_DESCRIPTION_DB','Version':1},'Body':body}
    report={'source_sha256':sources,'items':len(items),'grade_items':grade_count,'static_effect_items':native_count,
            'random_options':len(options),'untranslated_grade_items':untranslated,'option_definition_issues':option_issues,
            'item_script_gaps':script_gaps,'capped_items':capped}
    return database_header('generated')+yaml.safe_dump(data,sort_keys=False,allow_unicode=True,width=110),report

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');ap.add_argument('--check',action='store_true');args=ap.parse_args()
    text,report=generate(args.server);out=args.server/'db/item_description_generated.yml'
    if args.check:
        assert out.read_text(encoding='utf8')==text,'Generated description data is stale'
    else:out.write_text(text,encoding='utf8')
    report_path=ROOT/'Outputs/ItemDescription/generated-data-report.json';report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:len(v) if isinstance(v,(list,dict)) else v for k,v in report.items()},indent=2))
if __name__=='__main__':main()
