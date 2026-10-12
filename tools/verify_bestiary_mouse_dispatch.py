"""Run the actual native manager poll block through the published frame VTable.

The V11 failure was invisible to tests that called down/up directly: native slot
30 runs unconditionally between them. Slot 32 is right-down, 33 is right-up.
This test executes A46ED3..A46F4C from the client, not a reimplemented ordering.
"""
from pathlib import Path
import argparse,json,struct
import pefile
from unicorn.x86_const import UC_X86_REG_EBP,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_ESP,UC_X86_REG_EFLAGS
from verify_bestiary_journal import JournalVM
from verify_bestiary_cache import reply
from verify_bestiary_research_native import personal
from verify_bestiary_rewards_ui import preview

POLL_START=0xA46ED3
POLL_END=0xA46F4C
RIGHT_DOWN=0xA46EC5

def poll(v,x,y,left=0,right=0,right_down=False,moving=False):
    # Native dispatcher receives the current topmost frame in ESI and client
    # coordinates in EDI / [EBP-68], with the previous cursor in mgr+46C/470.
    frame=v.alloc(0x120)+0x100;manager=v.alloc(0x500)
    for off,value in [(0x68,y),(0x70,x),(0x74,y)]:v.write32(frame-off,value)
    v.write32(manager+0x46c,x+int(moving));v.write32(manager+0x470,y)
    for address,value in [(0x11E40E4,left),(0x11E40E8,right),(0x11E40EC,0)]:v.write32(address,value)
    for reg,value in [(UC_X86_REG_EBP,frame),(UC_X86_REG_EBX,manager),(UC_X86_REG_ESI,v.window),(UC_X86_REG_EDI,x),(UC_X86_REG_ESP,v.stack),(UC_X86_REG_EFLAGS,0x202)]:v.u.reg_write(reg,value)
    v.u.emu_start(RIGHT_DOWN if right_down else POLL_START,POLL_END,count=1000000)
    assert v.u.reg_read(UC_X86_REG_ESP)==v.stack,'Native mouse poll stack imbalance'
    assert v.u.reg_read(UC_X86_REG_ESI)==v.window,'Frame receiver corrupted'

def dispatch(v,slot,x,y):
    table=v.read32(v.window);return v.run(v.read32(table+slot*4),[x,y],ecx=v.window)

def fresh(pe,m):
    v=JournalVM(pe,m);v.ready();v.stub(0xA1EF70,8);v.stub(0xA23470,8) # stock tooltip reset; must stay slot 30
    return v

def verify(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary'];pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True);checks=[]
    def click(v,x,y):
        dispatch(v,25,x,y);poll(v,x,y,left=1);poll(v,x,y,left=3)
    v=fresh(pe,m);click(v,625,40)
    assert v.state32(4)==1,'Native slot-30 mouse poll erased Research tab click before left-button release'
    checks.append('Native poll preserves left presses through slot 30, stationary hover and slot-31 release')
    for x,tab in [(712,2),(545,0),(625,1),(712,2),(545,0)]:click(v,x,40);assert v.state32(4)==tab
    v=fresh(pe,m);dispatch(v,25,625,40);poll(v,625,40,left=1,moving=True);poll(v,625,40,left=3,moving=True);assert v.state32(4)==1
    v=fresh(pe,m);click(v,60,185);assert v.state32(28)==1004 and v.sent
    v=fresh(pe,m);click(v,60,70);assert v.focus==v.state32(116)
    v=fresh(pe,m);click(v,166,92);assert v.state32(124)==1;click(v,24,149);assert v.state32(120)==2 and v.state32(124)==0
    v=fresh(pe,m);click(v,203,40);assert v.state32(208)==1;click(v,370,264);assert v.state32(208)==0
    v=fresh(pe,m);click(v,305,336);assert v.state32(140)==1;click(v,397,336);assert v.state32(140)==2
    v=fresh(pe,m);click(v,747,11);assert v.u.mem_read(v.window+0x28,1)==b'\0'
    checks.append('Monster selection, all main/detail tabs, search focus, element/filter controls and close survive actual native dispatch')
    if m.get('layoutVersion',0)>=11:
        v=fresh(pe,m);ps=m['personalState']['vir'];v.run('sender',[1,0,0,0]);v.receive(reply(v.sent[-1]));v.receive(personal(v.read32(ps)));click(v,712,40);v.receive(preview(v.read32(ps)))
        rp=m['rewardPointer']['vir'];opened=[]
        v.stub(m['rewardItemName']['vir'],4,lambda ecx,a:v.string('Red Potion'));v.stub(m['rewardItemDetail']['vir'],12,lambda ecx,a:opened.append(a))
        sent=len(v.personal_sent);click(v,34,183);assert len(v.personal_sent)==sent
        poll(v,34,183,right=1,right_down=True);assert v.read32(rp)==1,'Native slot 32 must record the right press'
        poll(v,34,183,right=0);assert v.read32(rp)==1,'Unconditional slot 30 must not replace the recorded right press'
        poll(v,34,183,right=3);assert opened==[[501,0,0]] and v.read32(rp)==0 and len(v.personal_sent)==sent
        click(v,40,174);assert len(v.personal_sent)==sent+1 and struct.unpack_from('<H',v.personal_sent[-1],26)[0]==1
        v.receive(preview(v.read32(ps)));poll(v,34,183,right=1,right_down=True);v.receive(preview(v.read32(ps)));poll(v,34,183,right=3);assert len(opened)==1
        checks.append('Native slots 32/33 inspect the same item without claiming; slot 30 preserves that press and refresh cancels stale inspection')
        native=struct.unpack('<53I',pe.get_data(0x102FE08-pe.OPTIONAL_HEADER.ImageBase,212));table=struct.unpack('<53I',pe.get_data(m['vtable']['vir']-pe.OPTIONAL_HEADER.ImageBase,212))
        assert table[30]==native[30]==0xA23470 and table[32]==m['rightDown']['vir'] and table[33]==m['rightUp']['vir']
    result={'passed':True,'checks':checks,'dispatcher_range':[hex(POLL_START),hex(POLL_END)],'native_graphics_and_network_boundaries_mocked':True,'live_accepted':False};(directory/'mouse-dispatch-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');pe.close();return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);print(json.dumps(verify(ap.parse_args().directory),indent=2))
