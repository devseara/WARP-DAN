"""Render original generic dual ACT/SPR over the live actor's body resources.

Run with bundled Pillow Python plus the repository site-packages. Geometry
executes the PE's C40C20. CPU sampling/order is explicit; this is not a GPU
screenshot, and weapon/body occlusion must still be checked in the game.
"""
from __future__ import annotations
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'.venv/Lib/site-packages'))
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw,ImageFont
from verify_dual_weapon_pixel_grips import GripResources,GripMachine,CLIENT
from verify_dual_weapon_native_projection import NativeProjector
from verify_dual_weapon_native_basis import invoke_native
from verify_dual_weapon_compositor import PAIR_NAMES
from dual_weapon_formats.spr_reader import Spr

OUT=ROOT/'Outputs/dual_weapon_native_overlay'
PAYLOAD=ROOT/'Outputs/dual_weapon_grip_placement/compositor.dwcp'
EXE=CLIENT/'2025-07-16_Ragexe_175220998_clientinfo_patched.exe'

def paint(canvas,im,g,scale=3,origin=(60,85)):
    top,left,bottom,right,degrees=g;w,h=im.size
    angle=math.radians(degrees);c,s=math.cos(angle),math.sin(angle)
    cx,cy=(left+right)/2,(top+bottom)/2
    wx,wy=w/(right-left),h/(bottom-top)
    # Output board pixels -> actor-local coordinates -> inverse packet quad.
    tx,ty=400-origin[0]-cx,300-origin[1]-cy
    coeff=(c*wx/scale,s*wx/scale,w/2+wx*(c*tx+s*ty),
           -s*wy/scale,c*wy/scale,h/2+wy*(-s*tx+c*ty))
    layer=im.transform(canvas.size,Image.Transform.AFFINE,coeff,resample=Image.Resampling.NEAREST)
    canvas.alpha_composite(layer)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    resources=GripResources(CLIENT);machine=GripMachine(resources,PAYLOAD);proj=NativeProjector(EXE)
    ann=json.loads((ROOT/'Inputs/DualWeaponAuthored/grips/female-assassin-pixel-landmarks.json').read_text(encoding='utf-8'))
    cache={};records=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    coverage=json.loads((ROOT/'docs/evidence/dual-weapon-type-coverage.json').read_text(encoding='utf-8'))
    declared={r['view']:r for r in coverage['views'] if str(r['view']) in ann['weapon_pixels']}
    weapons={v:machine.load(r['resource_stem']) for v,r in declared.items()}
    def image_for(resource,kind,index):
        key=resource['name'],kind,index
        if key not in cache:
            spr=Spr(resources.read(resource['name']+'.spr'));rgba,w,h=spr.get_rgba(index,kind)
            cache[key]=Image.frombytes('RGBA',(w,h),rgba)
        return cache[key]
    def native(resource,action,frame):
        cell=resource['layers'].get((action,frame))
        if not cell:return None
        l=machine.native_layer(resource,action,frame);im=resource['images'].get((l[8],l[2]))
        if not im:return None
        p=proj.project(l,(im[1].width,im[1].height,0,0),origin=(400,300))
        return [*p[:4],p[7]],image_for(resource,l[8],l[2]),l
    def board(pair,phase,d,f,candidate=False,markers=False,mv=34,ov=45):
        action=(32 if phase==0 else 88)+d
        stock,trail=machine.equip_views(weapons[mv],weapons[ov],declared[mv]['base_type'],declared[ov]['base_type'],mv,ov,PAIR_NAMES[pair])
        canvas=Image.new('RGBA',(360,330),(223,234,238,255))
        body=native(machine.body,action,f);assert body
        paint(canvas,body[1],body[0])
        if candidate:
            for ch,res in [(5,stock),(6,trail)]:
                result=invoke_native(machine,proj,res,action,f,1.,ch)
                if not result:continue
                assert result['handled']==1
                for draw in result['draws']:
                    r=next(r for r in machine.loaded.values() if r['name']==draw['resource'])
                    g=draw['geometry'];g=[g[0]-195,g[1]-560,g[2]-195,g[3]-560,g[4]]
                    paint(canvas,image_for(r,*draw['image']),g)
        else:
            for res in (stock,trail):
                result=native(res,action,f)
                if result:
                    paint(canvas,result[1],result[0])
                    records.append(dict(pair=pair,action=action,frame=f,resource=res['name'],layer=list(result[2]),geometry=result[0]))
        if markers:
            # Native body-projected annotations, shown separately from the
            # weapon comparison rather than inferred from either render.
            from verify_dual_weapon_pixel_grips import point
            l=body[2];dims=body[1].size
            for role,p in enumerate(ann['body_pixels'][str(l[2])]):
                x,y=point(body[0],dims,p);x=(x-400+60)*3;y=(y-300+85)*3
                ImageDraw.Draw(canvas).ellipse((x-3,y-3,x+3,y+3),outline=('red','blue')[role],width=1)
        return canvas
    for pair in PAIR_NAMES:
        sheet=Image.new('RGB',(1440,720),(240,243,245));pen=ImageDraw.Draw(sheet)
        for d in range(8):
            x,y=(d%4)*360,(d//4)*360
            sheet.paste(board(pair,0,d,0), (x,y+25))
            pen.text((x+6,y+5),f'STOCK pair {pair} held D{d} F0',font=font,fill='black')
        sheet.save(OUT/f'stock-pair{pair}-all-directions.png')
    for phase,count in [(0,6),(1,8)]:
        for d in (0,2,4,6):
            # Rows are animation frames; columns compare exact generic art
            # and the candidate's two original item resources.
            for page in range(2):
                sheet=Image.new('RGB',(1440,740),(240,243,245));pen=ImageDraw.Draw(sheet)
                for slot,f in enumerate(range(page*4,min(count,page*4+4))):
                    for candidate in (False,True):
                        x=(slot%2)*720+int(candidate)*360;y=(slot//2)*370
                        sheet.paste(board(28,phase,d,f,candidate), (x,y+25))
                        label='candidate main Zeny / off Blue' if candidate else 'STOCK generic dagger/sword'
                        pen.text((x+5,y+5),f'P{phase} D{d} F{f} {label}',font=font,fill='black')
                sheet.save(OUT/f'compare-p{phase}-d{d}-page{page}.png')
            gif=[]
            for f in range(count):
                im=Image.new('RGB',(720,360),(240,243,245));p=ImageDraw.Draw(im)
                im.paste(board(28,phase,d,f), (0,25));im.paste(board(28,phase,d,f,True),(360,25))
                p.text((5,5),'Stock generic dual',font=font,fill='black')
                p.text((365,5),'Candidate: main Zeny / off Blue',font=font,fill='black');gif.append(im)
            gif[0].save(OUT/f'compare-p{phase}-d{d}.gif',save_all=True,append_images=gif[1:],duration=150,loop=0)
    for view in weapons:
        for phase,count in [(0,6),(1,8)]:
            for role in (0,1):
                mv,ov=(view,34 if view!=34 else 45) if role==0 else (45 if view!=45 else 34,view)
                frames=[]
                for f in range(count):
                    sheet=Image.new('RGB',(1440,360),(240,243,245));pen=ImageDraw.Draw(sheet)
                    for col,d in enumerate((0,2,4,6)):
                        sheet.paste(board(28,phase,d,f,True,mv=mv,ov=ov),(col*360,25))
                        pen.text((col*360+5,5),f'view{view} slot{role} P{phase} D{d} F{f}',font=font,fill='black')
                    frames.append(sheet)
                frames[0].save(OUT/f'view{view}-slot{role}-phase{phase}.gif',save_all=True,append_images=frames[1:],duration=150,loop=0)
                frames[0].save(OUT/f'view{view}-slot{role}-phase{phase}-f0.png')
    html=['<!doctype html><meta charset="utf-8"><title>Dual weapon native overlay review</title>',
          '<style>body{font:16px system-ui;background:#17212b;color:#f0f4f8;margin:28px}img{max-width:100%}details{margin:18px 0}summary{cursor:pointer}a{color:#82cfff}</style>',
          '<h1>Native generic dual overlay and original weapon grip review</h1>',
          '<p>Exact active SPR pixels. Geometry executes native C40C20 and candidate x86. CPU sampling; body first, weapons afterward. Head omitted. This does not simulate native depth or certify live acceptance.</p>',
          '<p>Main/right and off/left refer to the character. Adjacent direction pairs share body pixels. Drake weapons are excluded.</p>']
    for pair in PAIR_NAMES:html.append(f'<details><summary>Stock generic pair {pair}, all directions</summary><img src="stock-pair{pair}-all-directions.png"></details>')
    for d in (0,2,4,6):
        html.append(f'<details open><summary>Stock vs candidate, direction {d}</summary><img src="compare-p0-d{d}.gif"><img src="compare-p1-d{d}.gif"></details>')
    for v in weapons:
        html.append(f'<details><summary>View {v}: both equipment slots, held and attack</summary>')
        for role in (0,1):
            for phase in (0,1):html.append(f'<p>Slot {role}, phase {phase}</p><img loading="lazy" src="view{v}-slot{role}-phase{phase}.gif">')
        html.append('</details>')
    (OUT/'review.html').write_text('\n'.join(html),encoding='utf-8')
    result=dict(schema='dual_weapon_native_generic_overlay/v1',exe_sha256=proj.sha256,
        compositor_sha256=hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),generic_cells=records,
        weapon_sources=resources.evidence,body_sources=resources.corpus.sources,
        limits=['Geometry executes unmodified C40C20. Rasterization is CPU nearest-neighbor, not the GPU.',
                'Body is drawn first, weapon layers afterward; native per-pixel depth/occlusion is not simulated.',
                'Head is intentionally omitted to expose the arm/body reference.',
                'Candidate textures come from emitted x86 draw packets. No image resource is fabricated.'])
    (OUT/'native-overlay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(native_generic_layer_records=len(records),output=str(OUT))))

if __name__=='__main__':main()
