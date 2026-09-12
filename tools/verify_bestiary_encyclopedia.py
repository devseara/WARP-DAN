"""Execute v3 encyclopedia controls with native/transport boundaries mocked."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_bestiary_journal import JournalVM
from verify_bestiary_cache import reply

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary']
    assert m['protocolVersion']==3
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True);checks=[]
    def fresh():
        v=JournalVM(pe,m);v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]));return v
    def click(v,x,y):v.run('down',[x,y]);v.run('up',[x,y])
    v=fresh();click(v,195,39);assert v.state32(208)==1
    for y in [94,125,156,187,218]:v.run('down',[485,y])
    assert len(v.sent)==1 and [v.state32(x) for x in [168,172,176,180,212]]==[0]*5
    click(v,389,265);assert v.state32(208)==0 and len(v.sent)==1
    click(v,195,39)
    for y in [94,125,156,187,218]:v.run('down',[485,y])
    click(v,235,265);assert len(v.sent)==2
    assert struct.unpack_from('<6H',v.sent[-1],64)==(1,1,1,1,1,50)
    v.receive(reply(v.sent[-1]));v.run('sender',[3,0,1002,0]);assert len(v.sent)==2
    v.state32(168,2);v.run('sender',[3,0,1002,0]);assert len(v.sent)==3
    checks.append('Draft filter edits are local; Cancel discards; Apply sends one request; every filter participates in cache identity')
    v=fresh();click(v,309,336);click(v,402,360);assert v.state32(204)==1
    click(v,731,333);assert struct.unpack_from('<H',v.sent[-1],76)[0]==1
    v.receive(reply(v.sent[-1]));click(v,711,333);assert len(v.sent)==2 and v.state32(192)==0
    click(v,488,360);click(v,731,333);assert struct.unpack_from('<H',v.sent[-1],104)[0]==1
    v.receive(reply(v.sent[-1]));click(v,397,336);click(v,731,333)
    assert struct.unpack_from('<H',v.sent[-1],78)[0]==1
    v.receive(reply(v.sent[-1]));click(v,40,174)
    assert struct.unpack_from('<HH',v.sent[-1],76)==(0,0) and struct.unpack_from('<H',v.sent[-1],104)[0]==0
    checks.append('Skill, summon and lore pages use isolated cache keys and reset on monster selection')
    v=fresh();click(v,708,119)
    assert v.sent[-1][80:104]==b'prt_fild08\0'.ljust(24,b'\0')
    v.receive(reply(v.sent[-1]));click(v,708,176)
    assert v.sent[-1][80:104]==b'prt_fild05\0'.ljust(24,b'\0')
    checks.append('Each Navigate request carries the exact displayed map identity')
    v=fresh();v.run('wheel',[120]);assert len(v.sent)==1
    v.run('wheel',[-120]);assert len(v.sent)==2 and struct.unpack_from('<H',v.sent[-1],24)[0]==1
    v.run('wheel',[-120]);assert len(v.sent)==2
    v.receive(reply(v.sent[-1]));v.state32(4,1);v.run('wheel',[-120]);assert len(v.sent)==2
    checks.append('Wheel paging is bounded, disabled during pending requests, and confined to Monsters')
    v=fresh();v.state32(208,1);v.run('message',[0,5,0,0,0,0]);assert v.state32(208)==0 and v.u.mem_read(v.window+0x28,1)==b'\1'
    v.state32(124,1);v.run('message',[0,5,0,0,0,0]);assert v.state32(124)==0
    v.state32(116,0x60000a00);v.focus=0x60000a00;v.capture=v.window;v.state32(152,1)
    v.run('message',[0,5,0,0,0,0]);assert v.focus==0 and v.capture==0 and v.state32(152)==0 and v.u.mem_read(v.window+0x28,1)==b'\0'
    v.stub(0x8841D0,24,lambda ecx,a:57);v.run('message',[0,99,1,2,3,4]);assert any(addr==0x8841D0 for addr,_,_ in v.calls)
    checks.append('Stock Escape message dismisses popups before closing; focus/capture release and unrelated messages preserve native ownership')
    v=fresh();description=v.alloc(220);table=v.alloc(220);v.write32(description,table);v.write32(table+0x94,0x60000d00)
    constructed=[];destroyed=[];observed=[]
    def ctor(ecx,args):v.u.mem_write(ecx,b'\0'*248);constructed.append(ecx);return ecx
    def identity(ecx,args):v.write32(ecx+0x2c,args[0])
    def opened(ecx,args):
        observed.append((ecx,args, v.read32(args[2]),v.read32(args[2]+8),v.read32(args[2]+0x2c),bytes(v.u.mem_read(args[2]+0x5c,1))))
    v.stub(0x6A1B20,0,ctor);v.stub(0x6A6570,4,identity);v.stub(0xA39340,4,lambda ecx,args:description if args==[12] else 0)
    v.stub(0x60000d00,24,opened);v.stub(0x4F08F0,0,lambda ecx,args:destroyed.append(ecx))
    v.run('itemDetail',[1201,5,2]);base=constructed[-1]
    assert observed[-1]==(description,[0,24,base,0,0,0],5,2,1201,b'\1')
    assert destroyed==[base+0x44,base+0x2c] and len(v.sent)==1
    v.stub(0xA39340,4,lambda ecx,args:0);v.run('itemDetail',[909,3,0]);assert len(destroyed)==4 and len(observed)==1
    before=len(constructed);v.run('itemDetail',[0,0,0]);assert len(constructed)==before
    checks.append('Native descriptions construct an identified CItem, forward the numeric ID/type/equip mask and release both strings even when the window factory fails')
    v=fresh();recorded=[];v.stub(m['itemDetail']['vir'],12,lambda ecx,args:recorded.append(args))
    v.write32(m['payload']['vir']+1352,5<<24);v.write32(m['payload']['vir']+3432,2)
    click(v,250,378);assert recorded==[[909,5,2]] and len(v.sent)==1
    v.state32(140,1);click(v,250,378);assert len(recorded)==1
    checks.append('Only populated drop cards on Drops open native descriptions; clicking them emits no server request')
    # Every new fixed-width field is defensively terminated by the receiver.
    v=fresh();v.run('sender',[6,0,1002,0]);raw=bytearray(reply(v.sent[-1]))
    fields=[(3464,48),(3512,64),(3576,40),(4112,40),(4152,40),(4288,112),(4736,64),(4808,48),(4856,24)]
    for off,size in fields:raw[off:off+size]=b'X'*size
    v.receive(bytes(raw))
    for off,size in fields:assert v.u.mem_read(m['payload']['vir']+off+size-1,1)==b'\0'
    checks.append('Extended skill, habitat, lore/source and summon strings are terminated before native rendering')
    report={'passed':True,'checks':checks,'native_and_network_boundaries_mocked':True,'live_accepted':False}
    (directory/'encyclopedia-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
