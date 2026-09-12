"""Execute V9 account transport, views, claims, favorites and teardown as emitted x86."""
from pathlib import Path
import argparse,json,struct
import pefile
from verify_bestiary_journal import JournalVM
from verify_bestiary_cache import reply

def personal(request,tab=1,view=0,selected=1002,flags=0):
    data=bytearray(2176)
    struct.pack_into('<HHIHHIIII6HI',data,0,0xbef,2176,0x49555342,3,9,request,7,0,selected,tab,view,0,2,6,flags,1002)
    struct.pack_into('<I',data,44,1002)
    def text(off,value):data[off:off+len(value)]=value.encode()
    for off,value in [(64,'Poring'),(128,'Research tier 2 / 5 | 25 eligible kills'),(256,'Account progress committed.'),(384,'Journal points: 100'),(2048,'Tracking: Poring | 25 / 100 kills')]:text(off,value)
    for i in range(6):
        row=512+i*256;struct.pack_into('<4I',data,row,1002+i,1002+i,2 if tab==2 else 1,1002)
        for off,value in [(16,f'Milestone {i+1}'),(80,'Account milestone description'),(176,'Available' if tab==2 else 'Completed'),(224,'Cosmetic reward')]:text(row+off,value)
    return bytes(data)

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary'];assert m['layoutVersion']>=9
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True);ps=m['personalState']['vir'];pp=m['personalPayload']['vir'];checks=[]
    def click(v,x,y):v.run('down',[x,y]);v.run('up',[x,y])
    def fresh():
        v=JournalVM(pe,m);v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]));v.receive(personal(v.read32(ps)));return v
    v=fresh();assert len(v.personal_sent)==1 and len(v.sent)==1
    q=v.personal_sent[0];assert struct.unpack_from('<HHIHH',q)==(0xbf8,128,0x49555342,3,8)
    before=bytes(v.u.mem_read(m['payload']['vir'],5120));cache=bytes(v.u.mem_read(m['cache']['vir'],m['cache']['size']))
    click(v,620,40);q=v.personal_sent[-1];assert struct.unpack_from('<H',q,20)[0]==1 and v.state32(4)==1
    v.receive(personal(v.read32(ps)));assert v.read32(ps+16)==1
    assert bytes(v.u.mem_read(m['payload']['vir'],5120))==before and bytes(v.u.mem_read(m['cache']['vir'],m['cache']['size']))==cache
    checks.append('Independent personal request/snapshot never changes the encyclopedia payload or cache')
    for off,fmt,value in [(2,'H',2175),(8,'H',4),(10,'H',10),(12,'I',0),(12,'I',1000),(20,'I',4),(28,'H',0),(28,'H',3),(30,'H',4),(32,'H',2),(36,'H',7),(38,'H',8)]:
        v=fresh();good=bytes(v.u.mem_read(pp,2176));bad=bytearray(personal(v.read32(ps)));struct.pack_into('<'+fmt,bad,off,value);v.receive(bytes(bad));assert bytes(v.u.mem_read(pp,2176))==good,(off,value)
    v=fresh();bad=bytearray(personal(v.read32(ps)));bad[64:]=b'X'*(2176-64);v.receive(bytes(bad));assert v.u.mem_read(pp+127,1)==b'\0' and v.u.mem_read(pp+2175,1)==b'\0'
    checks.append('Account snapshots reject stale/future identities, wrong schema, invalid pages/counts and terminate all strings')
    v=fresh();click(v,620,40);v.receive(personal(v.read32(ps)));v.calls=[];v.run('draw')
    assert any(a[3:7]==[31,181,210,168] for address,_,a in v.calls if address==m['preview']['vir'])
    click(v,144,127);assert struct.unpack_from('<H',v.personal_sent[-1],64)[0]==1
    v.receive(personal(v.read32(ps),view=1));click(v,40,174);assert v.read32(ps+4)==0 and v.read32(ps+24)==1002
    v.receive(personal(v.read32(ps)));click(v,423,486);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==3
    v.receive(personal(v.read32(ps)));click(v,551,486);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==4
    checks.append('Research has a native fitted sprite, group-to-limiting-member selection and server-owned tracking/favorites')
    v=fresh();click(v,712,40);v.receive(personal(v.read32(ps),tab=2));click(v,40,174)
    assert struct.unpack_from('<HI',v.personal_sent[-1],26)==(1,1002)
    count=len(v.personal_sent);click(v,40,174);assert len(v.personal_sent)==count
    v.receive(personal(v.read32(ps),tab=2));click(v,677,486);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==2
    v.receive(personal(v.read32(ps),tab=2));click(v,373,127);assert struct.unpack_from('<H',v.personal_sent[-1],64)[0]==3
    data=bytearray(personal(v.read32(ps),tab=2,view=3));struct.pack_into('<I',data,520,8);v.receive(bytes(data));click(v,40,174);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==6
    assert len(v.sent)==1
    checks.append('Only eligible rows claim; in-flight double clicks are blocked; Claim All and cabinet title equip send bounded account actions')
    v=fresh();click(v,620,40);before=bytes(v.u.mem_read(m['payload']['vir'],5120));count=len(v.personal_sent)
    v.now+=8000;v.run('requestTick');assert v.read32(ps+12)==0 and v.read32(pp+20)==3
    assert b'timed out' in v.cstring(pp+256) and len(v.personal_sent)==count
    assert bytes(v.u.mem_read(m['payload']['vir'],5120))==before
    click(v,290,486);assert struct.unpack_from('<H',v.personal_sent[-1],26)[0]==5
    v.receive(personal(v.read32(ps)));assert v.read32(pp+20)==0
    checks.append('Personal timeout preserves catalog/display, sends no idle polling and recovers through Sync progress')
    v=fresh();seq=v.read32(ps);v.run('destructor',[0],ecx=v.window)
    assert v.read32(ps)!=seq and v.read32(ps+16)==0 and bytes(v.u.mem_read(pp,2176))==bytes(2176)
    v.receive(personal(seq));assert bytes(v.u.mem_read(pp,2176))==bytes(2176)
    checks.append('Destruction clears all personal payload/preferences, advances request identity and rejects the old account reply')
    result={'passed':True,'checks':checks,'live_accepted':False,'engine_boundaries_mocked':True}
    (directory/'research-native-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
