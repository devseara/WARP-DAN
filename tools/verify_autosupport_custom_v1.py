"""Execute Custom AutoSupport renderer and preserved ASUI handlers in Unicorn."""
from pathlib import Path
import argparse,json,struct
from verify_autohunt_custom_v1 import Machine,WINDOW,verify_gdi_alpha

class SupportMachine(Machine):
    def __init__(self,directory,game=None):super().__init__(directory,game,'autosupport')
    def populate(self):
        super().populate()
        self.set(72,0x1FFFF);self.u.mem_write(self.state+184,bytes(68));self.u.mem_write(self.state+188,b'Timer: 02h 15m 00s\0')
        self.set(76,10);self.set(64,2)
        for i in range(10):self.u.mem_write(self.rows[0]+i*40,struct.pack('<II32s',2001+i,0,('Party player '+str(i+1)).encode()))
        self.resources[506]='초록포션'.encode('cp949')
        self.u.mem_write(self.cfg[157],struct.pack('<III24s12s',506,0,1|(17<<16),b'Green Potion',b''))

def verify(m):
    for slot,tab in enumerate([0,2,1,3,4,5,6]):
        m.click(30,140+44*slot);assert m.get(4)==tab;m.draw()
        if tab in (3,5,6):assert any('x ' in s for _,_,s in m.texts)
        assert any(b'sys_close_off.bmp' in p for p in m.widget_paths)
        m.image.save(m.directory/f'support-v1-tab-{tab}.png')
    m.set(4,1);m.set(64,0);m.calls.clear();m.click(175,215);assert m.calls[-1]==(19,2001,0),m.calls
    m.event('Down',724,240);m.event('Move',724,999);m.event('Up',724,999);assert m.get(144)==5 and m.capture==0
    m.set(4,2)
    for page in (1,2):
        m.set(8,page);m.click(680,174);assert m.calls[-1]==(47,(page-1)*8,0)
        m.drag(8,5,10);m.event('Up',185,175);assert m.calls[-1]==(37 if page==1 else 40,0,5|(10<<16))
    m.set(8,3);m.set(108,60);m.click(339,378);assert m.calls[-1]==(50,70,0)
    m.event('Down',260,378);m.event('Move',999,378);m.event('Up',999,378);assert m.calls[-1]==(50,100,0)
    m.set(4,3);m.set(12,1);m.click(711,185);assert m.calls[-1][0:2]==(60,0)
    m.event('Down',480,211);m.event('Move',999,211);m.event('Up',999,211);assert m.calls[-1]==(59,0,100)
    m.drag(1,2);m.event('Up',185,185);assert m.calls[-1]==(58,0,2)
    m.set(12,2);m.draw();assert any(s=='x 17' for _,_,s in m.texts)
    m.image.save(m.directory/'support-v1-status.png')
    m.drag(1,2);m.event('Up',185,230);assert m.calls[-1]==(66,0,2)
    m.set(4,4);m.set(16,1);m.click(170,235);assert m.calls[-1][0]==36
    m.click(451,298);assert m.calls[-1][0]==65 and m.get(16)==1
    m.event('Down',560,258);m.event('Move',999,258);m.event('Up',999,258);assert m.calls[-1]==(53,90,0)
    m.set(16,2);m.click(530,190);assert m.get(168)==1
    m.click(530,213+3*24+5);assert m.calls[-1]==(54,0,3),m.calls[-1]
    m.set(4,5);m.drag(1,2);m.event('Up',185,185);assert m.calls[-1][0]==62
    m.drag(8,26,2);m.event('Up',185,250);assert m.calls[-1][0]==63
    m.set(4,6);m.click(680,174);assert m.calls[-1]==(47,20,0)
    for count in [65535,7]:
        m.write(m.rows[5]+8,1|(count<<16));m.draw();assert any(s==f'x {count}' for _,_,s in m.texts)
    m.set(4,0);m.click(175,368);assert m.get(4)==1 # Master navigation, never AHUI pickup setting 20.
    m.set(4,0);m.click(465,302);assert m.calls[-1][0]==22 and m.get(4)==0
    m.click(530,150);m.set(124,0);m.click(175,178);assert m.calls[-1][0]==7
    m.click(510,178);assert m.calls[-1][0]==64
    m.event('Down',724,240);m.event('Move',724,999);m.event('Up',724,999);assert m.get(124)==4 and m.capture==0
    for result,index in [(2,158),(3,159),(4,160)]:
        m.set(112,1);m.set(184,result);m.draw()
        # Native message wraps into complete lines; verify its leading word.
        first=m.decode(m.cstr(m.cfg[index])).split()[0];assert any(first in s for _,_,s in m.texts)
        m.click(300,250);assert m.get(112)==0
    m.calls.clear();m.click(40,500);assert m.calls[-1]==(10,1,0)
    m.set(28,1<<12);m.click(738,12);assert m.read(WINDOW+0x28)==0 and m.get(28)==1<<12
    assert all(call[0] not in (45,46) for call in m.calls)
    return {'passed':True,'live_accepted':False,'checks':['seven tabs and native close bitmap','party master selection and scroll capture','attack/support/recovery skill registration and delay dialogs','HP/SP potion thresholds and quantities','status recovery item registration and quantities','loot categories/weight/actions/dropdown context','movement methods','buff delays and quantity refresh to 65535','Overview master/return controls','all nine Advanced settings and native scrollbar','master/session rejection messages','close preserves automation flags','x86 ABI and opaque text surface'],'windows_gdi_alpha':verify_gdi_alpha()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--game',type=Path);a=p.parse_args()
    result=verify(SupportMachine(a.directory.resolve(),a.game));(a.directory/'support-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
