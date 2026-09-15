"""Replay the real native mouse-capture branch behind crash 00A46B1C.

No live process/packets. --expect-crash reproduces the deployed v4 failure;
without it, item right-down must leave native left-drag capture untouched.
"""
import argparse
from test_gacha_ui import GachaMachine
from test_modern_chat_ui import pack
from unicorn import UcError
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EIP


def replay(exe, expect_crash):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready();manager=0x131F4E8
    m.w(obj+0x1c,0);m.w(obj+0x20,0);m.w(obj+0x10,0)
    m.right(obj,(30,149))
    assert m.r(s+60),'right-down did not record the item slot'
    assert m.r(manager+0x19c)==(obj if expect_crash else 0)
    # Native outer poll starts at its actual capture/no-capture selection.
    # Right-down capture forces the old code down the LEFT-button-only path.
    m.w(0x11e40e4,1);m.w(0x11e40e8,0);m.w(0x11e40ec,0)
    m.stub(0xA1EDD0,lambda:m.ret(0,obj)) # native root lookup
    m.stub(m.r(c['vtable']+8),lambda:m.ret(0,0)) # no focus/list promotion
    m.stub(0xA336D0,lambda:m.ret(8,0)) # following left-click outside UI
    code=m.alloc(256)
    prefix=(b'\x55\x8b\xec\x81\xec'+pack(0x90)+b'\x53\x56\x57\xbb'+pack(manager)+
            b'\xc7\x45\x8c'+pack(100)+b'\xc7\x45\x90'+pack(101)+b'\xe9')
    m.u.mem_write(code,prefix+pack(0xA46940-(code+len(prefix)+4)))
    done=code+192;m.u.mem_write(done,b'\x5f\x5e\x5b\x8b\xe5\x5d\xc3')
    for site in (0xA46F4C,0xA470CC):m.stub(site,lambda:m.u.reg_write(UC_X86_REG_EIP,done))
    # Base harness maps page zero for stock constructor SEH. No constructors run
    # during this poll; unmap it to model Windows' real null-pointer protection.
    m.u.mem_unmap(0,0x1000)
    try:
        m.invoke(code,obj)
    except UcError:
        assert expect_crash and m.u.reg_read(UC_X86_REG_EIP)==0xA46B1C
        assert m.u.reg_read(UC_X86_REG_ECX)==0 and m.r(manager+0x19c)==0
        print('REPRODUCED: v4 right-down -> captured left-down clears capture -> native 00A46B1C NULL read, exactly matching report')
        return
    assert not expect_crash,'old crash was not reproduced'
    assert m.r(manager+0x19c)==0
    # Right inspection must never disturb another window's existing capture.
    other=m.alloc(256);m.w(manager+0x19c,other)
    m.right(obj,(30,149));m.right(obj,(30,149),True)
    assert m.r(manager+0x19c)==other and not m.sent
    # Normal left-button controls still retain capture until mouse-up.
    m.w(manager+0x19c,0)
    m.invoke(c['down'],obj,(705,395));assert m.r(manager+0x19c)==obj
    m.invoke(c['up'],obj,(705,395));assert m.r(manager+0x19c)==0
    print('PASS: actual native poll takes uncaptured path after item right-down; no 00A46B1C crash, foreign capture preserved, left controls still capture/release')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--expect-crash',action='store_true');args=ap.parse_args()
    replay(args.exe,args.expect_crash)
