"""Execute the emitted collection-art path and real native UIScrollBar code."""
from pathlib import Path
import argparse,json,struct
import pefile
from PIL import Image
from verify_item_description_native import VM,PIXELS

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
    # One full collection image per slot; the card name/effects use the right column.
    hits=[struct.unpack('<5i',v.u.mem_read(v.state+118064+i*20,20)) for i in range(v.s('hits'))]
    assert len(hits)==1
    gx,gy,gw,gh,row=hits[0];assert gw==476 and gh>=100
    v.s('scroll',gy);v.run('Draw');dy=124
    def pixel(x,y):return v.read32(PIXELS+(y*520+x)*4)&0xffffff
    assert pixel(19,dy+1)==0x010180
    assert pixel(18,dy)!=0xff00ff
    # Partial card visibility is clipped at the body boundary, not hidden wholesale.
    v.s('scroll',gy+10);v.run('Draw');assert pixel(19,124)==0x010a80
    assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    assert bytes(v.u.mem_read(v.scroll_pixels+13*394*4,64))==b'\xcd'*64
    expected={'scroll0up.bmp','scroll0mid.bmp','scroll0down.bmp','scroll0bar_up.bmp','scroll0bar_mid.bmp','scroll0bar_down.bmp'}
    assert expected <= {p.rsplit('\\',1)[-1] for p in v.loaded_paths}
    # Exercise actual native arrow and page input through our parent-message bridge.
    v.s('scroll',50);v.run('Draw');v.run('Down',[500,126]);assert v.s('scroll')==2
    v.run('Up',[500,126]);v.run('Down',[500,516]);assert v.s('scroll')==50
    v.run('Up',[500,516]);v.s('scroll',0);v.run('Draw')
    v.run('Down',[500,140]);assert v.read32(0x131f4e8+0x19c)==v.scrollbar
    v.run('Move',[500,5000]);assert v.s('scroll')==v.s('content')-394
    # Native drag receiver and private storage are released on Original while captured.
    v.run('Message',[int(v.scrollbar),7,(-10000)&0xffffffff,0,0,0]);assert v.s('scroll')==0
    v.run('Message',[0,5,0,0,0,0]);assert v.scroll_destroyed==1
    assert v.read32(0x131f4e8+0x19c)==0 and not v.s('ready')
    report={'passed':True,'checks':['collection art preferred over item icon','one 75x100 collection image per slot, clipped at viewport, exact magenta key',
        'native six-BMP UIScrollBar renderer with bounded surface writes','native arrow, drag and parent-message delta contract',
        'Closing destroys private native control and releases capture'],'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'artwork-verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
