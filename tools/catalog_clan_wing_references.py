"""Read the installed sprite archive and catalog native directional wings."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
from audit_clan_wing_attachment import ROOT,ART
from grf_reader import GrfFile
from spr_reader import Spr
from sprite_formats import read_act

OUT=ROOT/'Outputs/clan-body-skins/wing-anatomy-v18'
ARCHIVE=Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/spritedata.grf')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    grf=GrfFile(ARCHIVE)
    try:
        matches=[key for key in grf.entries if key.endswith('.spr') and re.search(r'wing|angel|feather|seraph|천사|날개|깃털|엔젤|세라핌|미카엘',key,re.I)]
        (OUT/'archive-wing-paths.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding='utf8')
        groups=Counter('/'.join(k.split('/')[:-1]) for k in matches)
        print('Archive',grf.file_count,'records; wing matches',len(matches))
        print('FOLDERS',json.dumps(groups,ensure_ascii=False))
        # Locate the exact wing source used by the old builder by payload hash.
        old_hash=hashlib.sha256((ART/'production-v02/source/male-wing.spr').read_bytes()).hexdigest()
        exact=[]
        unique={}
        for key in matches:
            data=grf.read(key);sha=hashlib.sha256(data).hexdigest()
            if sha==old_hash:exact.append(key)
            unique.setdefault(sha,key)
        print('Previous reference source:',json.dumps(exact,ensure_ascii=False))
        print('Unique wing SPR payloads',len(unique))
        (OUT/'unique-wing-paths.json').write_text(json.dumps(list(unique.values()),ensure_ascii=False,indent=2),encoding='utf8')
        print('PATHS',json.dumps(list(unique.values()),ensure_ascii=False))
    finally:grf.close()

if __name__=='__main__':main()
