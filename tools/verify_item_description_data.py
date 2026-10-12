"""Regressions for script translation and the documented DB files."""
from pathlib import Path
import json,unittest
import yaml
from generate_item_description_data import translate,translate_static,inline_grade_effects

ROOT=Path(__file__).resolve().parents[1];SERVER=ROOT.parent/'BanquetOfHeroes'

class ScriptDescriptions(unittest.TestCase):
    def test_partial_static_keeps_safe_effects(self):
        lines,gaps=translate_static('bonus bStr,5; bonus3 bAutoSpell,"MG_FIREBOLT",3,100; bonus bAgi,2;',{})
        self.assertEqual(lines,['STR +5','AGI +2']);self.assertEqual(len(gaps),1)
    def test_conditions_are_never_flattened(self):
        for branch in ['if(getrefine()>7){bonus bStr,50;bonus bDex,30;}',
                       'if(getrefine()>7) bonus bStr,50; else bonus bDex,30;']:
            lines,gaps=translate_static(branch+' bonus bAgi,2;',{})
            self.assertEqual(lines,['AGI +2']);self.assertTrue(gaps)
    def test_control_flow_stops_unconditional_claims(self):
        for barrier in ['end;','if(readparam(bStr)>99) end;','callfunc("Unknown");','for(.@i=0;.@i<5;++.@i) bonus bDex,10;']:
            lines,gaps=translate_static('bonus bStr,5;'+barrier+'bonus bAgi,2;',{})
            self.assertEqual(lines,['STR +5']);self.assertTrue(gaps)
    def test_quotes_comments_and_autobonus_are_not_effects(self):
        script='/* bonus bDex,100; */ bonus bStr,5; // ignored\n autobonus "{bonus bDex,99;}",100,1000; bonus bAgi,2;'
        lines,gaps=translate_static(script,{})
        self.assertEqual(lines,['STR +5','AGI +2']);self.assertEqual(len(gaps),1)
        fake='autobonus "if(.@g > 0) bonus bDex,.@g;",100,1000;'
        self.assertEqual(inline_grade_effects(fake,{})[0],[])
    def test_grade_branches_keep_native_semantics(self):
        for prefix in ['end;','if(getrefine()>5) end;']:
            effects,_=inline_grade_effects(prefix+'if(.@g > 0) bonus bDex,.@g;',{})
            self.assertEqual(effects,[])
        effects,_=inline_grade_effects('bonus bDex,3; .@g=getenchantgrade(); if(.@g > 0) bonus bLongAtkRate,.@g;',{})
        self.assertEqual([e['Text'] for e in effects],[f'Ranged physical damage +{n}%' for n in range(1,6)])
    def test_literal_skill_grants_and_case(self):
        skill={'Id':89,'Name':'WZ_STORMGUST','Description':'Storm Gust','MaxLevel':10};skills={89:skill,'WZ_STORMGUST':skill}
        for stmt in ['skill "WZ_STORMGUST",10;','Skill 89,10;','SKILL 89,10,SKILL_TEMP;']:
            self.assertEqual(translate(stmt,{},skills),'Enables Storm Gust Lv. 10')
        self.assertEqual(translate('addtoskill 89,1;',{},skills),'Storm Gust skill level +1')
        self.assertEqual(translate('skill 89,10,3;',{},skills),'Permanently grants Storm Gust Lv. 10 independent of the skill tree')
        self.assertIsNone(translate('skill "UNKNOWN",10;',{},skills))
        self.assertIsNone(translate('skill 89,getskilllv("WZ_STORMGUST");',{},skills))
        self.assertEqual(translate('bonus bDelayRate,-5;',{}),'After-cast delay -5%')
        self.assertEqual(translate('bonus bUnbreakableWeapon;',{}),'Indestructible weapon')
    def test_drain_units_and_invalid_option_definition(self):
        self.assertEqual(translate('bonus2 bHPDrainRate,1000,100;',{}),'100% chance to drain HP equal to 100% of damage dealt when attacking')
        self.assertEqual(translate('bonus2 bSPDrainRate,25,20;',{}),'2.5% chance to drain SP equal to 20% of damage dealt when attacking')
        self.assertIsNone(translate('bonus bHPDrainRate,getrandomoptinfo(ROA_VALUE);',{}))
    def test_complete_angra_and_existing_grade_coverage(self):
        data=yaml.safe_load((SERVER/'db/item_description_generated.yml').read_text(encoding='utf8'))
        entries={x['Id']:x for x in data['Body'] if x.get('Kind','Item')=='Item'};angra=entries[1599]
        self.assertFalse(angra['Legacy'])
        native=[e['Text'] for e in angra['Effects'] if e['Section']=='NativeEffects']
        self.assertEqual(len(native),12)
        for text in ['All stats +50','ATK +3800','MATK +200%','ATK +100%','Healing power +200%',
                     'Enables Storm Gust Lv. 10','Enables Meteor Storm Lv. 10','Enables Lord of Vermilion Lv. 10','Enables GM Sandman Lv. 1']:
            self.assertIn(text,native)
        self.assertEqual(len([e for e in angra['Effects'] if e['Section']=='Grade']),4)
        baseline=json.loads((ROOT/'tools/fixtures/item_description/baseline.json').read_text())
        known=lambda e: any(x.get('Section')=='Grade' and not x.get('Unknown') for x in e.get('Effects',[]))
        old_ids=set(baseline['grade_covered_ids'])
        self.assertTrue(old_ids <= {id for id,e in entries.items() if known(e)})
        self.assertFalse(entries[2285]['Legacy']);self.assertEqual(len(entries[2285]['Effects']),6)
    def test_headers_and_commented_examples(self):
        for relative in ['db/item_description_db.yml','db/item_description_generated.yml','db/import/item_description_db.yml','db/import-tmpl/item_description_db.yml']:
            text=(SERVER/relative).read_text(encoding='utf8')
            self.assertTrue(text.startswith('###########################################################################'))
            for field in ['MaxGrade:','RequiredCards:','Legacy:','Unknown:','{signed_value}','@reloaditemdb','REPLACES']:
                self.assertIn(field,text.split('\nHeader:',1)[0])
            data=yaml.safe_load(text);self.assertEqual(data['Header'],{'Type':'ITEM_DESCRIPTION_DB','Version':1})
        for relative in ['db/import/item_description_db.yml','db/import-tmpl/item_description_db.yml']:
            self.assertIsInstance(yaml.safe_load((SERVER/relative).read_text(encoding='utf8'))['Body'],list)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ScriptDescriptions)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    path=ROOT/'Outputs/ItemDescription/script-data-verification.json'
    path.write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2)+'\n')
    if not result.wasSuccessful():raise SystemExit(1)
