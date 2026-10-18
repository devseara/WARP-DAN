"""Execute current menu callbacks and server replies in the emitted x86.

Native allocation, transport and Windows services are explicit offline doubles.
"""
import argparse,json,struct
from pathlib import Path
from test_battlepass_board import BoardMachine

def verify(exe, manifest):
    exported=json.loads(manifest.read_text(encoding='utf8'));bp=exported['battlepass']
    m=BoardMachine(str(exe));s=m.c['state'];sent=[]
    def send():
        size,ptr=m.args(2);sent.append(bytes(m.u.mem_read(ptr,size)));m.ret(8)
    m.stub(bp['packetRefs']['packetSend'],send)
    timer_set,timer_kill=m.alloc(16),m.alloc(16);timers=[]
    m.stub(timer_set,lambda:(timers.append('start'),m.ret(16,567)))
    m.stub(timer_kill,lambda:(timers.append('stop'),m.ret(8,1)))
    m.w(s+16,timer_set);m.w(s+20,timer_kill)
    m.w(m.obj+0x28,0);m.w(s,0);m.u.mem_write(s+32,bytes(2872));m.w(s+24,0)
    m.invoke(bp['menuRequestVir'],0)
    assert not m.r(s) and sent==[struct.pack('<HHIHH',0xBF9,12,0x49555042,1,21)]
    disabled=bytearray(2240);struct.pack_into('<HHIHH',disabled,0,0xBF6,len(disabled),0x49555042,2,0)
    struct.pack_into('<H',disabled,1188,8192)
    m.receive(disabled);assert not m.r(s) and not m.r(s+24) and not timers
    # Existing hidden frame: approved reply is the only path that shows it.
    m.w(s,m.obj);m.invoke(bp['menuRequestVir'],0);assert not m.r(m.obj+0x28)
    allowed=bytearray(disabled);struct.pack_into('<H',allowed,10,32|16|0x8000)
    struct.pack_into('<H',allowed,1188,128)
    m.receive(allowed);assert m.r(m.obj+0x28) and timers==['start']
    m.receive(allowed);assert m.r(m.obj+0x28) and timers==['start'],'duplicate open must not toggle'
    m.w(s+2912,1);m.w(s+2924,2);m.w(s+2932,1)
    m.receive(disabled)
    assert not m.r(m.obj+0x28) and not m.r(s+24) and not m.r(s+2912) and not m.r(s+2924) and not m.r(s+2932)
    assert timers==['start','stop']
    m.invoke(bp['menuRequestVir'],0);m.receive(allowed);assert m.r(m.obj+0x28)
    before=len(sent);m.invoke(bp['menuRequestVir'],0)
    assert not m.r(m.obj+0x28) and len(sent)==before,'menu close stays immediate'
    print('PASS BP menu: initial request without window, disabled control, enable/reopen, duplicate reply, close and timer/input cleanup')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('manifest',type=Path)
    args=ap.parse_args();verify(args.exe,args.manifest)
