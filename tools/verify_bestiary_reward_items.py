"""Execute native reward hit testing, localized names and information clicks."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_bestiary_journal import JournalVM
from verify_bestiary_rewards_ui import preview
from verify_bestiary_cache import reply
from verify_bestiary_research_native import personal

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary'];assert m['layoutVersion']>=11
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True);ps=m['personalState']['vir'];rs=m['rewardSearchState']['vir'];rp=m['rewardPointer']['vir'];pp=m['personalPayload']['vir'];checks=[]
    def click(v,x,y):v.run('down',[x,y]);v.run('up',[x,y])
    def fresh():
        v=JournalVM(pe,m);v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]));v.receive(personal(v.read32(ps)));click(v,712,40)
        data=bytearray(preview(v.read32(ps)))
        for i in range(6):
            struct.pack_into('<H',data,2176+i*44,5)
            for j in range(5):struct.pack_into('<II',data,2180+i*44+j*8,501+i*5+j,j+1)
        v.receive(bytes(data));return v
    def names(v,missing=False):
        manager=v.alloc(64);v.write32(0x159C088,manager);records={};expected={}
        for id_ in range(501,531):
            node=v.alloc(160);name=(b'Red Potion' if id_==501 else ('Localized item '+str(id_)+' long display name').encode());expected[id_]=name
            if missing:name=b''
            if len(name)<16:v.u.mem_write(node+0x40,name+b'\0');v.write32(node+0x54,15)
            else:v.write32(node+0x40,v.string(name));v.write32(node+0x54,len(name))
            v.write32(node+0x50,len(name));records[id_]=node
        def lookup(ecx,args):assert ecx==manager+8;return records.get(v.read32(args[0]),0)
        v.stub(0xA7E780,4,lookup);return expected
    v=fresh();expected=names(v)
    for id_ in range(501,531):assert v.cstring(v.run('rewardItemName',[id_]))==expected[id_]
    v.write32(0x159C088,0);assert v.run('rewardItemName',[501])==0
    checks.append('Native itemInfo identified names resolve correctly for short/heap strings, with null-manager handling')
    v=fresh();expected=names(v);tip=v.alloc(80);v.write32(0x121333C,tip);shown=[]
    def coordinates(ecx,args):
        assert ecx==v.window
        v.write32(args[0],v.read32(args[0])+100);v.write32(args[1],v.read32(args[1])+200)
    v.stub(0xA1EF70,8,coordinates);v.stub(0xA753D0,24,lambda ecx,a:shown.append((ecx,v.cstring(a[0]),a[1:])))
    v.stub(0xA23470,8);opened=[];v.stub(m['rewardItemDetail']['vir'],12,lambda ecx,a:opened.append(a))
    sent=len(v.personal_sent)
    for i in range(6):
        for j in range(5):
            x=30+(i%2)*365+j*66;y=179+(i//2)*82;id_=501+i*5+j
            assert v.run('rewardItemHit',[x,y])==id_
            assert v.run('rewardItemHit',[x+23,y+23])==id_
            assert v.run('rewardItemHit',[x+24,y])==0
            v.run('move',[x+4,y+4]);assert shown[-1]==(tip,expected[id_],[x+114,y+180,0xffffffff,0,1])
            v.run('rightDown',[x+4,y+4]);v.run('rightUp',[x+4,y+4]);assert opened[-1]==[id_,0,0]
    assert len(opened)==30 and len(shown)==30 and len(v.personal_sent)==sent
    click(v,34,183);assert len(v.personal_sent)==sent
    click(v,40,174);assert len(v.personal_sent)==sent+1 and struct.unpack_from('<H',v.personal_sent[-1],26)[0]==1
    checks.append('All 30 icon slots show localized native tooltips and open their own ItemId; inspection sends no claim, while card text still claims')
    for change in ['off-icon','different-icon','refresh','pending','search','tab','cabinet','close','empty','no-name']:
        v=fresh();names(v);v.stub(m['rewardItemDetail']['vir'],12,lambda ecx,a:opened.append(a));before=len(opened)
        v.run('rightDown',[34,183]);x,y=34,183
        if change=='off-icon':x=60
        elif change=='different-icon':x=100
        elif change=='refresh':v.receive(preview(v.read32(ps)))
        elif change=='pending':v.write32(ps+12,1)
        elif change=='search':v.write32(rs+96,1)
        elif change=='tab':v.state32(4,1)
        elif change=='cabinet':v.write32(ps+4,3)
        elif change=='close':v.run('message',[0,5,0,0,0,0])
        elif change=='empty':v.u.mem_write(pp+2176,bytes(2))
        elif change=='no-name':names(v,True)
        v.run('rightUp',[x,y]);assert len(opened)==before,change
        assert v.read32(rp)==0
    v=fresh();names(v);v.stub(m['rewardItemDetail']['vir'],12,lambda ecx,a:opened.append(a));before=len(opened);v.run('rightUp',[34,183]);assert len(opened)==before
    v.run('rightDown',[34,183]);v.run('toggle');assert v.read32(rp)==0 and v.u.mem_read(v.window+0x28,1)==b'\0'
    v.run('destructor',[0],ecx=v.window);assert bytes(v.u.mem_read(rp,12))==bytes(12)
    checks.append('Mismatched/released-only clicks, stale snapshots, loading/search, other tabs, empty slots and missing names cannot open an item; destruction clears press state')
    v=fresh();description=v.alloc(220);table=v.alloc(220);v.write32(description,table);v.write32(table+0x94,0x60000d00);constructed=[];destroyed=[];observed=[]
    def ctor(ecx,args):v.u.mem_write(ecx,bytes(248));v.write32(ecx,0x12345678);v.write32(ecx+8,0x87654321);constructed.append(ecx);return ecx
    v.stub(0x6A1B20,0,ctor);v.stub(0x6A6570,4,lambda ecx,a:v.write32(ecx+0x2c,a[0]));v.stub(0xA39340,4,lambda ecx,a:description if a==[12] else 0)
    def opened_item(ecx,a):observed.append((ecx,a,v.read32(a[2]),v.read32(a[2]+8),v.read32(a[2]+0x2c),bytes(v.u.mem_read(a[2]+0x5c,1))))
    v.stub(0x60000d00,24,opened_item);v.stub(0x4F08F0,0,lambda ecx,a:destroyed.append(ecx))
    v.run('rewardItemDetail',[501,0,0]);local=constructed[-1];assert observed[-1]==(description,[0,24,local,0,0,0],0x12345678,0x87654321,501,b'\1')
    assert destroyed==[local+0x44,local+0x2c]
    v.stub(0xA39340,4,lambda ecx,a:0);v.run('rewardItemDetail',[1201,0,0]);assert len(destroyed)==4 and len(observed)==1
    checks.append('Identified CItem information uses native constructor defaults and window 12 / message 24; both strings release even if window creation fails')
    pe.close();result={'passed':True,'checks':checks,'native_boundaries_mocked':True,'live_accepted':False};(directory/'reward-item-interaction-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
