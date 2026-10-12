"""Package the native-style Bestiary button BMPs without changing their pixels."""
from pathlib import Path
from bestiary_paths import BESTIARY_TEXTURE_ROOT
import hashlib,json,struct,zipfile

ROOT=Path(__file__).resolve().parents[1]
STATES=('normal','mouseon','pressed')
README='''Bestiary menu button - 2025-07-16 Ragexe

Renewal UI: 45 x 41 pixels, normal / mouse-on / pressed.
Classic UI: 32 x 34 pixels, normal / mouse-on / pressed.
Renewal uses an illustrated book-and-paw icon with a transparent exterior.
Classic uses the same icon inside the native dark menu frame.

Copy the included data folder into your game directory. The updated BestiaryUI
patch also copies these files automatically when building the client.

Select BestiaryUI and ROGlobalZeroMenu in WARP (with the menu dependencies).
Select Bestiary in Hide Buttons (New UI) to hide it in BOTH themes.
Select Bestiary in Show Buttons (New UI) to show it in BOTH themes.
If both patches select Bestiary, the last applied/edited patch wins.
Removing that patch restores the other selection; removing both restores the
default visible button. Disabling BestiaryUI always disables its menu button.
The updated client patches are required; copying BMPs alone adds no button.

Live validation: Renewal/Classic switching, hover/press/click, close/reopen,
map change and Hide/Show. This archive contains assets only.
'''

def main():
    source=ROOT/'Images/BestiaryUI/menuicon';files={};manifest={'client':'2025-07-16','files':{}}
    for theme,prefix,dimensions in [('renewal','',(45,41)),('classic','old_',(32,34))]:
        for state in STATES:
            name=f'bt_bestiary_{prefix}{state}.bmp';raw=(source/name).read_bytes()
            assert raw[:2]==b'BM' and struct.unpack_from('<ii',raw,18)==dimensions,name
            assert struct.unpack_from('<HI',raw,28)==(24,0),name
            relative=(BESTIARY_TEXTURE_ROOT/'menuicon'/name).as_posix();files[relative]=raw
            manifest['files'][relative]={'theme':theme,'state':state,'width':dimensions[0],'height':dimensions[1],'sha256':hashlib.sha256(raw).hexdigest()}
    files['README.txt']=README.encode('utf-8');files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode('utf-8')
    out=ROOT/'Outputs/Bestiary/bestiary-menu-buttons.zip';out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert all(z.read(name)==raw for name,raw in files.items())
    (out.parent/'bestiary-menu-buttons-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'archive':str(out),'bmp_states':6,'packaging_changes_pixels':False,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))

if __name__=='__main__':main()
