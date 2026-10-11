"""Additional emitted-code tests for long layouts, capture and item invalidation."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_item_description_native import VM,WIN,PIXELS,HITS
BODY_TOP=154
def long_response(v,rows=64):
    data=v.response();data[128:]=bytes(len(data)-128);struct.pack_into('<H',data,38,rows)
    for i in range(rows):
        off=128+i*192;struct.pack_into('<HH',data,off,3,1);value=('Long effect '+str(i)+' with a correctly bounded visible line. '*2).encode();data[off+64:off+64+len(value)]=value
    return data
def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    fresh=lambda:VM(pe,m);checks=[]
    v=fresh();v.open(scope=0,index=7);assert not v.sent and not v.s('ready') and v.u.mem_read(v.child+0x28,1)==b'\1'
    checks.append('Unprofiled indexed containers retain the complete native view instead of claiming inventory or catalog ownership')
    v=fresh();v.open();first=v.response();v.open(index=8,refine=9);assert v.receive(first)==0
    checks.append('Two customized copies of the same item ID cannot exchange responses')
    v=fresh();v.open();data=v.response();struct.pack_into('<Q',data,52,0x1122334455667788);v.receive(data);v.run('Draw')
    v.open();assert struct.unpack_from('<Q',v.sent[-1],76)[0]==0x1122334455667788 and not v.s('loading')
    assert v.receive(v.response())==1 and v.s('ready')
    checks.append('Reopening carries the accepted server fingerprint and remains valid through the native identity comparison')
    v=fresh();v.open();data=v.response();v.receive(data);sent=len(v.sent);struct.pack_into('<I',data,20,2);struct.pack_into('<H',data,38,0)
    v.now+=200;assert v.receive(data)==1 and v.s('ready') and v.s('loading') and len(v.sent)==sent+1
    assert v.u.mem_read(v.child+0x28,1)==b'\0' and v.receive(data)==0
    checks.append('Unsolicited stale-item notice reinspects in place behind the skeleton and cannot reactivate the old snapshot')
    v=fresh();v.open();assert v.receive(long_response(v))==1;v.run('Draw');assert v.s('content')>560 and v.s('lines')<=512
    v.run('Wheel',[-120]);assert v.s('scroll')==48;v.run('Wheel',[120]);assert v.s('scroll')==0
    sx=v.read32(WIN+0x14)-27+7
    v.run('Down',[sx,BODY_TOP+16]);assert v.read32(0x131f4e8+0x19c)==v.scrollbar
    v.run('Move',[sx,3000]);assert v.s('scroll')==v.s('content')-(560-166)
    v.run('Up',[sx,3000]);assert not v.read32(0x131f4e8+0x19c)
    v.run('Draw');assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    v.write32(0x131f4e8+0x19c,0x50107000);v.run('Down',[sx,BODY_TOP+56]);v.run('Up',[sx,BODY_TOP+56]);assert v.read32(0x131f4e8+0x19c)==0x50107000
    checks.append('64-row layout scrolls, thumb dragging clamps at both edges, and capture ownership survives outside release/foreign capture')
    v=fresh();v.open();v.receive(v.response());v.run('Draw')
    x,y,w,h,row=struct.unpack('<iiiii',v.u.mem_read(v.state+HITS,20));assert w==v.read32(WIN+0x14)-48 and h>=70
    calls=[];v.stub(0xa39340,4,lambda ecx,args:calls.append(('factory',args)) or 0)
    v.run('Right',[x+3,BODY_TOP+y+3-v.s('scroll')]);assert not calls
    v.write32(0x159c088,0x50109000);v.stub(0xa7e780,4,lambda ecx,args:0x50109400)
    v.stub(0x4f08f0,0,lambda ecx,args:calls.append(('destroy',ecx)) or 0)
    v.run('Right',[x+3,BODY_TOP+y+3-v.s('scroll')]);assert [x[0]for x in calls]==['factory','destroy','destroy']
    assert calls[0][1]==[82] and calls[1][1]-calls[2][1]==0x18
    checks.append('Card hit opens a real known component, missing catalog IDs are blocked, and native strings are released when factory creation fails')
    v=fresh();v.write32(v.renderer+0x28,320);v.write32(v.renderer+0x2c,300);v.open();v.receive(v.response());v.run('Draw')
    assert v.read32(WIN+0x14)==288 and v.read32(WIN+0x18)==268
    assert all(x>=0 and y>=0 and x<288 and y<268 for x,y,_,_,_ in v.draws)
    assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
    checks.append('Small viewport body stays within its allocated surface and all visible text origins remain in bounds')
    result={'passed':True,'checks':checks,'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'edge-verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);print(json.dumps(verify(p.parse_args().directory),indent=2))
