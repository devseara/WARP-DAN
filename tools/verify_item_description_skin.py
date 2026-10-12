"""Pixel checks for the grade-tinted card frame, info strip and loading skeleton."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_item_description_native import VM,WIN,ITEM,PIXELS
ROOT=Path(__file__).resolve().parents[1]
# Must match item_description.cpp tint_top/tint_bottom (native grade_icon inks).
TINT_TOP=[0x6E98D6,0xD8605D,0xE3963F,0x5C9E4A,0x7F73A6];TINT_BOTTOM=[0x9ABAE8,0xEE9179,0xF1BC78,0x8EC47A,0xA99FCB]
def mix(a,b,n,total):
    out=0;total=max(1,total)
    for shift in (0,8,16):
        c,d=(a>>shift)&255,(b>>shift)&255;num=(d-c)*n
        out|=(c+(abs(num)//total)*(1 if num>=0 else -1))<<shift
    return out
def edge(grade):top=TINT_TOP[grade];return mix(top,mix(top,0,1,5),1,2)

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    def fresh(grade=0,respond=True):
        v=VM(pe,m);v.open()
        if grade:
            v.u.mem_write(ITEM+0x88,struct.pack('<H',grade));v.now+=200;v.s('origin',1);v.run('Message',[0,24,ITEM,0,0,0]);v.s('origin',0)
        if respond:assert v.receive(v.response())==1
        return v
    def pixel(v,x,y):return v.read32(PIXELS+(y*v.read32(WIN+0x14)+x)*4)&0xffffff
    v=fresh();v.run('Draw');W,H=v.read32(WIN+0x14),v.read32(WIN+0x18);assert (W,H)==(360,560)
    for point in [(0,0),(W-1,0),(0,H-1),(W-1,H-1)]:assert pixel(v,*point)==0xff00ff,('rounded corner lost its color key',point)
    for point in [(0,300),(W-1,300),(180,H-1)]:assert pixel(v,*point)==edge(0),point
    for point in [(1,300),(W-5,300),(180,H-6)]:assert pixel(v,*point)==0xffffff,point
    assert pixel(v,200,2)==mix(TINT_TOP[0],TINT_BOTTOM[0],1,114),'header gradient row'
    assert pixel(v,100,146)==0xe3e8f0,'info strip divider'
    assert not any('sysbox' in p or 'btn_' in p for p in v.loaded_paths),'card frame uses no stock frame or footer BMPs'
    g=fresh(4);g.run('Draw')
    assert pixel(g,200,2)==mix(TINT_TOP[4],TINT_BOTTOM[4],1,114) and pixel(g,0,300)==edge(4),'grade tint follows the native item grade'
    assert any('grade_icon4.bmp' in p for p in g.loaded_paths),'grade badge resolves the native grade icon'
    s=fresh(respond=False);s.draws=[];s.run('Draw')
    assert pixel(s,40,160)==0xdde6f5 and pixel(s,40,184)==0xedf1f7,'loading skeleton'
    assert not s.draws,'skeleton paints no stale or stock text'
    t=VM(pe,m);t.write32(t.renderer+0x28,320);t.write32(t.renderer+0x2c,300);t.open();assert t.receive(t.response())==1;t.run('Draw')
    assert (t.read32(WIN+0x14),t.read32(WIN+0x18))==(288,268) and pixel(t,0,267)==0xff00ff
    for v in [g,s,t]:assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    preview=fresh();preview.render(directory/'native-body-preview.png')
    report={'passed':True,'checks':['rounded card keeps keyed corners, a 1px grade-tone edge and a pure-white body',
        'header gradient and edge follow the native item grade; grade badge uses the native grade icon',
        'no stock sysbox frame or footer button BMPs are loaded','loading skeleton paints no text',
        'small-window geometry and surface bounds'],'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'skin-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
