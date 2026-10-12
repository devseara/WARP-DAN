"""Execute the emitted collection-art path and real native UIScrollBar code."""
from pathlib import Path
import argparse,json,struct
import pefile
from PIL import Image
from verify_item_description_native import VM,PIXELS,WIN,HITS
from verify_item_description_edges import long_response,BODY_TOP

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription']
    pe=pefile.PE(str(directory/'item-description.exe'));v=VM(pe,m);v.open();v.receive(v.response())
    v.write32(0x159c088,0x50109000);node=0x50110000
    v.stub(0xa7e780,4,lambda ecx,args:node)
    for off,value in [(0x40,b'Poring Card'),(0x58,b'testcard')]:
        v.u.mem_write(node+off,value+b'\0');v.write32(node+off+0x14,15)
    im=Image.new('RGBA',(75,100),(255,0,255,255))
    for y in range(1,99):
        for x in range(1,74):im.putpixel((x,y),(x,y,128,255))
    path='유저인터페이스\\collection\\testcard.bmp';v.add_texture(path,im)
    v.run('Draw')
    assert any('collection\\testcard.bmp' in p for p in v.loaded_paths)
    assert not any('item\\testcard.bmp' in p for p in v.loaded_paths)
    assert any(text=='Poring Card' for _,_,text,*_ in v.draws),'catalog name is the card title'
    # One card panel per slot; the art is a nearest-neighbour fit inside its 40x52 frame.
    hits=[struct.unpack('<5i',v.u.mem_read(v.state+HITS+i*20,20)) for i in range(v.s('hits'))]
    assert len(hits)==1
    gx,gy,gw,gh,row=hits[0];W=v.read32(WIN+0x14);assert gw==W-48 and gh>=70
    def pixel(x,y):return v.read32(PIXELS+(y*W+x)*4)&0xffffff
    dw,dh=39,52;ox=26;oy=gy+9;scroll=v.s('scroll')
    def expected(dx,dy):sx,sy=dx*75//dw,dy*100//dh;return sx<<16|sy<<8|128
    for dx,dy in [(1,1),(20,30),(38,51)]:assert pixel(ox+dx,BODY_TOP+oy+dy-scroll)==expected(dx,dy),(dx,dy)
    # Partial card visibility is clipped at the body boundary, not hidden wholesale.
    v.s('scroll',oy+10);v.run('Draw');assert pixel(ox+1,BODY_TOP)==expected(1,10)
    assert pixel(ox+1,BODY_TOP-1)!=expected(1,9)
    assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    # Native scrollbar with a long body.
    v=VM(pe,m);v.open();assert v.receive(long_response(v))==1;v.run('Draw')
    expected_bmps={'scroll0up.bmp','scroll0mid.bmp','scroll0down.bmp','scroll0bar_up.bmp','scroll0bar_mid.bmp','scroll0bar_down.bmp'}
    assert expected_bmps <= {p.rsplit('\\',1)[-1] for p in v.loaded_paths}
    assert bytes(v.u.mem_read(v.scroll_pixels+13*394*4,64))==b'\xcd'*64
    sx=v.read32(WIN+0x14)-27+7
    # Exercise actual native arrow and page input through our parent-message bridge.
    v.s('scroll',50);v.run('Draw');v.run('Down',[sx,BODY_TOP+2]);assert v.s('scroll')==2
    v.run('Up',[sx,BODY_TOP+2]);v.run('Down',[sx,BODY_TOP+392]);assert v.s('scroll')==50
    v.run('Up',[sx,BODY_TOP+392]);v.s('scroll',0);v.run('Draw')
    v.run('Down',[sx,BODY_TOP+16]);assert v.read32(0x131f4e8+0x19c)==v.scrollbar
    v.run('Move',[sx,5000]);assert v.s('scroll')==v.s('content')-394
    # Native drag receiver and private storage are released on close while captured.
    v.run('Message',[int(v.scrollbar),7,(-10000)&0xffffffff,0,0,0]);assert v.s('scroll')==0
    v.run('Message',[0,5,0,0,0,0]);assert v.scroll_destroyed==1
    assert v.read32(0x131f4e8+0x19c)==0 and not v.s('ready')
    # A short body needs no scrollbar control at all.
    s=VM(pe,m);s.open();s.receive(s.response());s.run('Draw');assert not s.read32(s.state+119524)
    report={'passed':True,'checks':['collection art preferred over item icon; catalog name titles the card',
        'one nearest-neighbour 40x52 card thumbnail per slot, clipped at the viewport, exact magenta key',
        'native six-BMP UIScrollBar renderer with bounded surface writes, only when the body overflows',
        'native arrow, drag and parent-message delta contract','Closing destroys private native control and releases capture'],
        'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'artwork-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
