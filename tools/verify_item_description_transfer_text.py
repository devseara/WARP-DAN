"""Inventory deposit continuity and player-facing notice filtering regressions."""
import struct
from verify_item_description_native import VM, WIN, ITEM, OFF
from verify_item_description_comparison import DualVM, COMP
from verify_item_description_components import TripleVM, DETAIL

SESSION=0x15fa3c0

def container(v, scope, rows):
    head=0x50160000 if scope==1 else 0x50170000
    offset=0x16f0 if scope==1 else 0x1718
    v.write32(SESSION+offset,head);v.write32(SESSION+offset+4,len(rows))
    v.write32(head,head+0x100 if rows else head)
    for i,(index,amount,data) in enumerate(rows):
        node=head+0x100+i*0x110
        v.write32(node,head+0x100+(i+1)*0x110 if i+1<len(rows) else head)
        value=bytearray(data);struct.pack_into('<I',value,4,index);struct.pack_into('<I',value,0x10,amount)
        v.u.mem_write(node+8,bytes(value))

def stale(v):
    data=v.response();struct.pack_into('<I',data,20,2);struct.pack_into('<H',data,38,0)
    return data

def transfers(pe,m):
    def fresh(existing=()):
        v=VM(pe,m);v.open();data=bytes(v.u.mem_read(ITEM,0xb8))
        container(v,1,[(7,3,data)]);container(v,3,[(i,q,data) for i,q in existing])
        v.open();reply=v.response();struct.pack_into('<Q',reply,52,0x12345678)
        assert v.receive(reply)==1
        return v,data,reply
    routes=[]
    for name,existing,destination in [('new slot',[],1),('identical older copy',[(1,1)],2),('merged stack',[(3,5)],3)]:
        v,data,old=fresh(existing);before=len(v.sent)
        calls=len(v.native_calls);container(v,1,[])
        assert v.receive(stale(v))==1 and v.s('ready')
        # Server may invalidate before the destination packet arrives. An older
        # identical storage copy must not be selected during this interval.
        v.now+=160;v.run('Process');assert len(v.sent)==before and v.s('ready')
        rows=[(i,q,data) for i,q in existing if i!=destination]
        rows.append((destination,8 if existing and destination==3 else 3,data))
        container(v,3,rows);v.now+=160;v.run('Process')
        assert len(v.sent)==before+1 and v.s('ready')
        request=v.sent[-1]
        assert struct.unpack_from('<IH',request,20)==(destination,3)
        assert struct.unpack_from('<Q',request,76)[0]==0,'old inventory fingerprint survived deposit'
        assert request[26:74]==v.sent[-2][26:74],'refine/cards/options changed during deposit'
        assert v.read32(WIN+0xb8+4)==destination
        assert not any(slot==37 for slot,_,_ in v.native_calls[calls:]),'legacy body was rebuilt'
        assert v.receive(old)==0 and v.receive(v.response())==1 and v.s('ready')
        assert v.run('CustomDraw',[WIN],ecx=0)==1
        lookups=[];getter=v.stubs[0x5d98a0][1]
        v.stub(0x5d98a0,0,lambda ecx,args:lookups.append(ecx) or getter(ecx,args))
        count=len(v.sent)
        for _ in range(120):v.now+=16;v.run('Process')
        assert len(v.sent)==count and not lookups,'idle frames rescanned containers'
        routes.append(name)
    # Partial deposit stays attached to the surviving Inventory stack.
    v,data,_=fresh();container(v,1,[(7,1,data)]);container(v,3,[(1,2,data)])
    v.now+=200;assert v.receive(stale(v))==1
    assert struct.unpack_from('<IH',v.sent[-1],20)==(7,1)
    assert struct.unpack_from('<Q',v.sent[-1],76)[0]==0 and v.receive(v.response())==1
    # A delayed rejected request (rather than an unsolicited notice) follows
    # the same recovery path while the first snapshot is still loading.
    v,data,_=fresh();v.now+=200;v.open();container(v,1,[]);container(v,3,[(1,3,data)])
    assert v.receive(stale(v))==1;v.now+=160;v.run('Process')
    assert struct.unpack_from('<IH',v.sent[-1],20)==(1,3) and v.receive(v.response())==1
    # If two new indistinguishable copies arrive, do not claim either. Retain
    # the new UI using server catalog data after a bounded settling interval.
    v,data,_=fresh();container(v,1,[]);container(v,3,[(1,3,data),(2,3,data)])
    calls=len(v.native_calls);assert v.receive(stale(v))==1
    for _ in range(7):v.now+=160;v.run('Process');assert v.s('ready')
    assert struct.unpack_from('<IH',v.sent[-1],20)==(0,0)
    assert v.receive(v.response())==1 and not any(slot==37 for slot,_,_ in v.native_calls[calls:])
    # New item / close cancels pending recovery; old replies cannot overwrite it.
    for close in [False,True]:
        v,data,old=fresh();container(v,1,[]);assert v.receive(stale(v))==1
        if close:v.run('Message',[0,5,0,0,0,0])
        else:v.open(itemid=1202);v.receive(v.response())
        before=len(v.sent);container(v,3,[(1,3,data)])
        for _ in range(10):v.now+=160;v.run('Process')
        assert len(v.sent)==before and v.receive(old)==0
        if not close:assert struct.unpack_from('<I',v.sent[-1],16)[0]==1202
    return dict(passed=True,routes=routes,checks=[
        'Delayed inventory deletion/storage addition keeps the redesigned pane open',
        'New slots and increased destination stacks retain refine/cards/options and reset the old fingerprint',
        'Older identical copies excluded; ambiguous arrivals use catalog without guessing',
        'Partial deposits stay in inventory; pending-request rejection also recovers',
        'Switch/close cancels recovery; late replies rejected; 120 idle frames have no scans or requests'])

def wording(pe,m):
    from verify_item_description_payload import rows_response,layout_lines
    notices=[
        (3,'Item effects','Use Original for the full legacy description; server descriptors are not configured'),
        (3,'Additional effects','See Original for character-dependent or conditional effects.'),
        (8,'Effect','Inspect component for its legacy description'),
        (4,'Refine','Instance required'),
        (10,'Job / equip rules','Instance and compatible equipment required'),
        (11,'Instance restrictions','Inspect an owned item'),
        (8,'Slot 2','Unknown component'),
        (8,'Slot 3','Extra slot modifier (type not configured)'),
        (3,'Item metadata','Forged / created item metadata; not card sockets'),
        (7,'Rolled property 1','7 (label not configured)'),
        (4,'Refine bonus','No direct ATK/DEF contribution'),
        (4,'Next +8','No direct ATK/DEF contribution total')]
    rows=[(section,3,0,4,0,label,text) for section,label,text in notices]
    rows += [(4,0,0,0,0,'Refine bonus','+5.25 DEF before rounding'),
             (4,0,0,0,0,'Next +8','+6.00 DEF before rounding total'),
             (3,1,0,2,0,'','Requires refine +9; requires grade 2: Damage +20%'),
             (5,1,0,2,0,'Epic','requires grade 2: ATK +2%'),
             (8,2,4001,0,1,'Slot 1','Installed card'),
             (8,3,0,4,1,'Effect','Inspect component for its legacy description'),
             (8,1,0,2,1,'','Requires refine +9: Physical damage +20%'),
             (8,2,4002,4,3,'Slot 3','Extra slot modifier (type not configured)'),
             (8,2,0,8,4,'Slot 4','Empty'),
             (10,0,0,2,0,'Equip eligibility','Requirements or restrictions not met')]
    checked=[]
    for cls,window in [(VM,WIN),(DualVM,COMP),(TripleVM,DETAIL)]:
        v=cls(pe,m);v.open()
        if window!=WIN:v.run('Message',[0,24,ITEM,1,0,0],ecx=window)
        data=rows_response(v,rows);struct.pack_into('<I',data,48,1)
        assert v.receive(data)==1;v.run('Draw',ecx=window)
        saved=v.state;v.state=m['state' if window==WIN else 'comparisonState' if window==COMP else 'componentState']['vir']
        lines=layout_lines(v);text='\n'.join(line[-1] for line in lines)
        for _,_,message in notices:assert message not in text
        for phrase in ['before rounding','Requires refine','requires grade','Some effects were omitted.','label not configured']:
            assert phrase not in text,phrase
        for phrase in ['+5.25 DEF','+6.00 DEF total','Damage +20%','ATK +2%','Physical damage +20%','Slot 4','Equipable: No']:
            assert phrase in text,(window,phrase,text)
        assert v.s('hits')==2,'known card/socket disappeared with its technical subtitle'
        assert bytes(v.u.mem_read(v.state+OFF['snapshot'],len(data)))==bytes(data),'presentation changed authoritative rows'
        v.state=saved;checked.append(window)
    v=VM(pe,m);v.open();v.receive(rows_response(v,[(3,3,0,4,0,'Item effects',notices[0][2])]))
    v.run('Draw');assert not any('Special Effects:' in line[-1] for line in layout_lines(v))
    return dict(passed=True,panes=checked,checks=[
        'Requested fallback/technical notices removed in main, comparison and component panes',
        'Numeric DEF and effect bonuses retained; refine/grade prefixes removed without altering flags',
        'Known occupied sockets and empty-slot labels preserved; all-hidden sections leave no headings',
        'Raw snapshots unchanged; truncation footer hidden'])

def checks(pe,m):
    return dict(passed=True,transfers=transfers(pe,m),wording=wording(pe,m))
