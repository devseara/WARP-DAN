"""Exercise actual emitted reward previews and independent native search input."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_bestiary_journal import JournalVM
from verify_bestiary_cache import reply
from verify_bestiary_research_native import personal

def preview(sequence,items=((501,20),(505,10),(601,5),(602,1),(999,100))):
    data=bytearray(personal(sequence,tab=2));data.extend(bytes(264));struct.pack_into('<H',data,2,2440);struct.pack_into('<H',data,10,10)
    struct.pack_into('<H',data,2176,len(items))
    for i,(id,quantity) in enumerate(items):struct.pack_into('<II',data,2180+i*8,id,quantity)
    return bytes(data)

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary'];assert m['layoutVersion']>=10 and m['personalPayload']['size']==2440
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True);ps=m['personalState']['vir'];pp=m['personalPayload']['vir'];rs=m['rewardSearchState']['vir'];checks=[]
    def click(v,x,y):v.run('down',[x,y]);v.run('up',[x,y])
    def fresh():
        v=JournalVM(pe,m);v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]));v.receive(personal(v.read32(ps)));click(v,712,40);v.receive(preview(v.read32(ps)));return v
    v=fresh();assert struct.unpack_from('<H',v.personal_sent[-1],106)[0]==2
    captured=[];v.stub(0xA25A70,36,lambda ecx,a:captured.append(v.cstring(a[2])))
    v.stub(m['item']['vir'],12);v.calls=[];v.run('draw')
    icon_calls=[a for address,ecx,a in v.calls if address==m['item']['vir']]
    assert [a[0] for a in icon_calls]==[501,505,601,602,999]
    assert [a[1:] for a in icon_calls]==[[30+66*i,179] for i in range(5)]
    for quantity in [20,10,5,1,100]:assert ('x'+str(quantity)).encode() in captured
    checks.append('All five native ItemId icons render with their own quantity, within the existing reward card')
    for offset,fmt,value in [(2176,'H',6),(2178,'H',1),(2180,'I',0),(2184,'I',0),(2184,'I',101),(2,'H',2439),(10,'H',9)]:
        v=fresh();before=bytes(v.u.mem_read(pp,2440));bad=bytearray(preview(v.read32(ps)));struct.pack_into('<'+fmt,bad,offset,value);v.receive(bytes(bad));assert bytes(v.u.mem_read(pp,2440))==before,(offset,value)
    v=fresh();v.receive(personal(v.read32(ps),tab=2));assert bytes(v.u.mem_read(pp+2176,264))==bytes(264)
    checks.append('Malformed item counts, quantities and message/length pairs are rejected; legacy snapshots erase old preview slots')
    v=fresh();edit=v.alloc(0x11C);v.write32(rs+116,edit);v.write32(rs,v.window);v.focus=edit
    reward_text=v.string('white potion');monster_text=v.string('poring');monster_edit=v.alloc(0x11C);v.write32(m['state']['vir']+116,monster_edit)
    v.u.mem_write(m['query']['vir'],b'poring\0');v.stub(0x8210A0,0,lambda ecx,a:reward_text if ecx==edit else monster_text)
    before=bytes(v.u.mem_read(m['payload']['vir'],5120));cache=bytes(v.u.mem_read(m['cache']['vir'],m['cache']['size']));sent=len(v.personal_sent)
    v.run('rewardSearchTick');assert v.read32(rs+96)==1 and v.read32(ps+16)==0 and len(v.personal_sent)==sent
    click(v,40,174);assert len(v.personal_sent)==sent,'Stale search row was claimable'
    v.now+=249;v.run('rewardSearchTick');assert len(v.personal_sent)==sent
    v.now+=1;v.run('rewardSearchTick');q=v.personal_sent[-1]
    assert len(v.personal_sent)==sent+1 and q[36:64].split(b'\0')[0]==b'white potion' and struct.unpack_from('<H',q,24)[0]==0
    assert struct.unpack_from('<H',q,26)[0]==0 and struct.unpack_from('<H',q,106)[0]==2
    assert v.cstring(m['query']['vir'])==b'poring' and bytes(v.u.mem_read(m['payload']['vir'],5120))==before and bytes(v.u.mem_read(m['cache']['vir'],m['cache']['size']))==cache
    v.receive(preview(v.read32(ps)));v.run('rewardSearchTick');assert len(v.personal_sent)==sent+1
    checks.append('Rewards search debounces for 250 ms, resets paging, blocks stale claims and leaves Monsters query/cache untouched')
    v.u.mem_write(reward_text,b'blue potion\0');v.run('rewardSearchTick');assert v.read32(rs+96)==1
    click(v,620,40);assert v.state32(4)==1 and v.focus==0 and v.u.mem_read(edit+0x28,1)==b'\0' and v.read32(rs+96)==0
    v.receive(personal(v.read32(ps)));click(v,423,486);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==3
    click(v,712,40);v.receive(preview(v.read32(ps)));v.focus=edit;v.run('destructor',[0],ecx=v.window)
    assert v.focus==0 and bytes(v.u.mem_read(rs,120))==bytes(120) and bytes(v.u.mem_read(m['rewardQuery']['vir'],28))==bytes(28) and bytes(v.u.mem_read(pp,2440))==bytes(2440)
    checks.append('Tab changes hide the Rewards edit and release focus; destruction clears both input ownership and all preview data')
    result={'passed':True,'checks':checks,'native_boundaries_mocked':True,'live_accepted':False};(directory/'rewards-preview-search-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
