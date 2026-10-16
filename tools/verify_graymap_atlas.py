"""Pixel checks for logical GAT masks through this client's inverted atlas V.

The preview is a CPU sampling regression, not a captured game screenshot.
"""
import argparse,json,math,struct
from pathlib import Path
import pefile
from PIL import Image

WALK=(160,171,181);GRID=(193,204,214)


def load(folder):
    m=json.loads((folder/'manifest.json').read_text())['graymap']
    pe=pefile.PE(str(folder/'graymap.exe'))
    table=pe.get_data(m['style']['uvVir']-pe.OPTIONAL_HEADER.ImageBase,32*16)
    uv=[struct.unpack_from('<4f',table,i*16) for i in range(32)]
    relative=Path('data/texture/graymap/cells.tga')
    path=folder/'release'/relative
    if not path.is_file():path=folder/relative
    logical=Image.open(path).convert('RGB')
    assert logical.size==(512,256)
    uploaded=logical.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return uploaded,uv


def sample(image,uv,x,y):
    u=uv[0]+(uv[2]-uv[0])*x;v=uv[1]+(uv[3]-uv[1])*y
    return image.getpixel((min(image.width-1,max(0,math.floor(u*image.width))),
                           min(image.height-1,max(0,math.floor(v*image.height)))))


def masks(folder):
    image,uv=load(folder)
    for variant in range(32):
        for cell in range(4):
            rgb=sample(image,uv[variant],.25+.5*(cell&1),.25+.5*(cell//2))
            actual=rgb[0]<90;expected=bool((variant&15)&(1<<cell))
            assert actual==expected,dict(variant=variant,cell=cell,rgb=rgb,expected_blocked=expected)
    return image,uv


def verify(folder):
    image,uv=masks(folder)
    # Open floor must not acquire dark holes or a checker motif. Fully blocked
    # tiles must not acquire light squares, even on their former grid borders.
    for variant in (0,16):
        colors={sample(image,uv[variant],x/63,y/63) for y in range(64) for x in range(64)}
        assert colors<=({WALK,GRID} if variant==16 else {WALK}),colors
        assert sample(image,uv[variant],.25,.25)==WALK
    assert sample(image,uv[16],0,.25)==GRID
    for variant in (15,31):
        colors={sample(image,uv[variant],x/63,y/63) for y in range(64) for x in range(64)}
        assert colors<={(43,50,58),(45,52,60)},colors
    return dict(build=str(folder),mask_cell_samples=128,uniform_walkable_floor=True,
                thin_grid=True,continuous_dark_blocked_regions=True,passed=True,live_accepted=False)


def preview(folder,path):
    image,uv=load(folder);width,height=20,14
    walk=lambda x,y:2<=x<18 and 1<=y<13 and not(7<=x<13 and 4<=y<10)
    out=Image.new('RGB',(width*24,height*24))
    for gy in range(0,height,2):
        for gx in range(0,width,2):
            mask=sum((not walk(gx+(i&1),gy+(i//2)))<<i for i in range(4))
            for y in range(48):
                for x in range(48):out.putpixel((gx*24+x,gy*24+y),sample(image,uv[mask+16],x/47,y/47))
    path.parent.mkdir(parents=True,exist_ok=True);out.save(path)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('build',type=Path)
    ap.add_argument('--broken',type=Path);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--preview',type=Path);args=ap.parse_args()
    report=verify(args.build)
    if args.broken:
        try:masks(args.broken)
        except AssertionError as error:report['old_phantom_cells_reproduced']=True;report['old_failure']=str(error)
        else:raise AssertionError('old atlas sampling unexpectedly passed')
    if args.preview:preview(args.build,args.preview)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
