"""Pixel checks against original RO BMPs for the white body and native footer."""
from pathlib import Path
import argparse,json,struct
import pefile
from PIL import Image
from verify_item_description_native import VM,WIN,ITEM,PIXELS
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'tools/fixtures/item_description/assets'

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    def fresh(grade=0):
        v=VM(pe,m);v.open()
        if grade:
            v.u.mem_write(ITEM+0x88,struct.pack('<H',grade));v.s('origin',1);v.run('Message',[0,24,ITEM,0,0,0]);v.s('origin',0)
        assert v.receive(v.response())==1
        return v
    def pixel(v,x,y):return v.read32(PIXELS+(y*v.read32(WIN+0x14)+x)*4)&0xffffff
    def match(v,name,x,y,w=None,h=None,phase_y=0):
        im=Image.open(ASSETS/name).convert('RGB');w=w or im.width;h=h or im.height
        for dy in range(h):
            for dx in range(w):
                r,g,b=im.getpixel((dx%im.width,(dy+phase_y)%im.height));expected=r<<16|g<<8|b
                if expected==0xff00ff:continue
                assert pixel(v,x+dx,y+dy)==expected,(name,x+dx,y+dy,hex(pixel(v,x+dx,y+dy)),hex(expected))
    v=fresh();v.run('Draw')
    for point in [(470,155),(300,535),(300,525),(300,542)]:assert pixel(v,*point)==0xffffff,point
    match(v,'sysbox_lm.bmp',0,116,14,420,102);match(v,'sysbox_rm.bmp',506,116,14,420,102)
    match(v,'sysbox_ld.bmp',0,546);match(v,'sysbox_md.bmp',14,546,492,14);match(v,'sysbox_rd.bmp',506,546)
    assert pixel(v,0,559)==0xff00ff,'rounded corner lost its native color key'
    assert any(p.endswith('sysbox_bg.bmp') for p in v.loaded_paths)
    # Original button caps + repeating middle, including hover/pressed states.
    for mode,action in [('out',None),('over','Move'),('press','Down')]:
        if action:v.run(action,[20,530])
        v.run('Draw')
        for suffix,x,w in [('left',14,6),('mid',20,54),('right',74,6)]:match(v,Path('basic_interface')/f'btn_{mode}_{suffix}.bmp',x,524,w,20)
    assert v.s('pressed')==1;v.run('Up',[20,530]);assert not v.s('ready'),'hit box missed the moved native button'
    g=fresh(4);g.run('Draw')
    for suffix,x,y,w,h in [('lm',0,116,14,420),('rm',506,116,14,420),('ld',0,546,14,14),('md',14,546,492,14),('rd',506,546,14,14)]:
        match(g,f'sysbox_g4_{suffix}.bmp',x,y,w,h,102 if suffix in ['lm','rm'] else 0)
    assert pixel(g,300,535)==0xffffff
    # Small viewport and nonuniform replacement skins still tile in the native phase.
    t=fresh();t.write32(t.renderer+0x28,320);t.write32(t.renderer+0x2c,300)
    t.s('origin',1);t.run('Message',[0,24,ITEM,0,0,0]);t.s('origin',0);assert t.receive(t.response())==1
    im=Image.new('RGBA',(14,14))
    for y in range(14):
        for x in range(14):im.putpixel((x,y),(230+x,230+y,240,255))
    t.add_texture('유저인터페이스\\sysbox_bg.bmp',im);t.run('Draw')
    x,y=220,225;r,gc,b,_=im.getpixel(((x-14)%14,(y-14)%14));assert pixel(t,x,y)==r<<16|gc<<8|b
    for v in [g,t]:assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    preview=fresh();preview.render(directory/'native-body-preview.png')
    report={'passed':True,'checks':['body and footer use pure-white stock sysbox_bg.bmp',
        'native side/bottom slices match source BMP pixels and preserve rounded keyed corners',
        'grade frame pieces match the native header grade',
        'native button idle/hover/pressed assets and relocated hit areas agree',
        'small-window pattern tiling and surface bounds'], 'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'skin-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
