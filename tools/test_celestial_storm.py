"""Execute the actual client storm receiver and native scene-lighting wrapper."""
import argparse
from pathlib import Path
import struct

from test_celestial_dial import Machine


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client',type=Path)
    args=parser.parse_args()
    m=Machine(args.client);s=m.c['state'];weather=0x15C57D8
    m.stub(0xC44540,lambda:m.ret(20,0))
    m.frame();m.receive(m.snapshot());m.frame()
    storm=dict(weather=128|256,rain_remaining=120000,map_name=b'prt_fild08\0',push=True)
    m.receive(m.snapshot(**storm));m.frame()
    assert 'Storm' in m.draw() and m.r(s+132)==384
    seq=m.r(s+20)
    for bad in [m.snapshot(weather=256,push=True),m.snapshot(protocol=3,**storm),
                m.snapshot(**{**storm,'rain_remaining':0}),
                m.snapshot(**{**storm,'map_name':b'prontera\0'})]:
        m.receive(bad);assert m.r(s+20)==seq
    m.now+=5000;m.frame();assert m.r(s+132)==0 and 'Clear' in m.draw()
    m.receive(m.snapshot(protocol=3,weather=128,rain_remaining=120000,map_name=b'prt_fild08\0',push=True))
    m.frame();assert 'Rain' in m.draw()
    # Execute stock CWeather::Process, including its real SSE blend calculations.
    m.u.hook_del(m.weather_hook)
    target=0xC74F76+struct.unpack('<i',bytes(m.u.mem_read(0xC74F72,4)))[0]
    assert target!=0xC136A0
    def initialize(night):
        m.u.mem_write(weather,bytes(0x60));m.u.mem_write(weather,bytes([int(night)]))
        for offset,value in [(0x14,.5),(0x18,.5),(0x1c,1.),(0x20,1.),(0x24,1.),(0x28,1.)]:
            m.u.mem_write(weather+offset,struct.pack('<f',value))
    def rgb():return struct.unpack('<3f',bytes(m.u.mem_read(weather+0x38,12)))
    initialize(True)
    m.receive(m.snapshot(phase=1,push=True));m.frame();m.invoke(target,ecx=weather)
    assert all(abs(a-b)<1e-5 for a,b in zip(rgb(),(.34,.39,.48))),rgb()
    assert bytes(m.u.mem_read(weather,3))==b'\1\0\0','Changed native weather flags'
    m.invoke(m.c['reset']);assert rgb()==(.5,.5,1.),'Reset failed to restore native scene RGB'
    # Indoor / non-nightenabled maps keep the exact stock colors, even in global night.
    m.frame();m.receive(m.snapshot(phase=1,flags=0));m.frame();initialize(False)
    m.invoke(target,ecx=weather)
    expected=rgb();assert expected[0]>.5 and expected[2]==1.
    # A stale or mismatched world cannot retain custom darkness.
    m.receive(m.snapshot(phase=1,push=True));m.frame();initialize(True)
    m.now+=90001;m.invoke(target,ecx=weather);assert rgb()==(.5,.5,1.)
    # A negotiated strike is one pulse; repeated pushes cannot restart it.
    m.receive(m.snapshot(phase=1,weather=128|256|512,rain_remaining=120000,generation=22,map_name=b'prt_fild08\0',push=True));m.frame()
    strike_tick=m.now;m.now+=45;initialize(True);m.invoke(target,ecx=weather)
    assert all(abs(a-b)<1e-5 for a,b in zip(rgb(),(.94,.97,1.))),rgb()
    m.receive(m.snapshot(phase=1,weather=128|256|512,rain_remaining=120000,generation=22,map_name=b'prt_fild08\0',push=True))
    assert m.r(s+200)==strike_tick,'Repeated snapshot restarted lightning'
    m.now=strike_tick+350;initialize(True);m.invoke(target,ecx=weather)
    assert all(abs(a-b)<1e-5 for a,b in zip(rgb(),(.34,.39,.48))),rgb()
    old=m.r(s+20)
    m.receive(m.snapshot(protocol=4,weather=128|256|512,rain_remaining=1000,map_name=b'prt_fild08\0',push=True))
    assert m.r(s+20)==old,'Legacy storm protocol accepted a flash bit'
    m.receive(m.snapshot(protocol=4,weather=128|256,rain_remaining=1000,map_name=b'prt_fild08\0',push=True));m.frame()
    assert 'Storm' in m.draw(),'V4 storm fallback failed'
    print('PASS: v5 storm/flash bounds, v3/v4 fallback, pulse/duplicate expiry, real native scene RGB, indoor/stale gates and reset')


if __name__=='__main__':main()
