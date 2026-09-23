"""Execute v7 configurable text and server-owned Premium gating in shipped x86.

Offline resource/font/transport boundaries; no game connection or account writes.
"""
import argparse
from pathlib import Path
import struct
from test_battlepass_board import BoardMachine, snapshot
from test_battlepass_surface import real_window
from test_battlepass_rewards import rewards, picture, gray

LABELS=['Battle Pass','BATTLE PASS','Status','Level','Pass EXP','Track Information','Difficulty Tiers',
        'Tier','Count','EXP','Difficulty','Rules','Normal','Premium','Rewards','Standard','Premium',
        'Current level','Total EXP','Status','Season Information','Ends in','Easy','Normal','Hard','Hardcore','Battle Pass Rewards']
INFO=['Normal rewards are free.','Premium rewards require','an unlocked premium pass.','Select a level and track,','then click Claim Reward.','Items arrive via RODEX.']
RULES=['One difficulty mission','per account at a time.','','Items used on turn-in.','','Abandon fee:','300,000 Zeny','Pass resets monthly.']


def put(p,offset,value,size=64):p[offset:offset+size]=value.encode()[:size-1].ljust(size,b'\0')


def configured():
    p=rewards()+bytearray(2624)
    struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,7)
    struct.pack_into('<I',p,1188,512|1024|2048|48)
    for i,value in enumerate(LABELS+INFO+RULES):put(p,7976+i*64,value)
    return p


def verify(exe,output):
    output.mkdir(parents=True,exist_ok=True)
    m=BoardMachine(exe);p=configured();m.receive(p);real_window(m)
    assert m.sent[-1][3:]==(7,0,0),'real open must negotiate v7 only with advertised capability'
    m.draw();assert m.contains('Status: Standard') and not m.contains('Track:')
    custom=bytearray(p)
    edits={0:'My Pass',1:'AUTUMN PASS',2:'Membership',3:'Rank',4:'Pass Points',5:'Reward Guide',6:'Challenge Tiers',
           7:'Mode',8:'Goal',9:'Points',10:'Challenge',11:'Guidelines',12:'Free',13:'Elite',14:'Loot',
           17:'Current rank',18:'Total points',19:'Membership',20:'Season Details',21:'Expires',
           22:'Beginner',23:'Regular',24:'Expert',25:'Master',26:'Season Loot'}
    for i,value in edits.items():put(custom,7976+i*64,value)
    put(custom,2912,'Autumn Adventures',48)
    put(custom,7976+27*64,'Custom reward guide')
    put(custom,7976+33*64,'Custom first rule')
    put(custom,7976+34*64,'')
    m.receive(custom);m.draw(output/'custom-quests.png')
    for value in ['My Pass','AUTUMN PASS','Autumn Adventures','Membership: Standard','Rank: 2 / 30','Pass Points: 2,500',
                  'Challenge Tiers','Mode','Goal','Points','Guidelines','Custom first rule','Beginner','Expert','+50 Points']:
        assert m.contains(value),value
    m.click(50,82);m.draw(output/'custom-mission.png')
    for label,x in [('Challenge',150),('Goal',335),('Points',416),('Membership',509)]:
        assert any(row[:3]==(label,x,230) for row in m.texts),(label,x)
    m.click(50,114);m.draw(output/'custom-rewards.png')
    for value in ['Season Loot','Reward Guide','Custom reward guide','Free','Elite','Loot','Rank 1','Rank 2']:
        assert m.contains(value),value
    m.click(50,146);m.draw(output/'custom-stats.png')
    for value in ['Current rank','Total points','Membership','Season Details','Autumn Adventures']:
        assert m.contains(value),value
    # Server premium flag is authoritative even when labels or cell flags lie.
    locked=bytearray(p);struct.pack_into('<H',locked,10,struct.unpack_from('<H',locked,10)[0]&~8)
    put(locked,348,'Premium',24) # Cosmetic text must never grant access.
    for col in range(5):struct.pack_into('<I',locked,3536+(5+col)*372+4,5)
    m.receive(locked);m.click(50,114)
    def item():
        window,item_id,x,y=m.args(4);m.items.append((item_id,x,y));pix,width,_=m.pixels(window)
        for row in range(24):m.u.mem_write(pix+((y+row)*width+x)*4,struct.pack('<I',0xFFDC4628)*24)
        m.ret(16)
    m.stub(m.r(m.c['api']+32),item)
    m.draw(output/'non-premium-gray.png')
    pix,width,_=m.pixels(m.obj)
    def pixel(x,y):return m.r(pix+(y*width+x)*4)
    assert pixel(230,194)==0xFFDC4628 and pixel(230,345)==gray(0xFFDC4628)
    for col in range(5):
        region=picture(m).crop((210+col*100,335,306+col*100,468))
        assert all(r==g==b and a==255 for r,g,b,a in region.get_flattened_data())
        m.mouse(230+col*100,445,0);assert m.r(m.c['state']+8)==0
        m.mouse(230+col*100,445,1)
    m.draw();assert pixel(258,184)==0xFF60C789 and pixel(258,335)!=0xFFD0A03C
    m.invoke(m.c['move'],0,(m.obj,271,421));m.draw(output/'non-premium-tooltip.png')
    assert m.contains('Client item name') and m.contains('Quantity: 6')
    m.mouse(271,421,2);m.mouse(271,421,3);assert m.descriptions==[555]
    # Acquiring Premium unlocks only reached levels; revocation clears selection.
    m.receive(p);m.click(230,445);m.invoke(m.c['move'],0,(m.obj,0,0));m.draw(output/'premium-unlocked.png')
    assert pixel(258,335)==0xFFD0A03C and pixel(230,345)==0xFFDC4628
    assert pixel(558,335)!=0xFFD0A03C
    m.click(670,502);assert m.sent[-1][3:]==(7,15,1)
    m.now+=1500;m.receive(locked);m.draw()
    assert pixel(258,335)==gray(0xFFD4DFE9) and pixel(258,184)==0xFF60C789
    # Malformed v7 framing leaves all cached data unchanged.
    before=bytes(m.u.mem_read(m.c['board'],7728))
    for length,version in [(10599,7),(10600,6),(10600,8),(7976,7)]:
        bad=bytearray(p);struct.pack_into('<HH',bad,0,0xBF6,length);struct.pack_into('<H',bad,8,version)
        m.receive(bad);assert bytes(m.u.mem_read(m.c['board'],7728))==before
    # Every text slot is terminated by the receiver notification, even malformed.
    unbounded=bytearray(p);unbounded[7976:]=b'X'*2624;m.receive(unbounded)
    assert all(m.u.mem_read(m.c['board']+5104+i*64+63,1)==b'\0' for i in range(41))
    m.draw()
    # Empty strings intentionally hide prose. Downgrades restore legacy defaults.
    blank=bytearray(p);blank[7976:]=bytes(2624);m.receive(blank);m.draw()
    assert not m.contains('Track Information') and not m.contains('One difficulty mission')
    m.receive(rewards());assert bytes(m.u.mem_read(m.c['board']+5104,2624))==bytes(2624)
    m.draw();assert m.contains('Track Information') and m.contains('Status: Standard')
    assert m.r(m.r(m.obj+0x24)+0x28)==0,'text and gray cards must retain opaque presentation'
    print('PASS BPUI v7: negotiated text, 27 labels/6 info/8 rules, actual values preserved, all four pages, blank/bounded/malformed/downgrade, non-Premium gray/selection/inspection, Premium acquire/revoke and server-flag authority')
    mission_hint(exe,output)


def mission_hint(exe,output):
    m=BoardMachine(exe);m.click(50,82)
    original='Choose a type and an available tier. Targets use your configured pools.'
    m.draw();assert m.contains(original),'old servers retain default instructions'
    for p in (snapshot()[:2872],snapshot(),rewards(),configured()):
        struct.pack_into('<H',p,2,len(p))
        if len(p)==2872:struct.pack_into('<H',p,8,4)
        struct.pack_into('<I',p,1188,struct.unpack_from('<I',p,1188)[0]|4096)
        put(p,2776,'Pick a type, then choose your next challenge.',96)
        m.receive(p);m.draw(output/f'mission-hint-v{struct.unpack_from("<H",p,8)[0]}.png')
        assert any(row[:3]==('Pick a type, then choose your next challenge.',138,207) for row in m.texts)
        assert not m.contains(original)
        for kind in (0,1):
            m.click(200 if kind==0 else 400,185);m.draw()
            assert m.contains('Pick a type, then choose your next challenge.')
        put(p,2776,'',96);m.receive(p);m.draw()
        assert not any(row[1:3]==(138,207) and row[0] for row in m.texts),'empty hint should hide without fallback'
        p[2776:2872]=b'W'*96;m.receive(p);m.draw()
        assert m.u.mem_read(m.c['state']+32+2871,1)==b'\0'
        rows=[row for row in m.texts if row[1:3]==(138,207)]
        assert rows and len(rows[0][0])<=95 and m.font.getlength(rows[0][0])<=576,'hint must stay bounded inside its row'
    active=configured();struct.pack_into('<H',active,10,struct.unpack_from('<H',active,10)[0]|1)
    struct.pack_into('<I',active,1188,struct.unpack_from('<I',active,1188)[0]|4096)
    put(active,2776,'Top maps by configured monster spawn count.',96)
    m.receive(active);m.draw(output/'active-habitat-hint.png')
    assert any(row[:3]==('Top maps by configured monster spawn count.',136,320) for row in m.texts)
    assert not any(row[1:3]==(138,207) for row in m.texts),'selection text must not overlap active mission'
    m.receive(configured());m.draw();assert m.contains(original),'capability removal restores old-server fallback'
    print('PASS Mission hint: capability-gated v4-v7 field, both hunt types, blank hide, bounded long/malformed strings, active habitat isolation and old-server fallback')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();verify(args.exe,args.output)
