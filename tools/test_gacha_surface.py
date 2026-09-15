"""Replay actual CSurface cached GPU-tile upload/presentation after History.

Only the GPU texture allocation/upload/draw API is doubled. The stock surface
cache and 256px tile traversal execute unchanged, unlike CPU-only previews.
Use --expect-bug with v6 to reproduce its mid-lifetime alpha-mode switch.
"""
import argparse
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX
from test_gacha_ui import GachaMachine, snapshot


def verify(exe, expect_bug=False):
    m=GachaMachine(exe);c=m.c;obj=m.ready();surface=m.r(obj+0x24)
    head=m.alloc(12);m.w(head,head);m.w(head+4,head)
    m.w(surface+0x20,head);m.w(surface+0x24,0)
    textures={};uploads=[];draws=[]
    table=m.alloc(48);upload=m.alloc(16);draw=m.alloc(16)
    m.w(table+0x20,upload);m.w(table+0x28,draw)
    def create():
        width,height,mode,a,b=m.args(5)
        assert (a,b)==(0,0) and mode in (0,4)
        ptr=m.alloc(16);m.w(ptr,table);textures[ptr]=(width,height,mode)
        m.ret(20,ptr)
    def upload_texture():
        ptr=m.u.reg_read(UC_X86_REG_ECX);args=m.args(7)
        uploads.append((textures[ptr],args));m.ret(28)
    def draw_texture():
        ptr=m.u.reg_read(UC_X86_REG_ECX);args=m.args(5)
        draws.append((textures[ptr],args));m.ret(20)
    m.stub(0x568620,create);m.stub(upload,upload_texture);m.stub(draw,draw_texture)
    def present():
        # The real draw calls the real cache upload helper first.
        m.invoke(0x53EA90,surface,(0,0,760,440,0))
        assert (m.r(obj+0x14),m.r(obj+0x18),m.r(surface+4),m.r(surface+8))==(760,440,760,440)
    def check_tiles():
        expected=[(x,y,min(256,760-x),min(256,440-y),0)
                  for y in (0,256) for x in (0,256,512)]
        assert [tuple(args) for _,args in draws]==expected,draws
        assert len(uploads)==6
        for (width,height,mode),args in uploads:
            x,y,w,h,pixels,unused,pitch=args
            assert (x,y,w,h,unused,pitch)==(0,0,width,height,0,760),args
            assert mode==0 and pixels>=m.r(surface+0x18)
    # Warm the six native opaque tiles before the first History click.
    m.invoke(c['draw'],obj);m.u.mem_write(surface+0x1c,b'\1');present();check_tiles()
    assert len(textures)==6
    uploads.clear();draws.clear()
    m.receive(snapshot(view=2));m.invoke(c['draw'],obj);present()
    if expect_bug:
        assert m.r(surface+0x28)&255==1
        assert len(textures)==6 and len(uploads)==6 and len(draws)==6
        assert all(tuple(args[2:4])==(760,440) for _,args in uploads)
        assert all(tuple(args)==(0,0,760,440,0) for _,args in draws)
        print('REPRODUCED: History changes alpha mode after six opaque tiles exist; stock uploads the full 760x440 image to every small tile and draws all six at the same origin')
        return
    check_tiles();assert m.r(surface+0x28)&255==0
    # Page edges and returning to every other tab retain the same native tiles.
    for view,page in [(2,2),(2,10),(2,1),(1,100),(3,10),(4,10),(5,1),(0,1),(2,5)]:
        p=snapshot(view=view,page=page,pages=100 if view==1 else None,admin=view==5)
        m.receive(p);uploads.clear();draws.clear();m.invoke(c['draw'],obj)
        m.u.mem_write(surface+0x1c,b'\1');present();check_tiles()
        assert len(textures)==6 and m.r(surface+0x28)&255==0
    print('PASS: real native cached-tile upload/presentation stays 760x440 across History/page arrows/all tabs; six correct non-overlapping tiles, no surface-mode switch')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe');ap.add_argument('--expect-bug',action='store_true')
    args=ap.parse_args();verify(args.exe,args.expect_bug)
