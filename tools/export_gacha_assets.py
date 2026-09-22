"""Export code-native Gacha widget skins, excluding changeable item artwork.

No AI redesign: deterministic export of the native rectangle compositor.
Existing output artwork is never overwritten. Runtime captions stay dynamic.
"""
import argparse
import re
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--zeny-source',type=Path,help='Original marketui/itembox_00.png, copied unchanged as zeny.png')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=(Path(__file__).resolve().parents[1]/'Scripts/Patches/GachaUI.qjs').read_text(encoding='utf8')
    controls=re.findall(r'\{id:(\d+),x:[^,]+,y:[^,]+,w:(\d+),h:(\d+),label:"([^"]+)"',source)
    def save(image,name):
        target=args.output/name
        if not target.exists():image.save(target)
    colors={'out':0xDEEFFB,'over':0xEFFAFF,'press':0xB9D7F0,'off':0xF3F5F7}
    def skin(w,h,color,border=0xD4DFE9):
        image=Image.new('RGBA',(w,h));d=ImageDraw.Draw(image)
        rgb=lambda v:((v>>16)&255,(v>>8)&255,v&255,255)
        for x,y,r,b,c in [(2,0,w-3,h-1,border),(0,2,w-1,h-3,border),(1,3,w-2,h-4,color),(3,1,w-4,h-2,color)]:d.rectangle((x,y,r,b),fill=rgb(c))
        return image
    for id_,w,h,label in controls:
        for state,color in colors.items():save(skin(int(w),int(h),color),f'button_{id_}_{state}.png')
    for key,w in [('zeny',136),('ticket',104)]:
        for state in ('out','selected','off'):
            selected=state=='selected'
            im=skin(w,24,0xFFF3D5 if selected else 0xFFFFFF,0xD0A03C if selected else 0xD4DFE9)
            if selected:ImageDraw.Draw(im).rectangle((2,2,4,21),fill=(208,160,60,255))
            save(im,f'currency_{key}_{state}.png')
    star=Image.new('RGBA',(9,9));d=ImageDraw.Draw(star)
    for y,x,w in [(0,4,1),(1,3,3),(2,3,3),(3,0,9),(4,1,7),(5,2,5),(6,2,5),(7,1,3),(7,5,3),(8,1,2),(8,6,2)]:d.rectangle((x,y,x+w-1,y),fill=(230,182,71,255))
    save(star,'rarity_star.png')
    # UI caller renders the blue-Z region of the supplied original bar.
    # Never export item resources: the native client resolves those dynamically.
    original=args.zeny_source
    if original is not None and not (args.output/'zeny.png').exists():shutil.copy2(original,args.output/'zeny.png')
    print(f'Exported {len(controls)*4} button skins, six currency skins, rarity star and Zeny bitmap into {args.output}')
if __name__=='__main__':main()
